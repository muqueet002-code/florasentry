"""Field endpoints (TRD 12.4).

Implemented in Phase 1 because fields are the spatial anchor of every later module -
this is also what proves the PostGIS, provenance and ownership-scoping foundations
actually work end to end rather than merely being declared.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, get_current_user, get_db, require_permission
from app.core.rbac import Permission
from app.core.responses import paginated, success
from app.models.farmer import Field
from app.repositories.field_repository import FieldRepository
from app.schemas.field import FieldCreate, FieldUpdate
from app.services.field_service import FieldService

router = APIRouter(prefix="/fields", tags=["fields"])


def _serialise(field: Field, repo: FieldRepository) -> dict[str, object]:
    lat, lon, boundary = repo.read_geometry(field)
    return {
        "id": str(field.id),
        "farmer_id": str(field.farmer_id),
        "name": field.name,
        "latitude": lat,
        "longitude": lon,
        "boundary": boundary,
        "area_ha": float(field.area_ha) if field.area_ha is not None else None,
        "soil_type": field.soil_type,
        "irrigation_type": field.irrigation_type,
        "district_code": field.district_code,
        "current_crop_id": str(field.current_crop_id) if field.current_crop_id else None,
        "current_variety_id": (str(field.current_variety_id) if field.current_variety_id else None),
        "sowing_date": field.sowing_date.isoformat() if field.sowing_date else None,
        # Provenance is a required part of the payload, never optional (TRD 10.2).
        "provenance": {
            "source_type": field.source_type,
            "created_by": str(field.created_by),
            "created_at": field.created_at.isoformat(),
            "original_source_ref": field.original_source_ref,
        },
    }


@router.post("", status_code=status.HTTP_201_CREATED, summary="Create a field")
def create_field(
    payload: FieldCreate,
    current: CurrentUser = Depends(require_permission(Permission.MANAGE_OWN_FIELDS)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    field = FieldService(db).create_field(user=current, payload=payload)
    db.flush()
    return success(_serialise(field, FieldRepository(db)))


@router.get("", summary="List fields visible to the caller")
def list_fields(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """Scope is applied in the repository per TRD 13.6, not here."""
    fields, total = FieldService(db).list_fields(user=current, page=page, page_size=page_size)
    repo = FieldRepository(db)
    return paginated(
        [_serialise(f, repo) for f in fields],
        page=page,
        page_size=page_size,
        total_items=total,
    )


@router.get("/{field_id}", summary="Field detail")
def get_field(
    field_id: uuid.UUID,
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    field = FieldService(db).get_field(user=current, field_id=field_id)
    return success(_serialise(field, FieldRepository(db)))


@router.patch("/{field_id}", summary="Update a field")
def update_field(
    field_id: uuid.UUID,
    payload: FieldUpdate,
    current: CurrentUser = Depends(require_permission(Permission.MANAGE_OWN_FIELDS)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    field = FieldService(db).update_field(user=current, field_id=field_id, payload=payload)
    return success(_serialise(field, FieldRepository(db)))


@router.delete("/{field_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Soft-delete")
def delete_field(
    field_id: uuid.UUID,
    current: CurrentUser = Depends(require_permission(Permission.MANAGE_OWN_FIELDS)),
    db: Session = Depends(get_db),
) -> Response:
    FieldService(db).delete_field(user=current, field_id=field_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
