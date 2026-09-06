"""Application configuration (TRD 36).

All configuration is environment-driven. The application fails fast on a missing or
unsafe required value rather than starting with a silent, insecure default
(TRD 36.10: "A misconfigured system must not start and pretend to work").
"""

from __future__ import annotations

import sys
from functools import lru_cache
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

AppEnv = Literal["local", "ci", "demo", "production"]

# Value shipped in .env.example. Refusing to boot with it prevents an accidental
# deployment that reuses the published example secret.
EXAMPLE_JWT_SECRET = "change-me-generate-with-openssl-rand-hex-32"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---- Application (TRD 36.1) ----
    APP_ENV: AppEnv = "local"
    APP_NAME: str = "FloraSentry V2"
    APP_VERSION: str = "0.1.0"
    GIT_SHA: str = "unknown"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: Literal["json", "console"] = "json"
    API_BASE_PATH: str = "/api/v1"
    DEFAULT_LANGUAGE: str = "en"
    SUPPORTED_LANGUAGES: str = "en,hi,mr"

    # ---- Database (TRD 36.2) ----
    DATABASE_URL: str = "postgresql+psycopg://florasentry:florasentry@localhost:5432/florasentry"
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10
    DATABASE_POOL_TIMEOUT_SEC: int = 30
    DATABASE_STATEMENT_TIMEOUT_MS: int = 15000
    DATABASE_ECHO: bool = False

    # ---- Authentication (TRD 36.3) ----
    JWT_SECRET: str = EXAMPLE_JWT_SECRET
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TTL_MIN: int = 30
    JWT_REFRESH_TTL_DAYS: int = 14
    PASSWORD_MIN_LENGTH: int = 8
    ARGON2_TIME_COST: int = 2
    ARGON2_MEMORY_COST: int = 65536
    ARGON2_PARALLELISM: int = 2
    CORS_ALLOWED_ORIGINS: str = "http://localhost:5173"

    # ---- GIS (TRD 36.7) ----
    # Operating bounding box. Default covers Maharashtra (the MVP target geography
    # per the PRD). TRD decision D24 - confirm the intended extent before pilot.
    GIS_OPERATING_BBOX: str = "72.6,15.6,80.9,22.1"
    GIS_METRIC_SRID: int = 32643

    # ---- Image handling (Phase 2) ----
    IMAGE_MAX_BYTES: int = 10 * 1024 * 1024
    IMAGE_ALLOWED_MIME: str = "image/jpeg,image/png,image/webp"
    IMAGE_MIN_EDGE_PX: int = 64
    IMAGE_MAX_EDGE_PX: int = 8000
    IMAGE_STORE_MAX_EDGE_PX: int = 2048
    IMAGE_THUMBNAIL_EDGE_PX: int = 320
    IMAGE_DEDUPE_WINDOW_HOURS: int = 24

    # ---- Storage (Phase 2) ----
    STORAGE_BACKEND: Literal["local"] = "local"
    STORAGE_LOCAL_PATH: str = "./var/media"

    # ---- AI inference (Phase 2) ----
    AI_ENABLED: bool = True
    # Directory holding model weights. No weights ship with this repository; when the
    # registry points at a missing artifact the service reports AI_MODEL_UNAVAILABLE
    # rather than substituting anything.
    AI_MODEL_ARTIFACT_DIR: str = "./var/models"
    AI_DEVICE: str = "cpu"
    AI_INFERENCE_TIMEOUT_SEC: int = 30
    AI_MAX_CONCURRENT_INFERENCE: int = 2
    AI_TOP_K: int = 3

    # ---- Weather (Phase 3) ----
    # "open_meteo" is a real, key-less public API (verified). "none" disables weather
    # entirely and every risk assessment then reports WEATHER as a missing factor.
    WEATHER_PROVIDER: Literal["open_meteo", "none"] = "open_meteo"
    WEATHER_BASE_URL: str = "https://api.open-meteo.com/v1/forecast"
    WEATHER_API_KEY: str = ""  # Open-Meteo needs none; other providers would.
    WEATHER_TIMEOUT_SEC: float = 8.0
    WEATHER_MAX_RETRIES: int = 2
    WEATHER_CACHE_TTL_MIN: int = 60
    WEATHER_FORECAST_TTL_MIN: int = 180
    WEATHER_STALE_MAX_HOURS: int = 24
    # Coordinate rounding for the cache key: 2 dp is roughly 1.1 km, so nearby fields
    # share one entry and provider calls scale with area, not with observation count.
    WEATHER_GRID_PRECISION: int = 2
    WEATHER_FORECAST_DAYS: int = 7

    # ---- Risk engine (Phase 3) ----
    RISK_RULESET_PATH: str = "app/risk/rulesets/ruleset_v1.yaml"
    RISK_FORECAST_DAYS: int = 7
    RISK_NEARBY_RADIUS_M: int = 5000
    RISK_NEARBY_WINDOW_DAYS: int = 30

    # ---- GIS layers (Phase 4) ----
    # Every /gis/* endpoint is bounded: a bbox is required, and the result set is
    # capped, so a map view can never trigger an unbounded scan.
    GIS_MAX_FEATURES: int = 2000

    # ---- Hotspot detection (Phase 4) ----
    # Deterministic PostGIS clustering (ST_ClusterDBSCAN), not spatial ML. All
    # thresholds are configurable here rather than hardcoded in the query/service.
    HOTSPOT_RADIUS_M: int = 2000
    HOTSPOT_MIN_OBSERVATIONS: int = 3
    HOTSPOT_WINDOW_DAYS: int = 30

    # ---- Advisory (Phase 6) ----
    ADVISORY_RULESET_PATH: str = "app/advisory/rulesets/advisory_v1.yaml"

    # ---- Follow-up (Phase 7) ----
    # Days until a follow-up is due, by risk level at the time it was scheduled. A
    # higher-risk case gets checked sooner. Configurable, not hardcoded in the service.
    FOLLOWUP_DAYS_HIGH: int = 3
    FOLLOWUP_DAYS_MEDIUM: int = 7
    FOLLOWUP_DAYS_LOW: int = 14
    FOLLOWUP_DAYS_DEFAULT: int = 7  # no risk assessment available yet

    # ---- Later phases ----
    SENSOR_INGEST_ENABLED: bool = False

    @property
    def allowed_image_mimes(self) -> set[str]:
        return {m.strip().lower() for m in self.IMAGE_ALLOWED_MIME.split(",") if m.strip()}

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ALLOWED_ORIGINS.split(",") if o.strip()]

    @property
    def supported_languages(self) -> list[str]:
        return [x.strip() for x in self.SUPPORTED_LANGUAGES.split(",") if x.strip()]

    @property
    def operating_bbox(self) -> tuple[float, float, float, float]:
        parts = [float(x) for x in self.GIS_OPERATING_BBOX.split(",")]
        return parts[0], parts[1], parts[2], parts[3]

    @property
    def is_local(self) -> bool:
        return self.APP_ENV == "local"

    @field_validator("DATABASE_URL")
    @classmethod
    def _normalize_database_url(cls, v: str) -> str:
        """Accept the plain URL Render (and most Postgres hosts) provide.

        Render's connection string uses the `postgresql://` / `postgres://` scheme,
        not SQLAlchemy's psycopg-specific `postgresql+psycopg://`. Rewriting the
        scheme here means the same DATABASE_URL Render shows in its dashboard can be
        pasted in directly, with no manual edit required.
        """
        if v.startswith("postgres://"):
            return "postgresql+psycopg://" + v[len("postgres://") :]
        if v.startswith("postgresql://"):
            return "postgresql+psycopg://" + v[len("postgresql://") :]
        return v

    @field_validator("GIS_OPERATING_BBOX")
    @classmethod
    def _validate_bbox(cls, v: str) -> str:
        parts = v.split(",")
        if len(parts) != 4:
            raise ValueError("GIS_OPERATING_BBOX must be 'minx,miny,maxx,maxy'")
        try:
            minx, miny, maxx, maxy = (float(p) for p in parts)
        except ValueError as exc:
            raise ValueError("GIS_OPERATING_BBOX values must be numeric") from exc
        if not (minx < maxx and miny < maxy):
            raise ValueError("GIS_OPERATING_BBOX must satisfy minx<maxx and miny<maxy")
        if not (-180 <= minx <= 180 and -90 <= miny <= 90):
            raise ValueError("GIS_OPERATING_BBOX is outside valid WGS84 ranges")
        return v

    @model_validator(mode="after")
    def _validate_security(self) -> Settings:
        """Startup validation (TRD 36.10). Unsafe values are permitted only in `local`."""
        if self.APP_ENV != "local":
            if len(self.JWT_SECRET) < 32:
                raise ValueError("JWT_SECRET must be at least 32 characters outside APP_ENV=local")
            if self.JWT_SECRET == EXAMPLE_JWT_SECRET:
                raise ValueError("JWT_SECRET is still the .env.example value - generate a real one")
            if self.DEBUG:
                raise ValueError("DEBUG must be false outside APP_ENV=local")
            if self.DATABASE_ECHO:
                raise ValueError("DATABASE_ECHO must be false outside APP_ENV=local")
        if "*" in self.cors_origins:
            raise ValueError("CORS_ALLOWED_ORIGINS must not contain '*' (TRD 29.6)")
        if self.DEFAULT_LANGUAGE not in self.supported_languages:
            raise ValueError("DEFAULT_LANGUAGE must be one of SUPPORTED_LANGUAGES")
        return self


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton. Aborts startup with a precise message on failure."""
    try:
        return Settings()
    except Exception as exc:  # pragma: no cover - exercised manually via bad .env
        print(f"FATAL: invalid configuration - {exc}", file=sys.stderr)
        raise


settings = get_settings()
