"""Weather provider interface (Phase 3).

`supports_historical` is a DECLARED capability, not an assumption: a provider that
cannot serve history says so, and the caller reports that rather than fabricating past
values.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class WeatherReading:
    """One normalised weather sample.

    Every field is optional: a provider that omits a variable yields None, which the
    risk engine records as a missing factor. None never becomes zero.
    """

    observed_at: datetime
    temperature_c: float | None = None
    humidity_pct: float | None = None
    rainfall_mm: float | None = None
    wind_speed_ms: float | None = None
    wind_direction_deg: float | None = None
    pressure_hpa: float | None = None
    raw: dict[str, Any] | None = None


class WeatherUnavailable(Exception):
    """The provider could not be reached or returned an unusable response."""


class WeatherNotSupported(Exception):
    """The configured provider does not offer this capability."""


class WeatherProvider(ABC):
    name: str
    supports_historical: bool = False

    @abstractmethod
    def get_current(self, latitude: float, longitude: float) -> WeatherReading:
        """Current conditions. Raises WeatherUnavailable on failure."""

    @abstractmethod
    def get_forecast(self, latitude: float, longitude: float, days: int) -> list[WeatherReading]:
        """Daily forecast. Raises WeatherUnavailable on failure."""

    def get_historical(
        self, latitude: float, longitude: float, start: datetime, end: datetime
    ) -> list[WeatherReading]:
        raise WeatherNotSupported(f"{self.name} does not support historical weather")


class NullWeatherProvider(WeatherProvider):
    """Explicitly disabled weather.

    Selected with WEATHER_PROVIDER=none. Every call reports unavailability, so risk is
    computed without weather and says so - it never silently invents values.
    """

    name = "none"
    supports_historical = False

    def get_current(self, latitude: float, longitude: float) -> WeatherReading:
        raise WeatherUnavailable("Weather provider is disabled (WEATHER_PROVIDER=none)")

    def get_forecast(self, latitude: float, longitude: float, days: int) -> list[WeatherReading]:
        raise WeatherUnavailable("Weather provider is disabled (WEATHER_PROVIDER=none)")
