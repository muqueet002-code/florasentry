"""Field request/response schemas (TRD 12.4)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GeoJSONPolygon(StrictModel):
    """Minimal GeoJSON Polygon. Structural validation only.

    Geometric validity (self-intersection etc.) is checked by PostGIS via `ST_IsValid`,
    which is the authority - re-implementing that in Python would be duplicated logic
    that could disagree with the database.
    """

    type: Literal["Polygon"]
    coordinates: list[list[tuple[float, float]]]

    @model_validator(mode="after")
    def _validate_ring(self) -> GeoJSONPolygon:
        if not self.coordinates:
            raise ValueError("Polygon must have at least one linear ring")
        ring = self.coordinates[0]
        if len(ring) < 4:
            raise ValueError("A linear ring needs at least 4 positions")
        if ring[0] != ring[-1]:
            raise ValueError("A linear ring must be closed (first position == last)")
        return self


class FieldCreate(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    boundary: GeoJSONPolygon | None = None
    area_ha: Decimal | None = Field(default=None, gt=0, le=100000)
    soil_type: str | None = Field(default=None, max_length=60)
    irrigation_type: str | None = Field(default=None, max_length=60)
    district_code: str | None = Field(default=None, max_length=20)
    current_crop_id: uuid.UUID | None = None
    current_variety_id: uuid.UUID | None = None
    sowing_date: date | None = None


class FieldUpdate(StrictModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    area_ha: Decimal | None = Field(default=None, gt=0, le=100000)
    soil_type: str | None = Field(default=None, max_length=60)
    irrigation_type: str | None = Field(default=None, max_length=60)
    current_crop_id: uuid.UUID | None = None
    current_variety_id: uuid.UUID | None = None
    sowing_date: date | None = None


class ProvenanceOut(BaseModel):
    """Required on every provenance-bearing response (TRD 10.2).

    Declared as a required field so a serialiser cannot omit it by accident.
    """

    source_type: str
    created_by: uuid.UUID | None
    created_at: datetime
    verified_by: uuid.UUID | None = None
    verified_at: datetime | None = None
    model_version: str | None = None
    original_source_ref: str | None = None
    data_source_id: uuid.UUID | None = None

    model_config = ConfigDict(protected_namespaces=())


class FieldOut(BaseModel):
    id: uuid.UUID
    farmer_id: uuid.UUID
    name: str
    latitude: float
    longitude: float
    boundary: dict[str, Any] | None
    area_ha: Decimal | None
    soil_type: str | None
    irrigation_type: str | None
    district_code: str | None
    current_crop_id: uuid.UUID | None
    current_variety_id: uuid.UUID | None
    sowing_date: date | None
    provenance: ProvenanceOut
