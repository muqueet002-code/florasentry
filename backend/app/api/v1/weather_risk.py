"""Weather and risk endpoints (Phase 3)."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, get_current_user, get_db
from app.core.config import settings
from app.core.errors import ExternalServiceError, NotFoundError
from app.core.responses import success
from app.repositories.observation_repository import ObservationRepository
from app.risk.rule_engine import load_ruleset
from app.services.weather_service import WeatherService

router = APIRouter(tags=["weather", "risk"])


def _bounds_check(latitude: float, longitude: float) -> None:
    minx, miny, maxx, maxy = settings.operating_bbox
    if not (minx <= longitude <= maxx and miny <= latitude <= maxy):
        from app.core.errors import ValidationError

        raise ValidationError(
            "Coordinates are outside the configured operating area.",
            code="COORDINATES_OUT_OF_BOUNDS",
            message_key="errors.coordinates_out_of_bounds",
        )


@router.get("/weather/current", summary="Current weather for a coordinate")
def current_weather(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    _: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _bounds_check(lat, lon)
    snapshot = WeatherService(db).get_snapshot(lat, lon, include_forecast=False)

    if not snapshot.available:
        # Explicitly unavailable. No invented values, no zeros.
        raise ExternalServiceError(
            snapshot.unavailable_reason or "Weather is unavailable.",
            code="WEATHER_UNAVAILABLE",
            message_key="errors.weather_unavailable",
        )

    reading = snapshot.reading
    assert reading is not None
    warnings = (
        [{"code": "WEATHER_STALE", "message_key": "warnings.weather_stale"}]
        if snapshot.is_stale
        else None
    )
    return success(
        {
            "provider": snapshot.provider,
            "observed_at": reading.observed_at.isoformat(),
            "temperature_c": reading.temperature_c,
            "humidity_pct": reading.humidity_pct,
            "rainfall_mm": reading.rainfall_mm,
            "wind_speed_ms": reading.wind_speed_ms,
            "pressure_hpa": reading.pressure_hpa,
            "is_stale": snapshot.is_stale,
            "cache_hit": snapshot.cache_hit,
            "fetched_at": snapshot.fetched_at.isoformat() if snapshot.fetched_at else None,
        },
        warnings=warnings,
    )


@router.get("/weather/forecast", summary="Daily forecast for a coordinate")
def weather_forecast(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    _: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _bounds_check(lat, lon)
    snapshot = WeatherService(db).get_snapshot(lat, lon, include_forecast=True)

    if not snapshot.forecast:
        raise ExternalServiceError(
            "Forecast is unavailable.",
            code="WEATHER_UNAVAILABLE",
            message_key="errors.weather_unavailable",
        )

    return success(
        {
            "provider": snapshot.provider,
            "is_stale": snapshot.is_stale,
            "days": [
                {
                    "date": reading.observed_at.date().isoformat(),
                    "temperature_c": reading.temperature_c,
                    "humidity_pct": reading.humidity_pct,
                    "rainfall_mm": reading.rainfall_mm,
                    "wind_speed_ms": reading.wind_speed_ms,
                }
                for reading in snapshot.forecast
            ],
        }
    )


class HistoricalNotSupported(ExternalServiceError):
    """501, not 503: the capability is absent by design, so retrying cannot help."""

    status_code = 501
    code = "NOT_IMPLEMENTED"
    message_key = "errors.weather_historical_unsupported"
    retriable = False

    def __init__(self, provider: str) -> None:
        super().__init__(
            f"The configured weather provider '{provider}' does not serve historical data.",
            code="NOT_IMPLEMENTED",
            message_key="errors.weather_historical_unsupported",
            details=[{"provider": provider, "capability": "historical"}],
        )


@router.get("/weather/historical", summary="Historical weather (provider-dependent)")
def weather_historical(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    _: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Answers honestly when the configured provider has no history capability.

    `supports_historical` is a declared provider capability, so this never guesses and
    never synthesises past values.
    """
    provider = WeatherService(db).provider
    if not provider.supports_historical:
        raise HistoricalNotSupported(provider.name)
    # No configured provider currently declares support; when one does, its
    # get_historical() is called here.
    raise HistoricalNotSupported(provider.name)


@router.get("/risk/ruleset", summary="The active risk ruleset (transparency)")
def risk_ruleset(_: CurrentUser = Depends(get_current_user)) -> dict[str, Any]:
    """Exposes the full active configuration so a score can be audited.

    This is the concrete implementation of "explainability over black-box claims".
    """
    ruleset = load_ruleset()
    return success(
        {
            "ruleset_version": ruleset.get("ruleset_version"),
            "method": ruleset.get("method"),
            "disclaimer_key": ruleset.get("disclaimer_key"),
            "levels": ruleset.get("levels"),
            "missing_factor_policy": ruleset.get("missing_factor_policy"),
            "uncertainty": ruleset.get("uncertainty"),
            "factors": {
                name: {"weight": config.get("weight"), "rules": config.get("rules")}
                for name, config in ruleset.get("factors", {}).items()
            },
            "validation_status": "PROTOTYPE_NOT_SCIENTIFICALLY_VALIDATED",
        }
    )


@router.get("/risk/observations/{observation_id}", summary="Risk for an observation")
def observation_risk(
    observation_id: uuid.UUID,
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    repo = ObservationRepository(db)
    if repo.get_for_user(observation_id, current) is None:
        raise NotFoundError("Observation")

    risk = repo.latest_risk(observation_id)
    if risk is None:
        raise NotFoundError("Risk assessment")

    from app.api.v1.observations import _risk_out

    return success(_risk_out(risk))
