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

    # ---- Feature flags for later phases ----
    # Phase 1 ships no model, no weather provider and no sensor ingest.
    AI_ENABLED: bool = False
    WEATHER_PROVIDER: str = "none"
    SENSOR_INGEST_ENABLED: bool = False

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
