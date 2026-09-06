"""RiskContext and the context engine (Phase 3).

Assembles everything the risk engine needs into one typed, immutable object. Any input
that could not be obtained is recorded in `missing` - it is never defaulted, because a
default would be a claim the system cannot support.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from geoalchemy2 import Geography
from sqlalchemy import cast, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.catalog import Crop, CropVariety, GrowthStage
from app.models.observation import Observation
from app.services.weather_service import WeatherService, WeatherSnapshot


@dataclass(frozen=True)
class AiSignal:
    predicted_class: str
    confidence: float
    is_low_confidence: bool
    agent_id: uuid.UUID | None
    model_version: str


@dataclass(frozen=True)
class NearbyHistory:
    """Counts from a PostGIS radius query, split by verification state.

    Confirmed and predicted are deliberately separate: a cluster of unverified
    predictions must not carry the same weight as confirmed cases.
    """

    confirmed_count: int
    predicted_count: int
    total_count: int
    radius_m: int
    window_days: int


@dataclass(frozen=True)
class RiskContext:
    observation_id: uuid.UUID | None
    field_id: uuid.UUID | None
    latitude: float
    longitude: float
    observed_at: datetime

    ai_signal: AiSignal | None = None
    crop_code: str | None = None
    variety_code: str | None = None
    growth_stage_code: str | None = None
    weather: WeatherSnapshot | None = None
    nearby: NearbyHistory | None = None
    reported_severity: int | None = None

    # [{factor, reason}] for inputs that could not be assembled.
    missing: list[dict[str, str]] = field(default_factory=list)

    @property
    def weather_available(self) -> bool:
        return self.weather is not None and self.weather.available

    @property
    def weather_is_stale(self) -> bool:
        return self.weather is not None and self.weather.is_stale


class ContextEngine:
    """Builds a RiskContext from the database and the weather service."""

    def __init__(self, db: Session, weather_service: WeatherService | None = None) -> None:
        self.db = db
        self.weather = weather_service or WeatherService(db)

    def build(self, observation: Observation, ai_signal: AiSignal | None = None) -> RiskContext:
        missing: list[dict[str, str]] = []
        latitude = float(observation.latitude)
        longitude = float(observation.longitude)

        if ai_signal is None:
            missing.append({"factor": "AI_SIGNAL", "reason": "NO_PREDICTION"})

        crop_code = self._code(Crop, observation.crop_id)
        if crop_code is None:
            missing.append({"factor": "CROP", "reason": "NOT_PROVIDED"})

        variety_code = self._code(CropVariety, observation.variety_id)
        stage_code = self._code(GrowthStage, observation.growth_stage_id)
        if stage_code is None:
            missing.append({"factor": "GROWTH_STAGE", "reason": "NOT_PROVIDED"})

        weather = self.weather.get_snapshot(latitude, longitude)
        if not weather.available:
            missing.append(
                {"factor": "WEATHER", "reason": weather.unavailable_reason or "UNAVAILABLE"}
            )

        nearby = self._nearby_history(observation, latitude, longitude)

        return RiskContext(
            observation_id=observation.id,
            field_id=observation.field_id,
            latitude=latitude,
            longitude=longitude,
            observed_at=observation.observed_at,
            ai_signal=ai_signal,
            crop_code=crop_code,
            variety_code=variety_code,
            growth_stage_code=stage_code,
            weather=weather,
            nearby=nearby,
            reported_severity=observation.reported_severity,
            missing=missing,
        )

    def _code(self, model: type, row_id: uuid.UUID | None) -> str | None:
        if row_id is None:
            return None
        row = self.db.get(model, row_id)
        return getattr(row, "code", None) if row else None

    def _nearby_history(
        self, observation: Observation, latitude: float, longitude: float
    ) -> NearbyHistory:
        """PostGIS radius query, excluding this observation and any demo data.

        Demo rows are excluded so simulated points can never inflate a real
        observation's risk score.
        """
        radius = settings.RISK_NEARBY_RADIUS_M
        window = settings.RISK_NEARBY_WINDOW_DAYS
        since = datetime.now(UTC) - timedelta(days=window)
        point = func.ST_SetSRID(func.ST_MakePoint(longitude, latitude), 4326)

        rows = self.db.execute(
            select(Observation.verification_status, func.count())
            .where(
                # Cast to geography so the radius is real metres, not degrees.
                func.ST_DWithin(
                    cast(Observation.geom, Geography),
                    cast(point, Geography),
                    radius,
                ),
                Observation.id != observation.id,
                Observation.observed_at >= since,
                Observation.deleted_at.is_(None),
                Observation.source_type != "DEMO_SIMULATION",
            )
            .group_by(Observation.verification_status)
        ).all()

        counts = {status: int(count) for status, count in rows}
        confirmed = counts.get("CONFIRMED", 0) + counts.get("CORRECTED", 0)
        predicted = counts.get("PREDICTED", 0) + counts.get("PENDING_REVIEW", 0)

        return NearbyHistory(
            confirmed_count=confirmed,
            predicted_count=predicted,
            total_count=sum(counts.values()),
            radius_m=radius,
            window_days=window,
        )
