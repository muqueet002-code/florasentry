"""Shared FastAPI dependencies (TRD 6.3).

`Depends` is the only dependency-injection mechanism. Adapters (model runner, weather
provider, storage) are resolved from configuration here rather than at the import site,
which is what keeps them replaceable.
"""

from __future__ import annotations

import ipaddress
import uuid
from collections.abc import Callable
from dataclasses import dataclass

from fastapi import Depends, Header, Query, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import AuthenticationError, AuthorizationError
from app.core.rbac import Permission, UserRole, has_permission, permissions_for
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User

# auto_error=False so a missing header raises our own enveloped 401 rather than
# FastAPI's default body shape.
bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentUser:
    """The authenticated principal, as seen by services and repositories."""

    id: uuid.UUID
    role: UserRole
    full_name: str
    farmer_id: uuid.UUID | None
    district_code: str | None
    preferred_language: str

    @property
    def permissions(self) -> frozenset[Permission]:
        return permissions_for(self.role)

    def can(self, permission: Permission) -> bool:
        return has_permission(self.role, permission)

    @property
    def is_admin(self) -> bool:
        return self.role is UserRole.ADMIN


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> CurrentUser:
    """Decode the bearer token and load the active user."""
    if credentials is None or not credentials.credentials:
        raise AuthenticationError()

    payload = decode_access_token(credentials.credentials)
    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise AuthenticationError(
            "Malformed token subject.",
            code="AUTH_INVALID_TOKEN",
            message_key="errors.auth_invalid_token",
        ) from exc

    user = db.get(User, user_id)
    if user is None or not user.is_active or user.deleted_at is not None:
        # A token can outlive a deactivated account; re-check on every request.
        raise AuthenticationError(
            "Account is not active.",
            code="AUTH_ACCOUNT_INACTIVE",
            message_key="errors.auth_account_inactive",
        )

    return CurrentUser(
        id=user.id,
        role=UserRole(user.role),
        full_name=user.full_name,
        farmer_id=user.farmer.id if user.farmer else None,
        district_code=user.district_code,
        preferred_language=user.preferred_language,
    )


def require_roles(*roles: UserRole) -> Callable[[CurrentUser], CurrentUser]:
    """Guard factory: allow only the listed roles.

    Usage:
        @router.get("/x", dependencies=[Depends(require_roles(UserRole.ADMIN))])
    """
    allowed = set(roles)

    def _guard(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if user.role not in allowed:
            raise AuthorizationError(
                f"This action requires one of: {', '.join(sorted(r.value for r in allowed))}."
            )
        return user

    return _guard


def require_permission(permission: Permission) -> Callable[[CurrentUser], CurrentUser]:
    """Guard factory: allow any role holding the given permission.

    Preferred over `require_roles` for capability-based checks, because adding a role
    later only requires editing the matrix in `core/rbac.py`.
    """

    def _guard(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if not user.can(permission):
            raise AuthorizationError(f"This action requires the '{permission.value}' permission.")
        return user

    return _guard


def get_language(
    lang: str | None = Query(default=None),
    accept_language: str | None = Header(default=None),
) -> str:
    """Language negotiation (TRD 22.2): ?lang= > Accept-Language > default.

    `lang` is declared here, once, so every route depending on `get_language`
    automatically accepts the query override - a route does not need to redeclare it.
    """
    if lang:
        base = lang.strip().lower().split("-")[0]
        if base in settings.supported_languages:
            return base

    if accept_language:
        for part in accept_language.split(","):
            code = part.split(";")[0].strip().lower()
            base = code.split("-")[0]
            if base in settings.supported_languages:
                return base
    return settings.DEFAULT_LANGUAGE


def get_client_ip(request: Request) -> str | None:
    """Best-effort client IP for audit rows.

    The result is stored in an INET column, so anything that is not a parseable IP
    address is discarded rather than passed through. Without this, a malformed
    `X-Forwarded-For` header (which is entirely client-controlled) would raise a
    database DataError and turn a login into a 500.
    """
    candidates: list[str] = []
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        candidates.append(forwarded.split(",")[0].strip())
    if request.client:
        candidates.append(request.client.host)

    for candidate in candidates:
        try:
            return str(ipaddress.ip_address(candidate))
        except ValueError:
            continue
    return None


# Re-exported so routers import a single module.
__all__ = [
    "CurrentUser",
    "Session",
    "get_client_ip",
    "get_current_user",
    "get_db",
    "get_language",
    "require_permission",
    "require_roles",
]
