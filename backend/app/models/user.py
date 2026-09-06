"""User and refresh-token models (TRD 8.3, 13.1)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import (
    Base,
    SoftDeleteMixin,
    TimestampMixin,
    language_code_enum,
    user_role_enum,
    uuid_pk,
)


class User(Base, TimestampMixin, SoftDeleteMixin):
    """Authentication principal and role holder for all five user types."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = uuid_pk()

    # At least one login identifier is required (see the check constraint below).
    phone: Mapped[str | None] = mapped_column(String(20), unique=True, nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    username: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)

    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    role: Mapped[str] = mapped_column(user_role_enum, nullable=False, server_default="FARMER")
    preferred_language: Mapped[str] = mapped_column(
        language_code_enum, nullable=False, server_default="en"
    )
    district_code: Mapped[str | None] = mapped_column(
        String(20), ForeignKey("admin_regions.code", ondelete="SET NULL"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    farmer = relationship("Farmer", back_populates="user", uselist=False)
    refresh_tokens = relationship(
        "RefreshToken", back_populates="user", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            "phone IS NOT NULL OR email IS NOT NULL OR username IS NOT NULL",
            name="ck_users_has_identifier",
        ),
        Index("ix_users_role", "role"),
        Index("ix_users_district_code", "district_code"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<User {self.id} role={self.role}>"


class RefreshToken(Base):
    """Stored refresh tokens with rotation and reuse detection (TRD 13.1).

    Only the SHA-256 hash of the token is stored; the plaintext exists solely in the
    response to the client.
    """

    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    replaced_by: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(INET, nullable=True)

    user = relationship("User", back_populates="refresh_tokens")

    __table_args__ = (Index("ix_refresh_tokens_user_id", "user_id"),)
