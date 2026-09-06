"""Open-Meteo weather provider (Phase 3).

IMPLEMENTATION DECISION - TRD decision D5 (weather provider) was unresolved. Open-Meteo
is selected as the Phase 3 provider because it is a real, publicly documented, key-less
HTTP API, and its response shape was VERIFIED against the live endpoint rather than
assumed. The interface stays provider-agnostic, so swapping it is one new class plus a
config value.

Before any non-demo deployment the team must confirm Open-Meteo's terms of use and
rate limits for the intended volume, and record it in `data_sources`.

Units are requested explicitly (m/s wind, mm precipitation, UTC) so the stored values
match the column names rather than depending on provider defaults.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.integrations.weather.interface import (
    WeatherProvider,
    WeatherReading,
    WeatherUnavailable,
)

logger = get_logger(__name__)

CURRENT_FIELDS = (
    "temperature_2m,relative_humidity_2m,precipitation,"
    "wind_speed_10m,wind_direction_10m,surface_pressure"
)
DAILY_FIELDS = (
    "temperature_2m_max,temperature_2m_min,precipitation_sum,"
    "relative_humidity_2m_mean,wind_speed_10m_max"
)


class OpenMeteoProvider(WeatherProvider):
    name = "open_meteo"
    # The free forecast endpoint does not serve history; a separate archive API does.
    # Declared false rather than guessed, so /weather/historical answers honestly.
    supports_historical = False

    def __init__(self, base_url: str | None = None, timeout: float | None = None) -> None:
        self.base_url = base_url or settings.WEATHER_BASE_URL
        self.timeout = timeout or settings.WEATHER_TIMEOUT_SEC

    def _request(self, params: dict[str, Any]) -> dict[str, Any]:
        """GET with bounded retries. Any failure raises WeatherUnavailable."""
        last_error: Exception | None = None
        for attempt in range(settings.WEATHER_MAX_RETRIES + 1):
            try:
                response = httpx.get(self.base_url, params=params, timeout=self.timeout)
                response.raise_for_status()
                return response.json()
            except (httpx.HTTPError, ValueError) as exc:
                last_error = exc
                logger.warning(
                    "weather_request_failed",
                    extra={
                        "provider": self.name,
                        "attempt": attempt + 1,
                        "error": type(exc).__name__,
                    },
                )
        raise WeatherUnavailable(
            f"{self.name} unreachable after {settings.WEATHER_MAX_RETRIES + 1} attempts: "
            f"{type(last_error).__name__}"
        )

    @staticmethod
    def _parse_time(value: str) -> datetime:
        # Open-Meteo returns naive ISO timestamps; we request timezone=UTC.
        return datetime.fromisoformat(value).replace(tzinfo=UTC)

    def get_current(self, latitude: float, longitude: float) -> WeatherReading:
        payload = self._request(
            {
                "latitude": latitude,
                "longitude": longitude,
                "current": CURRENT_FIELDS,
                "wind_speed_unit": "ms",
                "timezone": "UTC",
            }
        )
        current = payload.get("current")
        if not isinstance(current, dict) or "time" not in current:
            raise WeatherUnavailable(f"{self.name} returned no current block")

        return WeatherReading(
            observed_at=self._parse_time(current["time"]),
            temperature_c=current.get("temperature_2m"),
            humidity_pct=current.get("relative_humidity_2m"),
            rainfall_mm=current.get("precipitation"),
            wind_speed_ms=current.get("wind_speed_10m"),
            wind_direction_deg=current.get("wind_direction_10m"),
            pressure_hpa=current.get("surface_pressure"),
            raw={"current": current, "current_units": payload.get("current_units")},
        )

    def get_forecast(self, latitude: float, longitude: float, days: int) -> list[WeatherReading]:
        payload = self._request(
            {
                "latitude": latitude,
                "longitude": longitude,
                "daily": DAILY_FIELDS,
                "forecast_days": max(1, min(days, 16)),
                "wind_speed_unit": "ms",
                "timezone": "UTC",
            }
        )
        daily = payload.get("daily")
        if not isinstance(daily, dict) or not daily.get("time"):
            raise WeatherUnavailable(f"{self.name} returned no daily block")

        def at(key: str, index: int) -> float | None:
            values = daily.get(key)
            if isinstance(values, list) and index < len(values):
                return values[index]
            return None

        readings: list[WeatherReading] = []
        for index, day in enumerate(daily["time"]):
            high = at("temperature_2m_max", index)
            low = at("temperature_2m_min", index)
            # Daily mean temperature, when both bounds are present.
            mean_temp = (high + low) / 2 if high is not None and low is not None else high

            readings.append(
                WeatherReading(
                    observed_at=datetime.fromisoformat(f"{day}T00:00:00").replace(tzinfo=UTC),
                    temperature_c=mean_temp,
                    humidity_pct=at("relative_humidity_2m_mean", index),
                    rainfall_mm=at("precipitation_sum", index),
                    wind_speed_ms=at("wind_speed_10m_max", index),
                    raw={
                        "temperature_2m_max": high,
                        "temperature_2m_min": low,
                        "date": day,
                    },
                )
            )
        return readings


def get_weather_provider() -> WeatherProvider:
    """Resolve the provider from configuration, never from the import site."""
    from app.integrations.weather.interface import NullWeatherProvider

    if settings.WEATHER_PROVIDER == "open_meteo":
        return OpenMeteoProvider()
    return NullWeatherProvider()
