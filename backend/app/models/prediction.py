"""AI model registry and prediction models (TRD 8.3).

Phase 1 creates these tables but registers NO model and writes NO prediction. The
inference pipeline is Phase 2. `evaluation_metrics` is populated only from an actual
evaluation run - it is never pre-filled, so no accuracy figure exists until one is
genuinely measured (TRD 15.9).
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
    Integer,
    Numeric,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, uuid_pk


class AiModelRegistry(Base, TimestampMixin):
    """Makes models replaceable and every prediction traceable to a version."""

    __tablename__ = "ai_model_registry"

    id: Mapped[uuid.UUID] = uuid_pk()
    model_version: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    task: Mapped[str] = mapped_column(String(30), nullable=False)  # CLASSIFICATION / DETECTION
    framework: Mapped[str] = mapped_column(String(30), nullable=False)
    runner_class: Mapped[str] = mapped_column(String(120), nullable=False)
    artifact_key: Mapped[str] = mapped_column(Text, nullable=False)
    artifact_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    input_size: Mapped[str] = mapped_column(String(20), nullable=False)
    class_list: Mapped[list[Any]] = mapped_column(JSONB, nullable=False)

    # Thresholds live per model, not in environment config, so a model swap carries its
    # own thresholds. Values must come from a real evaluation run (TRD decision D4).
    high_confidence_threshold: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False)
    low_confidence_threshold: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False)

    training_dataset_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    evaluation_metrics: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint("task IN ('CLASSIFICATION','DETECTION')", name="ck_model_task"),
        CheckConstraint(
            "high_confidence_threshold >= 0 AND high_confidence_threshold <= 1 "
            "AND low_confidence_threshold >= 0 AND low_confidence_threshold <= 1 "
            "AND low_confidence_threshold <= high_confidence_threshold",
            name="ck_model_thresholds",
        ),
        # Exactly one active model per task (TRD 8.3 partial unique index).
        Index(
            "uq_active_model_per_task",
            "task",
            unique=True,
            postgresql_where=text("is_active"),
        ),
    )


class AiPrediction(Base):
    """Immutable AI output.

    A prediction row is never updated. Re-running inference creates a new row, so
    prediction history is preserved for model comparison (TRD 8.3). There is
    deliberately no `updated_at` and no soft delete.
    """

    __tablename__ = "ai_predictions"

    id: Mapped[uuid.UUID] = uuid_pk()
    observation_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("observations.id", ondelete="CASCADE"), nullable=False
    )
    image_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("observation_images.id", ondelete="SET NULL"),
        nullable=True,
    )
    model_version: Mapped[str] = mapped_column(
        String(60),
        ForeignKey("ai_model_registry.model_version", ondelete="RESTRICT"),
        nullable=False,
    )
    predicted_agent_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("disease_pest_catalog.id", ondelete="SET NULL"),
        nullable=True,
    )
    # The raw model label is always kept, even when it maps to no catalogue entry.
    predicted_class: Mapped[str] = mapped_column(String(80), nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    top_k: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)
    severity_estimate: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    is_low_confidence: Mapped[bool] = mapped_column(Boolean, nullable=False)
    bbox_geojson: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    inference_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    runtime_device: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    observation = relationship("Observation", back_populates="predictions")

    __table_args__ = (
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_ai_pred_confidence_range"),
        Index("ix_ai_pred_observation_id", "observation_id"),
        Index("ix_ai_pred_model_version", "model_version"),
        Index("ix_ai_pred_confidence", "confidence"),
    )
