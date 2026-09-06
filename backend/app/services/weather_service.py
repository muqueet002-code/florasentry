"""Weather retrieval with caching and graceful degradation (Phase 3).

Four-tier read, in order:
  1. fresh cache        -> use it
  2. live provider call -> persist, use it
  3. stale cache        -> use it, flagged is_stale=true
  4. nothing            -> return unavailable

Tier 4 returns an explicit "unavailable" result. It never returns zeros, averages or
any other stand-in: a missing value must stay visibly missing all the way to the UI.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.integrations.weather.interface import (
    WeatherProvider,
    WeatherReading,
    WeatherUnavailable,
)
from app.integrations.weather.providers import get_weather_provider
from app.models.weather import WeatherForecast, WeatherObservation

logger = get_logger(__name__)


@dataclass(frozen=True)
class WeatherSnapshot:
    """What the risk engine and the API receive.

    `available=False` means no value could be obtained. `is_stale=True` means the value
    is real but older than the cache TTL - both are surfaced to the user.
    """

    available: bool
    is_stale: bool
    provider: str
    reading: WeatherReading | None = None
    forecast: list[WeatherReading] | None = None
    fetched_at: datetime | None = None
    cache_hit: bool = False
    unavailable_reason: str | None = None

    @property
    def age_hours(self) -> float | None:
        if self.fetched_at is None:
            return None
        return (datetime.now(UTC) - _aware(self.fetched_at)).total_seconds() / 3600


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def grid_cell(latitude: float, longitude: float) -> str:
    """Cache key: coordinates rounded so nearby fields share one provider call."""
    precision = settings.WEATHER_GRID_PRECISION
    return f"{round(latitude, precision)},{round(longitude, precision)}"


def _dec(value: float | None) -> Decimal | None:
    return None if value is None else Decimal(str(round(float(value), 2)))


def _row_to_reading(row: WeatherObservation | WeatherForecast) -> WeatherReading:
    observed = getattr(row, "observed_at", None) or row.forecast_for
    return WeatherReading(
        observed_at=_aware(observed),
        temperature_c=float(row.temperature_c) if row.temperature_c is not None else None,
        humidity_pct=float(row.humidity_pct) if row.humidity_pct is not None else None,
        rainfall_mm=float(row.rainfall_mm) if row.rainfall_mm is not None else None,
        wind_speed_ms=float(row.wind_speed_ms) if row.wind_speed_ms is not None else None,
        wind_direction_deg=(
            float(row.wind_direction_deg) if row.wind_direction_deg is not None else None
        ),
        pressure_hpa=float(row.pressure_hpa) if row.pressure_hpa is not None else None,
    )


class WeatherService:
    def __init__(self, db: Session, provider: WeatherProvider | None = None) -> None:
        self.db = db
        self.provider = provider or get_weather_provider()

    # ---- cache ----

    def _cached_current(self, cell: str, max_age_minutes: int) -> WeatherObservation | None:
        cutoff = datetime.now(UTC) - timedelta(minutes=max_age_minutes)
        return (
            self.db.execute(
                select(WeatherObservation)
                .where(
                    WeatherObservation.provider == self.provider.name,
                    WeatherObservation.grid_cell == cell,
                    WeatherObservation.fetched_at >= cutoff,
                )
                .order_by(WeatherObservation.fetched_at.desc())
                .limit(1)
            )
            .scalars()
            .first()
        )

    def _persist_current(
        self, cell: str, latitude: float, longitude: float, reading: WeatherReading
    ) -> WeatherObservation:
        existing = (
            self.db.execute(
                select(WeatherObservation).where(
                    WeatherObservation.provider == self.provider.name,
                    WeatherObservation.grid_cell == cell,
                    WeatherObservation.observed_at == reading.observed_at,
                )
            )
            .scalars()
            .first()
        )

        now = datetime.now(UTC)
        if existing is not None:
            # Same sample re-fetched: refresh its age rather than violating the
            # (provider, cell, observed_at) uniqueness constraint.
            existing.fetched_at = now
            self.db.flush()
            return existing

        row = WeatherObservation(
            provider=self.provider.name,
            latitude=Decimal(str(round(latitude, 6))),
            longitude=Decimal(str(round(longitude, 6))),
            grid_cell=cell,
            geom=func.ST_SetSRID(func.ST_MakePoint(longitude, latitude), 4326),
            temperature_c=_dec(reading.temperature_c),
            humidity_pct=_dec(reading.humidity_pct),
            rainfall_mm=_dec(reading.rainfall_mm),
            wind_speed_ms=_dec(reading.wind_speed_ms),
            wind_direction_deg=_dec(reading.wind_direction_deg),
            pressure_hpa=_dec(reading.pressure_hpa),
            raw_payload=reading.raw,
            fetched_at=now,
            # Provider data is public data, not a field observation.
            source_type="PUBLIC_DATA",
            observed_at=reading.observed_at,
        )
        self.db.add(row)
        self.db.flush()
        return row

    def _persist_forecast(
        self, cell: str, latitude: float, longitude: float, readings: list[WeatherReading]
    ) -> None:
        now = datetime.now(UTC)
        issued = now.replace(minute=0, second=0, microsecond=0)
        for reading in readings:
            exists = self.db.execute(
                select(WeatherForecast.id).where(
                    WeatherForecast.provider == self.provider.name,
                    WeatherForecast.grid_cell == cell,
                    WeatherForecast.forecast_for == reading.observed_at,
                    WeatherForecast.forecast_issued_at == issued,
                )
            ).first()
            if exists:
                continue
            self.db.add(
                WeatherForecast(
                    provider=self.provider.name,
                    latitude=Decimal(str(round(latitude, 6))),
                    longitude=Decimal(str(round(longitude, 6))),
                    grid_cell=cell,
                    geom=func.ST_SetSRID(func.ST_MakePoint(longitude, latitude), 4326),
                    temperature_c=_dec(reading.temperature_c),
                    humidity_pct=_dec(reading.humidity_pct),
                    rainfall_mm=_dec(reading.rainfall_mm),
                    wind_speed_ms=_dec(reading.wind_speed_ms),
                    pressure_hpa=_dec(reading.pressure_hpa),
                    raw_payload=reading.raw,
                    fetched_at=now,
                    source_type="PUBLIC_DATA",
                    forecast_for=reading.observed_at,
                    forecast_issued_at=issued,
                )
            )
        self.db.flush()

    def _cached_forecast(self, cell: str, max_age_minutes: int) -> list[WeatherForecast]:
        cutoff = datetime.now(UTC) - timedelta(minutes=max_age_minutes)
        return list(
            self.db.execute(
                select(WeatherForecast)
                .where(
                    WeatherForecast.provider == self.provider.name,
                    WeatherForecast.grid_cell == cell,
                    WeatherForecast.fetched_at >= cutoff,
                    WeatherForecast.forecast_for >= datetime.now(UTC) - timedelta(days=1),
                )
                .order_by(WeatherForecast.forecast_for)
            )
            .scalars()
            .all()
        )

    # ---- public API ----

    def get_snapshot(
        self, latitude: float, longitude: float, *, include_forecast: bool = True
    ) -> WeatherSnapshot:
        """Current conditions plus forecast, applying the four-tier degradation."""
        cell = grid_cell(latitude, longitude)

        fresh = self._cached_current(cell, settings.WEATHER_CACHE_TTL_MIN)
        if fresh is not None:
            forecast = self._forecast_with_cache(cell, latitude, longitude, include_forecast)
            return WeatherSnapshot(
                available=True,
                is_stale=False,
                provider=self.provider.name,
                reading=_row_to_reading(fresh),
                forecast=forecast,
                fetched_at=_aware(fresh.fetched_at),
                cache_hit=True,
            )

        try:
            reading = self.provider.get_current(latitude, longitude)
            row = self._persist_current(cell, latitude, longitude, reading)
            forecast = self._forecast_with_cache(cell, latitude, longitude, include_forecast)
            return WeatherSnapshot(
                available=True,
                is_stale=False,
                provider=self.provider.name,
                reading=_row_to_reading(row),
                forecast=forecast,
                fetched_at=_aware(row.fetched_at),
                cache_hit=False,
            )
        except WeatherUnavailable as exc:
            logger.warning(
                "weather_provider_unavailable",
                extra={"provider": self.provider.name, "reason": str(exc)},
            )

        # Provider down: fall back to a stale-but-real cached value, clearly flagged.
        stale = self._cached_current(cell, settings.WEATHER_STALE_MAX_HOURS * 60)
        if stale is not None:
            return WeatherSnapshot(
                available=True,
                is_stale=True,
                provider=self.provider.name,
                reading=_row_to_reading(stale),
                forecast=[
                    _row_to_reading(f)
                    for f in self._cached_forecast(cell, settings.WEATHER_STALE_MAX_HOURS * 60)
                ],
                fetched_at=_aware(stale.fetched_at),
                cache_hit=True,
            )

        return WeatherSnapshot(
            available=False,
            is_stale=False,
            provider=self.provider.name,
            unavailable_reason="No live response and no cached weather within the stale window.",
        )

    def _forecast_with_cache(
        self, cell: str, latitude: float, longitude: float, include: bool
    ) -> list[WeatherReading] | None:
        if not include:
            return None

        cached = self._cached_forecast(cell, settings.WEATHER_FORECAST_TTL_MIN)
        if cached:
            return [_row_to_reading(row) for row in cached]

        try:
            readings = self.provider.get_forecast(
                latitude, longitude, settings.WEATHER_FORECAST_DAYS
            )
        except WeatherUnavailable:
            # A missing forecast must not fail the whole snapshot: current conditions
            # are still useful, and the risk engine records the gap.
            stale = self._cached_forecast(cell, settings.WEATHER_STALE_MAX_HOURS * 60)
            return [_row_to_reading(row) for row in stale] if stale else None

        self._persist_forecast(cell, latitude, longitude, readings)
        return readings
