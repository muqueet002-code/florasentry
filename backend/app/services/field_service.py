"""Field business logic (TRD 5.3).

Validation performed here:
  - coordinates inside the configured operating bounding box
  - null-island (0,0) rejection
  - crop/variety consistency
  - per-farmer unique field name
Geometric validity of a boundary polygon is enforced by the PostGIS check constraints
on the table, which are the authority.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser
from app.core.config import settings
from app.core.errors import (
    ConflictError,
    NotFoundError,
    OwnershipError,
    ValidationError,
)
from app.core.rbac import UserRole
from app.models.catalog import CropVariety
from app.models.farmer import Field
from app.repositories.field_repository import FieldRepository
from app.repositories.user_repository import UserRepository
from app.services import audit_service as audit_actions
from app.services.audit_service import AuditService


class FieldService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.fields = FieldRepository(db)
        self.users = UserRepository(db)
        self.audit = AuditService(db)

    # ---- validation ----

    def _validate_coordinates(self, latitude: float, longitude: float) -> None:
        if latitude == 0 and longitude == 0:
            # Null island: almost always a device or client bug, never a real field.
            raise ValidationError(
                "Coordinates (0, 0) are not a valid field location.",
                code="COORDINATES_OUT_OF_BOUNDS",
                message_key="errors.coordinates_null_island",
                details=[{"field": "latitude", "issue": "null_island"}],
            )
        minx, miny, maxx, maxy = settings.operating_bbox
        if not (minx <= longitude <= maxx and miny <= latitude <= maxy):
            raise ValidationError(
                "Coordinates are outside the configured operating area.",
                code="COORDINATES_OUT_OF_BOUNDS",
                message_key="errors.coordinates_out_of_bounds",
                details=[
                    {
                        "field": "latitude,longitude",
                        "issue": "outside_operating_bbox",
                        "operating_bbox": settings.GIS_OPERATING_BBOX,
                    }
                ],
            )

    def _validate_crop_context(
        self, crop_id: uuid.UUID | None, variety_id: uuid.UUID | None
    ) -> None:
        if variety_id is None:
            return
        variety = self.db.get(CropVariety, variety_id)
        if variety is None:
            raise NotFoundError("Crop variety")
        if crop_id is None or variety.crop_id != crop_id:
            raise ValidationError(
                "The selected variety does not belong to the selected crop.",
                code="CROP_CONTEXT_MISMATCH",
                message_key="errors.crop_context_mismatch",
                details=[{"field": "current_variety_id", "issue": "crop_mismatch"}],
            )

    def _resolve_farmer_id(self, user: CurrentUser) -> uuid.UUID:
        if user.farmer_id:
            return user.farmer_id
        raise ValidationError(
            "This account has no farmer profile, so it cannot own a field.",
            code="NO_FARMER_PROFILE",
            message_key="errors.no_farmer_profile",
        )

    # ---- commands ----

    def create_field(self, *, user: CurrentUser, payload: Any) -> Field:
        self._validate_coordinates(payload.latitude, payload.longitude)
        self._validate_crop_context(payload.current_crop_id, payload.current_variety_id)

        farmer_id = self._resolve_farmer_id(user)
        if self.fields.name_taken(farmer_id, payload.name):
            raise ConflictError(
                "You already have a field with this name.",
                code="DUPLICATE_FIELD_NAME",
                message_key="errors.duplicate_field_name",
                details=[{"field": "name", "issue": "already_exists"}],
            )

        values: dict[str, Any] = {
            "farmer_id": farmer_id,
            "name": payload.name,
            "centroid": FieldRepository.point_wkt(payload.latitude, payload.longitude),
            "area_ha": payload.area_ha,
            "soil_type": payload.soil_type,
            "irrigation_type": payload.irrigation_type,
            "district_code": payload.district_code,
            "current_crop_id": payload.current_crop_id,
            "current_variety_id": payload.current_variety_id,
            "sowing_date": payload.sowing_date,
            "created_by": user.id,
            # A field created through the authenticated API is real, not simulated.
            # The demo seeder is the only writer permitted to set DEMO_SIMULATION.
            "source_type": "FIELD_OBSERVATION",
        }
        if payload.boundary is not None:
            values["boundary"] = FieldRepository.polygon_from_geojson(payload.boundary.model_dump())

        try:
            field = self.fields.create(**values)
        except IntegrityError as exc:
            self.db.rollback()
            # The PostGIS check constraints are the authority on geometry validity.
            message = str(exc.orig)
            if "ck_fields_boundary_valid" in message:
                raise ValidationError(
                    "The supplied boundary polygon is not a valid geometry.",
                    code="GEOMETRY_INVALID",
                    message_key="errors.geometry_invalid",
                    details=[{"field": "boundary", "issue": "invalid_polygon"}],
                ) from exc
            if "ck_fields_centroid_in_boundary" in message:
                raise ValidationError(
                    "The field location must lie inside the supplied boundary.",
                    code="GEOMETRY_INVALID",
                    message_key="errors.centroid_outside_boundary",
                    details=[{"field": "boundary", "issue": "centroid_outside"}],
                ) from exc
            raise

        self.audit.record(
            action=audit_actions.ACTION_FIELD_CREATED,
            entity_type="field",
            entity_id=field.id,
            actor_user_id=user.id,
            actor_role=user.role.value,
            after_state={"name": field.name, "source_type": field.source_type},
        )
        return field

    def get_field(self, *, user: CurrentUser, field_id: uuid.UUID) -> Field:
        field = self.fields.get_for_user(field_id, user)
        if field is None:
            # Distinguish "does not exist" from "not yours" only for admins; for
            # everyone else both are 404, so IDs cannot be probed.
            raise NotFoundError("Field")
        return field

    def list_fields(
        self, *, user: CurrentUser, page: int, page_size: int
    ) -> tuple[list[Field], int]:
        return self.fields.list_for_user(user, limit=page_size, offset=(page - 1) * page_size)

    def update_field(self, *, user: CurrentUser, field_id: uuid.UUID, payload: Any) -> Field:
        field = self.get_field(user=user, field_id=field_id)
        self._assert_can_modify(user, field)

        changes = payload.model_dump(exclude_unset=True)
        if "current_crop_id" in changes or "current_variety_id" in changes:
            self._validate_crop_context(
                changes.get("current_crop_id", field.current_crop_id),
                changes.get("current_variety_id", field.current_variety_id),
            )
        if (
            "name" in changes
            and changes["name"] != field.name
            and self.fields.name_taken(field.farmer_id, changes["name"])
        ):
            raise ConflictError(
                "You already have a field with this name.",
                code="DUPLICATE_FIELD_NAME",
                message_key="errors.duplicate_field_name",
            )

        before = {"name": field.name, "soil_type": field.soil_type}
        for key, value in changes.items():
            setattr(field, key, value)
        self.db.flush()

        self.audit.record(
            action=audit_actions.ACTION_FIELD_UPDATED,
            entity_type="field",
            entity_id=field.id,
            actor_user_id=user.id,
            actor_role=user.role.value,
            before_state=before,
            after_state=changes,
        )
        return field

    def delete_field(self, *, user: CurrentUser, field_id: uuid.UUID) -> None:
        field = self.get_field(user=user, field_id=field_id)
        self._assert_can_modify(user, field)
        self.fields.soft_delete(field)
        self.audit.record(
            action=audit_actions.ACTION_FIELD_DELETED,
            entity_type="field",
            entity_id=field.id,
            actor_user_id=user.id,
            actor_role=user.role.value,
            before_state={"name": field.name},
        )

    @staticmethod
    def _assert_can_modify(user: CurrentUser, field: Field) -> None:
        """Read scope is broader than write scope: officials may read, not modify."""
        if user.role is UserRole.ADMIN:
            return
        if user.farmer_id is not None and field.farmer_id == user.farmer_id:
            return
        if user.role is UserRole.EXTENSION_WORKER:
            return  # may act on behalf of farmers within their district scope
        raise OwnershipError()
