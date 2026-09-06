"""Declarative base, shared column mixins and the native enum types (TRD 8.1, 8.2).

The ProvenanceMixin is the mechanism that makes TRD 10.2 enforceable: `source_type` is
NOT NULL with no default, so a write that forgets provenance fails at the database
rather than silently producing an unattributed record.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import ENUM as PGEnum
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""

    type_annotation_map: dict[Any, Any] = {}


# ---- Native PostgreSQL enum types (TRD 8.2) ----------------------------------
# `create_type=False` on column definitions; the types themselves are created once in
# the initial Alembic migration so repeated table definitions do not attempt to
# recreate them.


def pg_enum(*values: str, name: str) -> PGEnum:
    """Reference an existing native enum type.

    `create_type=False` because the types are created once, explicitly, in the initial
    Alembic migration. Without it, every table referencing the type would try to
    recreate it.
    """
    return PGEnum(*values, name=name, create_type=False)


USER_ROLE_VALUES = ("FARMER", "EXTENSION_WORKER", "LAB_EXPERT", "OFFICIAL", "ADMIN")
SOURCE_TYPE_VALUES = (
    "FIELD_OBSERVATION",
    "PUBLIC_DATA",
    "GOVERNMENT_DATA",
    "EXPERT_VALIDATION",
    "DEMO_SIMULATION",
)
VERIFICATION_STATUS_VALUES = (
    "PREDICTED",
    "PENDING_REVIEW",
    "CONFIRMED",
    "CORRECTED",
    "REJECTED",
    "LAB_REFERRED",
)
OBSERVATION_STATUS_VALUES = (
    "PROCESSING",
    "COMPLETED",
    "AI_FAILED",
    "UNSUPPORTED_IMAGE",
    "RISK_UNAVAILABLE",
)
OBSERVATION_TYPE_VALUES = ("IMAGE", "PEST_TRAP", "SENSOR", "MANUAL_REPORT")
AGENT_KIND_VALUES = ("DISEASE", "PEST", "DISORDER", "HEALTHY", "UNKNOWN")
LANGUAGE_CODE_VALUES = ("en", "hi", "mr")

user_role_enum = pg_enum(*USER_ROLE_VALUES, name="user_role")
source_type_enum = pg_enum(*SOURCE_TYPE_VALUES, name="source_type")
verification_status_enum = pg_enum(*VERIFICATION_STATUS_VALUES, name="verification_status")
observation_status_enum = pg_enum(*OBSERVATION_STATUS_VALUES, name="observation_status")
observation_type_enum = pg_enum(*OBSERVATION_TYPE_VALUES, name="observation_type")
agent_kind_enum = pg_enum(*AGENT_KIND_VALUES, name="agent_kind")
language_code_enum = pg_enum(*LANGUAGE_CODE_VALUES, name="language_code")


# ---- Column factories --------------------------------------------------------


def uuid_pk() -> Mapped[uuid.UUID]:
    """UUID primary key (TRD 8.1): non-enumerable, collision-free across seeders."""
    return mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )


class TimestampMixin:
    """created_at / updated_at in UTC (TRD 8.1)."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class SoftDeleteMixin:
    """Soft delete for user-owned entities (TRD 8.1).

    Audit and prediction tables deliberately do NOT use this - they are never deleted.
    """

    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None


class ProvenanceMixin:
    """Provenance columns (TRD 10.1).

    `source_type` is NOT NULL with no server default. This is intentional: it makes an
    unattributed record impossible to write, which is what stops demo data from ever
    being mistaken for a real field observation.
    """

    source_type: Mapped[str] = mapped_column(source_type_enum, nullable=False)
    original_source_ref: Mapped[str | None] = mapped_column(String, nullable=True)

    @property
    def is_demo(self) -> bool:
        """True when this record is simulated demo data and must be labelled as such."""
        return self.source_type == "DEMO_SIMULATION"
