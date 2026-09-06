"""Weather cache models (Phase 3).

Two tables rather than one: an observation and a forecast have different natural keys
and different invalidation rules. Both are a CACHE of what a provider returned - the
provider is the source of truth, and `fetched_at` plus `is_stale` on read make the age
of any value visible rather than implied.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from geoalchemy2 import Geometry
from sqlalchemy import (
    DateTime,
    Index,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, source_type_enum, uuid_pk


class _WeatherColumns:
    """Columns shared by observed and forecast weather."""

    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    latitude: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)
    longitude: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)
    # Rounded-coordinate cache key, e.g. "19.75,75.71".
    grid_cell: Mapped[str] = mapped_column(String(40), nullable=False)
    geom: Mapped[object] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=False), nullable=False
    )

    temperature_c: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    humidity_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    rainfall_mm: Mapped[Decimal | None] = mapped_column(Numeric(7, 2), nullable=True)
    wind_speed_ms: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    wind_direction_deg: Mapped[Decimal | None] = mapped_column(Numeric(5, 1), nullable=True)
    pressure_hpa: Mapped[Decimal | None] = mapped_column(Numeric(7, 2), nullable=True)

    # The provider's untouched response, so a value can always be traced back.
    raw_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_type: Mapped[str] = mapped_column(source_type_enum, nullable=False)


class WeatherObservation(Base, TimestampMixin, _WeatherColumns):
    __tablename__ = "weather_observations"

    id: Mapped[uuid.UUID] = uuid_pk()
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("provider", "grid_cell", "observed_at", name="uq_weather_obs_cell_time"),
        Index("ix_weather_obs_cell_time", "grid_cell", "observed_at"),
        Index("gix_weather_obs_geom", "geom", postgresql_using="gist"),
    )


class WeatherForecast(Base, TimestampMixin, _WeatherColumns):
    __tablename__ = "weather_forecasts"

    id: Mapped[uuid.UUID] = uuid_pk()
    forecast_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    forecast_issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "provider",
            "grid_cell",
            "forecast_for",
            "forecast_issued_at",
            name="uq_weather_forecast_cell_time",
        ),
        Index("ix_weather_forecast_cell_time", "grid_cell", "forecast_for"),
        Index("gix_weather_forecast_geom", "geom", postgresql_using="gist"),
    )
