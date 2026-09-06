"""Observation and observation-image models (TRD 8.3).

This is the central record of the system. Two constraints here carry product meaning,
not just data hygiene:

1. `ck_obs_final_agent_requires_verification` - `final_agent_id` (the accepted
   diagnosis) can only be set when an expert has CONFIRMED or CORRECTED the record.
   This is a database-level guarantee that an AI prediction can never masquerade as a
   confirmed diagnosis (TRD 4.4, 8.3).

2. `source_type` is NOT NULL with no default (ProvenanceMixin) - an observation without
   provenance cannot be written at all, so demo data can never be silently presented as
   a real field observation (TRD 10.2).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from geoalchemy2 import Geometry
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import (
    Base,
    ProvenanceMixin,
    SoftDeleteMixin,
    TimestampMixin,
    observation_status_enum,
    observation_type_enum,
    uuid_pk,
    verification_status_enum,
)


class Observation(Base, TimestampMixin, SoftDeleteMixin, ProvenanceMixin):
    __tablename__ = "observations"

    id: Mapped[uuid.UUID] = uuid_pk()

    farmer_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("farmers.id", ondelete="SET NULL"), nullable=True
    )
    reported_by: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    field_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("fields.id", ondelete="SET NULL"), nullable=True
    )
    crop_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("crops.id", ondelete="SET NULL"), nullable=True
    )
    variety_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("crop_varieties.id", ondelete="SET NULL"), nullable=True
    )
    growth_stage_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("growth_stages.id", ondelete="SET NULL"), nullable=True
    )

    observation_type: Mapped[str] = mapped_column(
        observation_type_enum, nullable=False, server_default="IMAGE"
    )

    # 6 decimal places (~0.11 m). More precision is false precision for phone GPS.
    latitude: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)
    longitude: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)
    geom: Mapped[object] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=False), nullable=False
    )
    gps_accuracy_m: Mapped[Decimal | None] = mapped_column(Numeric(7, 2), nullable=True)
    location_method: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="DEVICE_GPS"
    )
    district_code: Mapped[str | None] = mapped_column(
        String(20), ForeignKey("admin_regions.code", ondelete="SET NULL"), nullable=True
    )

    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    reported_severity: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Pipeline state, distinct from truth state.
    status: Mapped[str] = mapped_column(
        observation_status_enum, nullable=False, server_default="PROCESSING"
    )
    # Truth state. Never collapsed into `status` (TRD 20.2).
    verification_status: Mapped[str] = mapped_column(
        verification_status_enum, nullable=False, server_default="PREDICTED"
    )
    # The accepted diagnosis. Set ONLY on CONFIRMED / CORRECTED - see the check below.
    final_agent_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("disease_pest_catalog.id", ondelete="RESTRICT"),
        nullable=True,
    )

    verified_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Optional short note an expert leaves with a CONFIRM/CORRECT/REJECT decision
    # (Phase 5). Distinct from the farmer's own `notes` above.
    review_note: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    data_source_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("data_sources.id", ondelete="SET NULL"), nullable=True
    )
    parent_observation_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("observations.id", ondelete="SET NULL"), nullable=True
    )
    processing_errors: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    field = relationship("Field", back_populates="observations")
    images = relationship(
        "ObservationImage", back_populates="observation", cascade="all, delete-orphan"
    )
    predictions = relationship(
        "AiPrediction", back_populates="observation", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("latitude >= -90 AND latitude <= 90", name="ck_obs_latitude_range"),
        CheckConstraint("longitude >= -180 AND longitude <= 180", name="ck_obs_longitude_range"),
        CheckConstraint(
            "reported_severity IS NULL OR (reported_severity BETWEEN 1 AND 5)",
            name="ck_obs_reported_severity_range",
        ),
        CheckConstraint(
            "location_method IN ('DEVICE_GPS','MAP_PIN','FIELD_CENTROID')",
            name="ck_obs_location_method",
        ),
        # The prediction-is-not-a-diagnosis guarantee.
        CheckConstraint(
            "final_agent_id IS NULL OR verification_status IN ('CONFIRMED','CORRECTED')",
            name="ck_obs_final_agent_requires_verification",
        ),
        Index("gix_observations_geom", "geom", postgresql_using="gist"),
        # Partial spatial indexes for the two hottest map queries (TRD 9.3): the
        # confirmed-cases layer, and any layer that excludes demo data.
        Index(
            "gix_obs_geom_confirmed",
            "geom",
            postgresql_using="gist",
            postgresql_where=text(
                "verification_status IN ('CONFIRMED','CORRECTED') AND deleted_at IS NULL"
            ),
        ),
        Index(
            "gix_obs_geom_real",
            "geom",
            postgresql_using="gist",
            postgresql_where=text("source_type <> 'DEMO_SIMULATION' AND deleted_at IS NULL"),
        ),
        Index("ix_obs_observed_at", "observed_at"),
        Index("ix_obs_verification_status", "verification_status"),
        Index("ix_obs_source_type", "source_type"),
        Index("ix_obs_crop_id", "crop_id"),
        Index("ix_obs_field_id", "field_id"),
        Index("ix_obs_farmer_id", "farmer_id"),
        Index("ix_obs_district_code", "district_code"),
        Index("ix_obs_district_observed_at", "district_code", "observed_at"),
        Index("ix_obs_status_verif", "status", "verification_status"),
        Index("ix_obs_parent", "parent_observation_id"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Observation {self.id} {self.verification_status} src={self.source_type}>"


class ObservationImage(Base, TimestampMixin):
    """Image metadata only.

    Binary image data is NOT stored in the database (TRD 14.4) - only the object-store
    key, the checksum and the metadata needed for validation and provenance.
    """

    __tablename__ = "observation_images"

    id: Mapped[uuid.UUID] = uuid_pk()
    observation_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("observations.id", ondelete="CASCADE"), nullable=False
    )
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    thumbnail_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mime_type: Mapped[str] = mapped_column(String(50), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    width_px: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height_px: Mapped[int | None] = mapped_column(Integer, nullable=True)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    exif_captured_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    exif_latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    exif_longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    quality_flags: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )

    observation = relationship("Observation", back_populates="images")

    __table_args__ = (
        CheckConstraint("size_bytes > 0", name="ck_obs_images_size_positive"),
        Index("ix_obs_images_observation_id", "observation_id"),
        Index("ix_obs_images_checksum", "checksum_sha256"),
    )
