"""Administrative regions (TRD 8.3).

IMPLEMENTATION NOTE - TRD decision D7 (REQUIRES DECISION) is unresolved: no
administrative-boundary dataset has been selected or licence-verified. The table
structure is created here because `users.district_code`, `farmers.district_code`,
`fields.district_code` and `observations.district_code` reference it, but the table
ships EMPTY. No boundary data is invented.

Consequences until D7 is resolved:
  - `geom` is nullable, so placeholder rows (if ever needed) cannot imply a real boundary.
  - Point-in-polygon district resolution is deferred to Phase 4 (GIS).
  - Any row loaded must carry the provenance of its actual source dataset.
"""

from __future__ import annotations

import uuid

from geoalchemy2 import Geometry
from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, ProvenanceMixin, TimestampMixin, uuid_pk


class AdminRegion(Base, TimestampMixin, ProvenanceMixin):
    __tablename__ = "admin_regions"

    id: Mapped[uuid.UUID] = uuid_pk()
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    level: Mapped[str] = mapped_column(String(20), nullable=False)  # STATE / DISTRICT / TALUKA
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("admin_regions.id", ondelete="SET NULL"), nullable=True
    )
    # SRID 4326 throughout (TRD 9.1). Nullable until a verified dataset is loaded.
    geom: Mapped[object | None] = mapped_column(
        Geometry(geometry_type="MULTIPOLYGON", srid=4326, spatial_index=False), nullable=True
    )
    source_reference: Mapped[str | None] = mapped_column(Text, nullable=True)

    children = relationship("AdminRegion", remote_side=[id])

    __table_args__ = (
        Index("ix_admin_regions_level", "level"),
        Index("ix_admin_regions_parent_id", "parent_id"),
        Index("gix_admin_regions_geom", "geom", postgresql_using="gist"),
    )
