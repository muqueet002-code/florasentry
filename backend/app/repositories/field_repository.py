"""Field data access, including all PostGIS geometry handling (TRD 6.2, 9).

Role-based scoping is applied HERE rather than in routers, so a new endpoint inherits
the scoping rule by construction (TRD 13.6).
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser
from app.core.rbac import UserRole
from app.models.farmer import Field


class FieldRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ---- scoping ----

    def _scoped(self, stmt: Select, user: CurrentUser) -> Select:
        """Apply the TRD 13.6 data-scoping rule for the calling principal."""
        stmt = stmt.where(Field.deleted_at.is_(None))
        if user.role is UserRole.ADMIN:
            return stmt
        if user.role is UserRole.FARMER:
            # A farmer with no profile can own no fields; force an empty result.
            return stmt.where(Field.farmer_id == (user.farmer_id or uuid.UUID(int=0)))
        if user.role in (UserRole.EXTENSION_WORKER, UserRole.OFFICIAL):
            # District scope. A NULL district_code on the user means statewide.
            if user.district_code:
                return stmt.where(Field.district_code == user.district_code)
            return stmt
        # LAB_EXPERT and any future role see no fields by default.
        return stmt.where(func.false())

    # ---- reads ----

    def get_for_user(self, field_id: uuid.UUID, user: CurrentUser) -> Field | None:
        stmt = self._scoped(select(Field).where(Field.id == field_id), user)
        return self.db.execute(stmt).scalars().first()

    def list_for_user(
        self, user: CurrentUser, *, limit: int, offset: int
    ) -> tuple[list[Field], int]:
        base = self._scoped(select(Field), user)
        total = self.db.execute(select(func.count()).select_from(base.subquery())).scalar_one()
        rows = list(
            self.db.execute(
                base.order_by(Field.created_at.desc()).limit(limit).offset(offset)
            ).scalars()
        )
        return rows, int(total)

    def name_taken(self, farmer_id: uuid.UUID, name: str) -> bool:
        stmt = select(Field.id).where(
            Field.farmer_id == farmer_id, Field.name == name, Field.deleted_at.is_(None)
        )
        return self.db.execute(stmt).first() is not None

    # ---- geometry helpers ----

    @staticmethod
    def point_wkt(latitude: float, longitude: float) -> Any:
        """SRID 4326 point built in SQL, so the database owns geometry construction."""
        return func.ST_SetSRID(func.ST_MakePoint(longitude, latitude), 4326)

    @staticmethod
    def polygon_from_geojson(geojson: dict[str, Any]) -> Any:
        return func.ST_SetSRID(func.ST_GeomFromGeoJSON(json.dumps(geojson)), 4326)

    def read_geometry(self, field: Field) -> tuple[float, float, dict[str, Any] | None]:
        """Return (latitude, longitude, boundary_geojson) for a stored field."""
        row = self.db.execute(
            select(
                func.ST_Y(Field.centroid),
                func.ST_X(Field.centroid),
                func.ST_AsGeoJSON(Field.boundary),
            ).where(Field.id == field.id)
        ).one()
        lat, lon, boundary_json = row
        return float(lat), float(lon), (json.loads(boundary_json) if boundary_json else None)

    # ---- writes ----

    def create(self, **values: Any) -> Field:
        field = Field(**values)
        self.db.add(field)
        self.db.flush()
        return field

    def soft_delete(self, field: Field) -> None:
        from datetime import datetime

        field.deleted_at = datetime.now(UTC)
        self.db.flush()
