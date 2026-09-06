"""Phase 3 schema: weather cache and risk assessments.

Revision ID: 0002_weather_risk
Revises: 0001_initial
"""

from __future__ import annotations

from collections.abc import Sequence

import geoalchemy2
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_weather_risk"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RISK_LEVEL_VALUES = ("LOW", "MEDIUM", "HIGH")


def _source_type() -> postgresql.ENUM:
    return postgresql.ENUM(name="source_type", create_type=False)


def _point() -> geoalchemy2.Geometry:
    return geoalchemy2.Geometry(geometry_type="POINT", srid=4326, spatial_index=False)


def _weather_columns() -> list[sa.Column]:
    return [
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("latitude", sa.Numeric(9, 6), nullable=False),
        sa.Column("longitude", sa.Numeric(9, 6), nullable=False),
        sa.Column("grid_cell", sa.String(40), nullable=False),
        sa.Column("geom", _point(), nullable=False),
        sa.Column("temperature_c", sa.Numeric(6, 2), nullable=True),
        sa.Column("humidity_pct", sa.Numeric(5, 2), nullable=True),
        sa.Column("rainfall_mm", sa.Numeric(7, 2), nullable=True),
        sa.Column("wind_speed_ms", sa.Numeric(6, 2), nullable=True),
        sa.Column("wind_direction_deg", sa.Numeric(5, 1), nullable=True),
        sa.Column("pressure_hpa", sa.Numeric(7, 2), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_type", _source_type(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    ]


def upgrade() -> None:
    postgresql.ENUM(*RISK_LEVEL_VALUES, name="risk_level").create(op.get_bind(), checkfirst=True)

    op.create_table(
        "weather_observations",
        *_weather_columns(),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "grid_cell", "observed_at", name="uq_weather_obs_cell_time"),
    )
    op.create_index("ix_weather_obs_cell_time", "weather_observations", ["grid_cell", "observed_at"])
    op.create_index(
        "gix_weather_obs_geom", "weather_observations", ["geom"], postgresql_using="gist"
    )

    op.create_table(
        "weather_forecasts",
        *_weather_columns(),
        sa.Column("forecast_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("forecast_issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider",
            "grid_cell",
            "forecast_for",
            "forecast_issued_at",
            name="uq_weather_forecast_cell_time",
        ),
    )
    op.create_index(
        "ix_weather_forecast_cell_time", "weather_forecasts", ["grid_cell", "forecast_for"]
    )
    op.create_index(
        "gix_weather_forecast_geom", "weather_forecasts", ["geom"], postgresql_using="gist"
    )

    op.create_table(
        "risk_assessments",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("observation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("field_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("risk_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("risk_level", postgresql.ENUM(name="risk_level", create_type=False),
                  nullable=False),
        sa.Column("forecast_period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("forecast_period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("contributing_factors", postgresql.JSONB(), nullable=False),
        sa.Column("missing_factors", postgresql.JSONB(), nullable=True),
        sa.Column("explanation_key", sa.String(120), nullable=False),
        sa.Column("explanation_params", postgresql.JSONB(), nullable=True),
        sa.Column("uncertainty", sa.Numeric(4, 3), nullable=True),
        sa.Column("method", sa.String(40), nullable=False),
        sa.Column("ruleset_version", sa.String(40), nullable=False),
        sa.Column("weather_is_stale", sa.Boolean(), server_default=sa.text("false"),
                  nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
                  nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("risk_score >= 0 AND risk_score <= 100", name="ck_risk_score_range"),
        sa.CheckConstraint("observation_id IS NOT NULL OR field_id IS NOT NULL",
                           name="ck_risk_target"),
        sa.ForeignKeyConstraint(["observation_id"], ["observations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["field_id"], ["fields.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["agent_id"], ["disease_pest_catalog.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_risk_observation_id", "risk_assessments", ["observation_id"])
    op.create_index("ix_risk_field_computed", "risk_assessments", ["field_id", "computed_at"])
    op.create_index("ix_risk_level", "risk_assessments", ["risk_level"])


def downgrade() -> None:
    op.drop_table("risk_assessments")
    op.drop_table("weather_forecasts")
    op.drop_table("weather_observations")
    postgresql.ENUM(name="risk_level").drop(op.get_bind(), checkfirst=True)
