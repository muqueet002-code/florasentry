"""Alembic environment.

The database URL comes from the application settings (i.e. from the environment), never
from alembic.ini, so no credential is committed.

`include_object` filters out PostGIS's own internal tables so autogenerate never
proposes dropping `spatial_ref_sys` or the topology schema.
"""

from __future__ import annotations

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context
from app.core.config import settings

# Importing the models package registers every table on Base.metadata.
from app.models import Base  # noqa: F401

config = context.config
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# PostGIS-managed objects that must never appear in a migration.
POSTGIS_TABLES = {
    "spatial_ref_sys",
    "geography_columns",
    "geometry_columns",
    "raster_columns",
    "raster_overviews",
    "topology",
    "layer",
}


def include_object(obj, name, type_, reflected, compare_to) -> bool:  # type: ignore[no-untyped-def]
    if type_ == "table" and name in POSTGIS_TABLES:
        return False
    # GeoAlchemy2 creates its spatial indexes itself; excluding them here keeps
    # autogenerate from proposing duplicates.
    return not (type_ == "index" and name is not None and name.startswith("idx_") and reflected)


def run_migrations_offline() -> None:
    context.configure(
        url=settings.DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        # The postgis/postgis image installs postgis_tiger_geocoder and appends `tiger`
        # to the database search_path. Without pinning to `public`, reflection sees the
        # geocoder's ~40 tables as unqualified and autogenerate proposes dropping them.
        connection.exec_driver_sql("SET search_path TO public")
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
