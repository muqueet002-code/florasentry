"""Observation request/response schemas (Phase 2 + 3)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ObservationCreate(BaseModel):
    """JSON part of the multipart create request.

    `extra="forbid"`: an unknown field is an error, not silently ignored. In
    particular there is no `verification_status` field - a client can never assert
    that an observation is confirmed.
    """

    model_config = ConfigDict(extra="forbid")

    field_id: uuid.UUID | None = None
    crop_id: uuid.UUID | None = None
    variety_id: uuid.UUID | None = None
    growth_stage_id: uuid.UUID | None = None
    observation_type: Literal["IMAGE", "MANUAL_REPORT"] = "IMAGE"

    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    gps_accuracy_m: float | None = Field(default=None, ge=0, le=100000)
    location_method: Literal["DEVICE_GPS", "MAP_PIN", "FIELD_CENTROID"] = "DEVICE_GPS"

    observed_at: datetime | None = None
    reported_severity: int | None = Field(default=None, ge=1, le=5)
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("observed_at")
    @classmethod
    def _not_in_future(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        from datetime import UTC, timedelta

        now = datetime.now(UTC)
        candidate = value if value.tzinfo else value.replace(tzinfo=UTC)
        # Small allowance for client clock skew; anything beyond that is a bug.
        if candidate > now + timedelta(minutes=10):
            raise ValueError("observed_at cannot be in the future")
        return candidate


class PredictionOut(BaseModel):
    """AI output. Always rendered alongside `verification_status`, never alone."""

    predicted_class: str
    agent_id: uuid.UUID | None
    confidence: float
    is_low_confidence: bool
    top_k: list[dict[str, Any]] | None
    severity_estimate: float | None
    model_version: str
    inference_ms: int | None
    runtime_device: str | None
    created_at: datetime

    model_config = ConfigDict(protected_namespaces=())


class WeatherOut(BaseModel):
    available: bool
    is_stale: bool
    provider: str
    observed_at: datetime | None = None
    temperature_c: float | None = None
    humidity_pct: float | None = None
    rainfall_mm: float | None = None
    wind_speed_ms: float | None = None
    pressure_hpa: float | None = None
    fetched_at: datetime | None = None
    cache_hit: bool = False
    age_hours: float | None = None
    unavailable_reason: str | None = None


class RiskOut(BaseModel):
    risk_score: float
    risk_level: str
    forecast_period_start: datetime
    forecast_period_end: datetime
    contributing_factors: list[dict[str, Any]]
    missing_factors: list[dict[str, Any]]
    explanation_key: str
    explanation_params: dict[str, Any] | None
    uncertainty: float | None
    method: str
    ruleset_version: str
    weather_is_stale: bool
    # Rendered by the UI on every risk display: prototype logic, not validated science.
    disclaimer_key: str = "risk.prototype_disclaimer"
    computed_at: datetime


class ImageOut(BaseModel):
    id: uuid.UUID
    url: str
    thumbnail_url: str | None
    width_px: int | None
    height_px: int | None
    quality_flags: dict[str, Any] | None


class ProvenanceOut(BaseModel):
    source_type: str
    created_by: uuid.UUID | None
    created_at: datetime
    verified_by: uuid.UUID | None = None
    verified_at: datetime | None = None
    model_version: str | None = None

    model_config = ConfigDict(protected_namespaces=())


class ObservationOut(BaseModel):
    """The combined result the frontend renders.

    `prediction` and `verification_status` are separate top-level fields: a client
    cannot obtain a diagnosis without also holding its verification state.
    """

    id: uuid.UUID
    status: str
    verification_status: str
    observation_type: str
    latitude: float
    longitude: float
    gps_accuracy_m: float | None
    observed_at: datetime
    reported_severity: int | None
    notes: str | None
    field_id: uuid.UUID | None
    crop_id: uuid.UUID | None
    variety_id: uuid.UUID | None
    growth_stage_id: uuid.UUID | None
    final_agent_id: uuid.UUID | None

    image: ImageOut | None = None
    prediction: PredictionOut | None = None
    weather: WeatherOut | None = None
    risk: RiskOut | None = None
    processing_errors: dict[str, Any] | None = None
    provenance: ProvenanceOut
