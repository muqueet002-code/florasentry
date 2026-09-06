"""Authentication business logic (TRD 5.1, 13.1).

Rotating refresh tokens with reuse detection: presenting a token that has already been
rotated revokes the entire chain for that user and writes an audit entry.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.errors import (
    AuthenticationError,
    ConflictError,
    InvalidCredentialsError,
    ValidationError,
)
from app.core.logging import get_logger
from app.core.rbac import UserRole
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    needs_rehash,
    refresh_token_expiry,
    validate_password_strength,
    verify_password,
)
from app.models.user import RefreshToken, User
from app.repositories.user_repository import RefreshTokenRepository, UserRepository
from app.services import audit_service as audit_actions
from app.services.audit_service import AuditService

logger = get_logger(__name__)


class AuthService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.users = UserRepository(db)
        self.tokens = RefreshTokenRepository(db)
        self.audit = AuditService(db)

    # ---- registration ----

    def register_farmer(
        self,
        *,
        full_name: str,
        phone: str,
        password: str,
        preferred_language: str = "en",
        village: str | None = None,
        taluka: str | None = None,
        district_code: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[User, tuple[str, str, int]]:
        """Register a FARMER account. Privileged roles are created by an admin only."""
        if self.users.phone_exists(phone):
            raise ConflictError(
                "An account with this phone number already exists.",
                code="DUPLICATE_PHONE",
                message_key="errors.duplicate_phone",
                details=[{"field": "phone", "issue": "already_registered"}],
            )

        validate_password_strength(password)
        user = self.users.create(
            full_name=full_name,
            password_hash=hash_password(password),
            role=UserRole.FARMER,
            phone=phone,
            preferred_language=preferred_language,
            district_code=district_code,
        )
        self.users.create_farmer_profile(
            user=user, village=village, taluka=taluka, district_code=district_code
        )

        self.audit.record(
            action=audit_actions.ACTION_REGISTER,
            entity_type="user",
            entity_id=user.id,
            actor_user_id=user.id,
            actor_role=user.role,
            after_state={"role": user.role, "full_name": user.full_name},
            ip_address=ip_address,
            user_agent=user_agent,
        )
        tokens = self._issue_tokens(user, ip_address=ip_address, user_agent=user_agent)
        return user, tokens

    # ---- login ----

    def login(
        self,
        *,
        identifier: str,
        password: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[User, tuple[str, str, int]]:
        user = self.users.get_by_identifier(identifier)

        # verify_password always performs a hash comparison, including when the user
        # does not exist, so timing does not disclose account existence (TRD 13.2).
        if not verify_password(password, user.password_hash if user else None):
            self.audit.record(
                action=audit_actions.ACTION_LOGIN_FAILURE,
                entity_type="user",
                entity_id=user.id if user else None,
                actor_user_id=user.id if user else None,
                after_state={"reason": "invalid_credentials"},
                ip_address=ip_address,
                user_agent=user_agent,
            )
            raise InvalidCredentialsError()

        assert user is not None  # narrowed by verify_password returning True
        if not user.is_active or user.deleted_at is not None:
            raise AuthenticationError(
                "Account is not active.",
                code="AUTH_ACCOUNT_INACTIVE",
                message_key="errors.auth_account_inactive",
            )

        # Transparently upgrade the hash if Argon2 parameters have been strengthened.
        if needs_rehash(user.password_hash):
            self.users.set_password_hash(user, hash_password(password))

        self.users.touch_last_login(user)
        self.audit.record(
            action=audit_actions.ACTION_LOGIN_SUCCESS,
            entity_type="user",
            entity_id=user.id,
            actor_user_id=user.id,
            actor_role=user.role,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        tokens = self._issue_tokens(user, ip_address=ip_address, user_agent=user_agent)
        return user, tokens

    # ---- refresh ----

    def refresh(
        self,
        *,
        raw_refresh_token: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[User, tuple[str, str, int]]:
        token_hash = hash_refresh_token(raw_refresh_token)
        stored = self.tokens.get_by_hash(token_hash)

        if stored is None:
            raise AuthenticationError(
                "Invalid refresh token.",
                code="AUTH_INVALID_REFRESH",
                message_key="errors.auth_invalid_refresh",
            )

        if stored.revoked_at is not None:
            # Reuse of an already-rotated token: assume compromise, kill the chain.
            revoked = self.tokens.revoke_all_for_user(stored.user_id)
            self.audit.record(
                action=audit_actions.ACTION_TOKEN_REUSE_DETECTED,
                entity_type="refresh_token",
                entity_id=stored.id,
                actor_user_id=stored.user_id,
                after_state={"revoked_token_count": revoked},
                ip_address=ip_address,
                user_agent=user_agent,
            )
            logger.warning("refresh_token_reuse_detected", extra={"user_id": str(stored.user_id)})
            raise AuthenticationError(
                "Refresh token has been revoked.",
                code="AUTH_REFRESH_REVOKED",
                message_key="errors.auth_refresh_revoked",
            )

        if self._is_expired(stored):
            raise AuthenticationError(
                "Refresh token has expired.",
                code="AUTH_REFRESH_EXPIRED",
                message_key="errors.auth_refresh_expired",
            )

        user = self.users.get(stored.user_id)
        if user is None or not user.is_active or user.deleted_at is not None:
            raise AuthenticationError(
                "Account is not active.",
                code="AUTH_ACCOUNT_INACTIVE",
                message_key="errors.auth_account_inactive",
            )

        new_tokens = self._issue_tokens(user, ip_address=ip_address, user_agent=user_agent)
        newest = self.tokens.get_by_hash(hash_refresh_token(new_tokens[1]))
        self.tokens.revoke(stored, replaced_by=newest.id if newest else None)

        self.audit.record(
            action=audit_actions.ACTION_TOKEN_REFRESH,
            entity_type="refresh_token",
            entity_id=stored.id,
            actor_user_id=user.id,
            actor_role=user.role,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return user, new_tokens

    # ---- logout ----

    def logout(self, *, raw_refresh_token: str, actor: uuid.UUID | None = None) -> None:
        stored = self.tokens.get_by_hash(hash_refresh_token(raw_refresh_token))
        if stored is not None and stored.revoked_at is None:
            self.tokens.revoke(stored)
            self.audit.record(
                action=audit_actions.ACTION_LOGOUT,
                entity_type="refresh_token",
                entity_id=stored.id,
                actor_user_id=actor or stored.user_id,
            )
        # An unknown or already-revoked token is not an error: logout is idempotent.

    # ---- password change ----

    def change_password(
        self, *, user_id: uuid.UUID, current_password: str, new_password: str
    ) -> None:
        user = self.users.get(user_id)
        if user is None:
            raise AuthenticationError()
        if not verify_password(current_password, user.password_hash):
            raise InvalidCredentialsError("Current password is incorrect.")
        if current_password == new_password:
            raise ValidationError(
                "The new password must differ from the current one.",
                message_key="errors.password_unchanged",
                details=[{"field": "new_password", "issue": "unchanged"}],
            )

        validate_password_strength(new_password)
        self.users.set_password_hash(user, hash_password(new_password))
        # Changing a password invalidates every existing session.
        self.tokens.revoke_all_for_user(user.id)
        self.audit.record(
            action=audit_actions.ACTION_PASSWORD_CHANGED,
            entity_type="user",
            entity_id=user.id,
            actor_user_id=user.id,
            actor_role=user.role,
        )

    # ---- internals ----

    def _issue_tokens(
        self, user: User, *, ip_address: str | None, user_agent: str | None
    ) -> tuple[str, str, int]:
        """Return (access_token, refresh_token, expires_in_seconds)."""
        farmer = self.users.get_farmer_by_user(user.id) if user.role == "FARMER" else None
        access, expires_in = create_access_token(
            user_id=user.id,
            role=user.role,
            farmer_id=farmer.id if farmer else None,
            district_code=user.district_code,
        )
        raw_refresh, refresh_hash = generate_refresh_token()
        self.tokens.create(
            user_id=user.id,
            token_hash=refresh_hash,
            expires_at=refresh_token_expiry(),
            user_agent=user_agent,
            ip_address=ip_address,
        )
        return access, raw_refresh, expires_in

    @staticmethod
    def _is_expired(token: RefreshToken) -> bool:
        expires = token.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=UTC)
        return expires < datetime.now(UTC)
