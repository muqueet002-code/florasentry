"""Authentication endpoints (TRD 12.1)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, get_client_ip, get_current_user, get_db
from app.core.responses import success
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    UserOut,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


def _token_payload(tokens: tuple[str, str, int]) -> dict[str, object]:
    access, refresh, expires_in = tokens
    return {
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "bearer",
        "expires_in": expires_in,
    }


@router.post("/register", status_code=status.HTTP_201_CREATED, summary="Register a farmer account")
def register(
    payload: RegisterRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """Self-registration. Always creates a FARMER; privileged roles are admin-created."""
    service = AuthService(db)
    user, tokens = service.register_farmer(
        full_name=payload.full_name,
        phone=payload.phone,
        password=payload.password,
        preferred_language=payload.preferred_language,
        village=payload.village,
        taluka=payload.taluka,
        district_code=payload.district_code,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    return success(
        {
            "user": UserOut.model_validate(user).model_dump(mode="json"),
            "tokens": _token_payload(tokens),
        }
    )


@router.post("/login", summary="Obtain an access/refresh token pair")
def login(
    payload: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    service = AuthService(db)
    user, tokens = service.login(
        identifier=payload.identifier,
        password=payload.password,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    return success(
        {
            "user": UserOut.model_validate(user).model_dump(mode="json"),
            **_token_payload(tokens),
        }
    )


@router.post("/refresh", summary="Rotate the token pair")
def refresh(
    payload: RefreshRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    service = AuthService(db)
    _user, tokens = service.refresh(
        raw_refresh_token=payload.refresh_token,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    return success(_token_payload(tokens))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, summary="Revoke a refresh token")
def logout(payload: RefreshRequest, db: Session = Depends(get_db)) -> Response:
    AuthService(db).logout(raw_refresh_token=payload.refresh_token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", summary="Current principal and effective permissions")
def me(
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    from app.repositories.user_repository import UserRepository

    user = UserRepository(db).get(current.id)
    return success(
        {
            "user": UserOut.model_validate(user).model_dump(mode="json"),
            "farmer_id": str(current.farmer_id) if current.farmer_id else None,
            "permissions": sorted(p.value for p in current.permissions),
        }
    )


@router.post("/change-password", summary="Change own password")
def change_password(
    payload: ChangePasswordRequest,
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """Succeeds only with the correct current password. Revokes all existing sessions."""
    AuthService(db).change_password(
        user_id=current.id,
        current_password=payload.current_password,
        new_password=payload.new_password,
    )
    return success({"changed": True})
