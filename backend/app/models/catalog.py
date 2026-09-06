"""Crop context and diagnosable-agent catalogue (TRD 8.3).

`disease_pest_catalog` is a single table with a `kind` discriminator rather than
separate `diseases` and `pests` tables. Rationale (TRD 8.3): they share every
structural column, and two tables would force mutually exclusive nullable foreign keys
in ai_predictions, expert_reviews, advisories, hotspots and observations.
"""

from __future__ import annotations

import uuid

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, agent_kind_enum, uuid_pk


class Crop(Base, TimestampMixin):
    __tablename__ = "crops"

    id: Mapped[uuid.UUID] = uuid_pk()
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    name_en: Mapped[str] = mapped_column(String(120), nullable=False)
    name_hi: Mapped[str] = mapped_column(String(120), nullable=False)
    name_mr: Mapped[str] = mapped_column(String(120), nullable=False)
    scientific_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    varieties = relationship("CropVariety", back_populates="crop", cascade="all, delete-orphan")
    growth_stages = relationship("GrowthStage", back_populates="crop", cascade="all, delete-orphan")


class CropVariety(Base, TimestampMixin):
    __tablename__ = "crop_varieties"

    id: Mapped[uuid.UUID] = uuid_pk()
    crop_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("crops.id", ondelete="CASCADE"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(60), nullable=False)
    name_en: Mapped[str] = mapped_column(String(120), nullable=False)
    name_hi: Mapped[str] = mapped_column(String(120), nullable=False)
    name_mr: Mapped[str] = mapped_column(String(120), nullable=False)
    duration_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    crop = relationship("Crop", back_populates="varieties")

    __table_args__ = (
        UniqueConstraint("crop_id", "code", name="uq_crop_varieties_crop_code"),
        Index("ix_crop_varieties_crop_id", "crop_id"),
    )


class GrowthStage(Base, TimestampMixin):
    __tablename__ = "growth_stages"

    id: Mapped[uuid.UUID] = uuid_pk()
    crop_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("crops.id", ondelete="CASCADE"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    name_en: Mapped[str] = mapped_column(String(120), nullable=False)
    name_hi: Mapped[str] = mapped_column(String(120), nullable=False)
    name_mr: Mapped[str] = mapped_column(String(120), nullable=False)
    sequence: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    typical_days_from_sowing_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    typical_days_from_sowing_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    susceptibility_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    crop = relationship("Crop", back_populates="growth_stages")

    __table_args__ = (
        UniqueConstraint("crop_id", "code", name="uq_growth_stages_crop_code"),
        UniqueConstraint("crop_id", "sequence", name="uq_growth_stages_crop_sequence"),
        Index("ix_growth_stages_crop_id", "crop_id"),
    )


class DiseasePestCatalog(Base, TimestampMixin):
    """A diagnosable agent: disease, pest, disorder, healthy or unknown."""

    __tablename__ = "disease_pest_catalog"

    id: Mapped[uuid.UUID] = uuid_pk()
    code: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    kind: Mapped[str] = mapped_column(agent_kind_enum, nullable=False)
    name_en: Mapped[str] = mapped_column(String(150), nullable=False)
    name_hi: Mapped[str] = mapped_column(String(150), nullable=False)
    name_mr: Mapped[str] = mapped_column(String(150), nullable=False)
    scientific_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    description_key: Mapped[str | None] = mapped_column(String(120), nullable=True)
    # True ONLY for classes the currently active model can actually output.
    # Phase 1 ships no model, so every row is false. Phase 2 sets this from the
    # registered model's class list - it is never set by hand.
    is_ai_supported: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")

    __table_args__ = (Index("ix_disease_pest_catalog_kind", "kind"),)


class AgentCrop(Base):
    """Which agents affect which crops."""

    __tablename__ = "agent_crops"

    agent_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("disease_pest_catalog.id", ondelete="CASCADE"),
        primary_key=True,
    )
    crop_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("crops.id", ondelete="CASCADE"), primary_key=True
    )


class Symptom(Base, TimestampMixin):
    """Symptom vocabulary.

    Kept as its own table because the expert UI (Phase 5) and advisory templates
    (Phase 6) reference symptoms independently of any single agent.
    """

    __tablename__ = "symptoms"

    id: Mapped[uuid.UUID] = uuid_pk()
    code: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    name_en: Mapped[str] = mapped_column(String(150), nullable=False)
    name_hi: Mapped[str] = mapped_column(String(150), nullable=False)
    name_mr: Mapped[str] = mapped_column(String(150), nullable=False)
    body_part: Mapped[str | None] = mapped_column(String(40), nullable=True)


class AgentSymptom(Base):
    __tablename__ = "agent_symptoms"

    agent_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("disease_pest_catalog.id", ondelete="CASCADE"),
        primary_key=True,
    )
    symptom_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("symptoms.id", ondelete="CASCADE"), primary_key=True
    )
    typicality: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
