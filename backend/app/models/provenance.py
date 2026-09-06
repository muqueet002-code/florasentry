"""Data-source register and audit log (TRD 8.3).

`data_sources` is what makes "no dataset may be represented as official or live without
verification" (PRD 7.2) enforceable rather than aspirational: any UI element rendering
attributed data must resolve its source here, and a source with `is_verified = false`
must be labelled unverified.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, source_type_enum, user_role_enum, uuid_pk

DATA_SOURCE_CATEGORIES = (
    "BOUNDARY",
    "WEATHER",
    "CROP_STATS",
    "TRAINING_DATA",
    "ADVISORY_CONTENT",
    "REFERENCE_CATALOG",
    "OTHER",
)


class DataSource(Base, TimestampMixin):
    __tablename__ = "data_sources"

    id: Mapped[uuid.UUID] = uuid_pk()
    code: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    source_type: Mapped[str] = mapped_column(source_type_enum, nullable=False)
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    provider_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    licence: Mapped[str | None] = mapped_column(String(120), nullable=True)
    version_or_release: Mapped[str | None] = mapped_column(String(60), nullable=True)
    retrieved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Defaults to false: a source is unverified until a human verifies it.
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    verified_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "category IN ({})".format(", ".join(f"'{c}'" for c in DATA_SOURCE_CATEGORIES)),
            name="ck_data_sources_category",
        ),
        Index("ix_data_sources_category", "category"),
    )


class AuditLog(Base):
    """Append-only business audit trail (TRD 33.1).

    Deliberately NOT a UUID PK: this table is append-only and high-volume, so a
    sequential BIGSERIAL is the right choice. The application database role is granted
    no UPDATE or DELETE on this table.
    """

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    actor_role: Mapped[str | None] = mapped_column(user_role_enum, nullable=True)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(60), nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    before_state: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    after_state: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(INET, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_audit_entity", "entity_type", "entity_id"),
        Index("ix_audit_actor_time", "actor_user_id", "created_at"),
        Index("ix_audit_action_time", "action", "created_at"),
    )
