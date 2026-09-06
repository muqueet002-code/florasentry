"""Risk assessment model (Phase 3).

Every row records HOW it was produced - `method`, `ruleset_version`, the full factor
breakdown and the inputs that were missing. That is what makes a score explainable and
reproducible after the fact, and it is why a new assessment always INSERTS rather than
updating: risk history is real history, not a reconstruction.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, risk_level_enum, uuid_pk


class RiskAssessment(Base):
    __tablename__ = "risk_assessments"

    id: Mapped[uuid.UUID] = uuid_pk()
    observation_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("observations.id", ondelete="CASCADE"), nullable=True
    )
    field_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("fields.id", ondelete="SET NULL"), nullable=True
    )
    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("disease_pest_catalog.id", ondelete="SET NULL"),
        nullable=True,
    )

    risk_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    risk_level: Mapped[str] = mapped_column(risk_level_enum, nullable=False)
    forecast_period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    forecast_period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # [{factor, value, weight, contribution, explanation_key}] - contributions sum to
    # risk_score, so a user can read exactly why the score is what it is.
    contributing_factors: Mapped[list[Any]] = mapped_column(JSONB, nullable=False)
    # [{factor, reason}] - inputs that were unavailable. Never silently defaulted.
    missing_factors: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)

    explanation_key: Mapped[str] = mapped_column(String(120), nullable=False)
    explanation_params: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    uncertainty: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)

    method: Mapped[str] = mapped_column(String(40), nullable=False)
    ruleset_version: Mapped[str] = mapped_column(String(40), nullable=False)
    weather_is_stale: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("risk_score >= 0 AND risk_score <= 100", name="ck_risk_score_range"),
        CheckConstraint(
            "observation_id IS NOT NULL OR field_id IS NOT NULL", name="ck_risk_target"
        ),
        Index("ix_risk_observation_id", "observation_id"),
        Index("ix_risk_field_computed", "field_id", "computed_at"),
        Index("ix_risk_level", "risk_level"),
    )
