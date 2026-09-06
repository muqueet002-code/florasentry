"""Farmer profile and field models (TRD 8.3).

Privacy (TRD 30.1): no Aadhaar, no bank details, no government identity number, no
precise home address. Adding any of those requires an explicit purpose and a schema
change - it must not arrive incidentally.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from geoalchemy2 import Geometry
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import (
    Base,
    ProvenanceMixin,
    SoftDeleteMixin,
    TimestampMixin,
    uuid_pk,
)


class Farmer(Base, TimestampMixin):
    """Agricultural profile attached to a FARMER user.

    Separate from `users` so authentication data and farming data have different
    lifecycles and access rules (TRD 8.3).
    """

    __tablename__ = "farmers"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        unique=True,
        nullable=False,
    )
    village: Mapped[str | None] = mapped_column(String(120), nullable=True)
    taluka: Mapped[str | None] = mapped_column(String(120), nullable=True)
    district_code: Mapped[str | None] = mapped_column(
        String(20), ForeignKey("admin_regions.code", ondelete="SET NULL"), nullable=True
    )
    land_holding_ha: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    primary_crop_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("crops.id", ondelete="SET NULL"), nullable=True
    )
    # Opt-in, revocable consent for research/model-training use of this farmer's
    # images (TRD 30.6). The Phase 2+ training-data quality gate requires it.
    research_consent: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")

    user = relationship("User", back_populates="farmer")
    fields = relationship("Field", back_populates="farmer", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint(
            "land_holding_ha IS NULL OR land_holding_ha >= 0",
            name="ck_farmers_land_holding_non_negative",
        ),
        Index("ix_farmers_district_code", "district_code"),
    )


class Field(Base, TimestampMixin, SoftDeleteMixin, ProvenanceMixin):
    """A farmer's plot: the spatial and contextual anchor of observations."""

    __tablename__ = "fields"

    id: Mapped[uuid.UUID] = uuid_pk()
    farmer_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("farmers.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)

    # SRID 4326 (TRD 9.1). Centroid is always present; boundary is optional.
    centroid: Mapped[object] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=False), nullable=False
    )
    boundary: Mapped[object | None] = mapped_column(
        Geometry(geometry_type="POLYGON", srid=4326, spatial_index=False), nullable=True
    )

    area_ha: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), nullable=True)
    soil_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    irrigation_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    district_code: Mapped[str | None] = mapped_column(
        String(20), ForeignKey("admin_regions.code", ondelete="SET NULL"), nullable=True
    )
    current_crop_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("crops.id", ondelete="SET NULL"), nullable=True
    )
    current_variety_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("crop_varieties.id", ondelete="SET NULL"), nullable=True
    )
    sowing_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )

    farmer = relationship("Farmer", back_populates="fields")
    observations = relationship("Observation", back_populates="field")

    __table_args__ = (
        CheckConstraint("area_ha IS NULL OR area_ha > 0", name="ck_fields_area_positive"),
        CheckConstraint(
            "boundary IS NULL OR ST_IsValid(boundary)", name="ck_fields_boundary_valid"
        ),
        CheckConstraint(
            "boundary IS NULL OR ST_Contains(boundary, centroid)",
            name="ck_fields_centroid_in_boundary",
        ),
        UniqueConstraint("farmer_id", "name", name="uq_fields_farmer_name"),
        Index("ix_fields_farmer_id", "farmer_id"),
        Index("ix_fields_district_code", "district_code"),
        Index("gix_fields_centroid", "centroid", postgresql_using="gist"),
        Index("gix_fields_boundary", "boundary", postgresql_using="gist"),
    )
