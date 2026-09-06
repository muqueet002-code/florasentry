"""User and refresh-token data access (TRD 6.2).

All SQL lives in the repository layer. Services never write SQL; routers never touch
the ORM.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.rbac import UserRole
from app.models.farmer import Farmer
from app.models.user import RefreshToken, User


class UserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ---- users ----

    def get(self, user_id: uuid.UUID) -> User | None:
        return self.db.get(User, user_id)

    def get_by_identifier(self, identifier: str) -> User | None:
        """Look up by phone, email or username (TRD 12.1)."""
        ident = identifier.strip()
        stmt = select(User).where(
            (User.phone == ident) | (User.email == ident.lower()) | (User.username == ident),
            User.deleted_at.is_(None),
        )
        return self.db.execute(stmt).scalars().first()

    def phone_exists(self, phone: str) -> bool:
        stmt = select(User.id).where(User.phone == phone)
        return self.db.execute(stmt).first() is not None

    def email_exists(self, email: str) -> bool:
        stmt = select(User.id).where(User.email == email.lower())
        return self.db.execute(stmt).first() is not None

    def create(
        self,
        *,
        full_name: str,
        password_hash: str,
        role: UserRole,
        phone: str | None = None,
        email: str | None = None,
        username: str | None = None,
        preferred_language: str = "en",
        district_code: str | None = None,
    ) -> User:
        user = User(
            full_name=full_name,
            password_hash=password_hash,
            role=role.value,
            phone=phone,
            email=email.lower() if email else None,
            username=username,
            preferred_language=preferred_language,
            district_code=district_code,
            is_active=True,
        )
        self.db.add(user)
        self.db.flush()  # assign the PK without ending the request transaction
        return user

    def count_active_admins(self) -> int:
        stmt = select(User.id).where(
            User.role == UserRole.ADMIN.value,
            User.is_active.is_(True),
            User.deleted_at.is_(None),
        )
        return len(self.db.execute(stmt).all())

    def touch_last_login(self, user: User) -> None:
        user.last_login_at = datetime.now(UTC)
        self.db.flush()

    def set_password_hash(self, user: User, password_hash: str) -> None:
        user.password_hash = password_hash
        self.db.flush()

    # ---- farmer profile ----

    def create_farmer_profile(
        self,
        *,
        user: User,
        village: str | None = None,
        taluka: str | None = None,
        district_code: str | None = None,
    ) -> Farmer:
        farmer = Farmer(
            user_id=user.id,
            village=village,
            taluka=taluka,
            district_code=district_code,
        )
        self.db.add(farmer)
        self.db.flush()
        return farmer

    def get_farmer_by_user(self, user_id: uuid.UUID) -> Farmer | None:
        stmt = select(Farmer).where(Farmer.user_id == user_id)
        return self.db.execute(stmt).scalars().first()


class RefreshTokenRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        *,
        user_id: uuid.UUID,
        token_hash: str,
        expires_at: datetime,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> RefreshToken:
        token = RefreshToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            user_agent=user_agent,
            ip_address=ip_address,
        )
        self.db.add(token)
        self.db.flush()
        return token

    def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        return self.db.execute(stmt).scalars().first()

    def revoke(self, token: RefreshToken, *, replaced_by: uuid.UUID | None = None) -> None:
        token.revoked_at = datetime.now(UTC)
        token.replaced_by = replaced_by
        self.db.flush()

    def revoke_all_for_user(self, user_id: uuid.UUID) -> int:
        """Revoke every live token for a user (reuse detection, deactivation)."""
        stmt = select(RefreshToken).where(
            RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None)
        )
        tokens = list(self.db.execute(stmt).scalars().all())
        now = datetime.now(UTC)
        for token in tokens:
            token.revoked_at = now
        self.db.flush()
        return len(tokens)
