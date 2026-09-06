"""Database, PostGIS, constraint and provenance tests (TRD 8, 9, 10).

These require a real PostgreSQL + PostGIS; they skip when none is reachable.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from app.models.catalog import DiseasePestCatalog
from app.models.observation import Observation
from app.models.user import User

pytestmark = pytest.mark.integration


class TestDatabaseFoundation:
    def test_connection_works(self, db_session: Session) -> None:
        assert db_session.execute(text("SELECT 1")).scalar_one() == 1

    def test_postgis_extension_is_available(self, db_session: Session) -> None:
        version = db_session.execute(text("SELECT PostGIS_Lib_Version()")).scalar_one()
        assert version, "PostGIS must be installed - the whole GIS design depends on it"

    def test_migration_has_been_applied(self, db_session: Session) -> None:
        revision = db_session.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        assert revision == "0001_initial"

    def test_all_phase1_tables_exist(self, db_session: Session) -> None:
        expected = {
            "users",
            "refresh_tokens",
            "farmers",
            "fields",
            "admin_regions",
            "crops",
            "crop_varieties",
            "growth_stages",
            "disease_pest_catalog",
            "agent_crops",
            "symptoms",
            "agent_symptoms",
            "observations",
            "observation_images",
            "ai_model_registry",
            "ai_predictions",
            "data_sources",
            "audit_logs",
        }
        rows = (
            db_session.execute(
                text("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
            )
            .scalars()
            .all()
        )
        assert expected <= set(rows)

    def test_geometry_columns_use_srid_4326(self, db_session: Session) -> None:
        """SRID 4326 everywhere (TRD 9.1). A mixed-SRID schema silently breaks queries."""
        rows = db_session.execute(
            text(
                "SELECT f_table_name, f_geometry_column, srid FROM geometry_columns "
                "WHERE f_table_name IN ('fields','observations','admin_regions')"
            )
        ).all()
        assert len(rows) == 4
        for table, column, srid in rows:
            assert srid == 4326, f"{table}.{column} has SRID {srid}, expected 4326"

    def test_spatial_indexes_exist(self, db_session: Session) -> None:
        indexes = (
            db_session.execute(
                text(
                    "SELECT indexname FROM pg_indexes WHERE schemaname='public' "
                    "AND indexdef LIKE '%USING gist%'"
                )
            )
            .scalars()
            .all()
        )
        assert {"gix_observations_geom", "gix_fields_centroid"} <= set(indexes)

    def test_partial_map_indexes_exist(self, db_session: Session) -> None:
        """The two hottest map queries are index-backed from Phase 1 (TRD 9.3)."""
        indexes = (
            db_session.execute(text("SELECT indexname FROM pg_indexes WHERE schemaname='public'"))
            .scalars()
            .all()
        )
        assert {"gix_obs_geom_confirmed", "gix_obs_geom_real"} <= set(indexes)


class TestProvenanceEnforcement:
    """TRD 10.2: provenance is enforced by the database, not by convention."""

    def _user(self, db: Session) -> User:
        user = User(
            full_name="Provenance Tester",
            phone=f"+9198{uuid.uuid4().hex[:8]}",
            password_hash="x",
            role="FARMER",
        )
        db.add(user)
        db.flush()
        return user

    def test_observation_without_source_type_is_rejected(self, db_session: Session) -> None:
        user = self._user(db_session)
        db_session.add(
            Observation(
                reported_by=user.id,
                latitude=19.0,
                longitude=75.0,
                geom=text("ST_SetSRID(ST_MakePoint(75.0,19.0),4326)"),
                source_type=None,
            )
        )
        with pytest.raises((IntegrityError, DBAPIError)):
            db_session.flush()

    def test_observation_with_source_type_is_accepted(self, db_session: Session) -> None:
        user = self._user(db_session)
        observation = Observation(
            reported_by=user.id,
            latitude=19.0,
            longitude=75.0,
            geom=text("ST_SetSRID(ST_MakePoint(75.0,19.0),4326)"),
            source_type="FIELD_OBSERVATION",
        )
        db_session.add(observation)
        db_session.flush()
        assert observation.id is not None
        assert observation.is_demo is False

    def test_demo_observation_is_flagged_as_demo(self, db_session: Session) -> None:
        user = self._user(db_session)
        observation = Observation(
            reported_by=user.id,
            latitude=19.0,
            longitude=75.0,
            geom=text("ST_SetSRID(ST_MakePoint(75.0,19.0),4326)"),
            source_type="DEMO_SIMULATION",
        )
        db_session.add(observation)
        db_session.flush()
        assert observation.is_demo is True, "demo data must be distinguishable from real"


class TestPredictionIsNotADiagnosis:
    """TRD 4.4 / 8.3: the database itself forbids an unverified diagnosis."""

    def _setup(self, db: Session) -> tuple[User, DiseasePestCatalog]:
        user = User(
            full_name="Verification Tester",
            phone=f"+9197{uuid.uuid4().hex[:8]}",
            password_hash="x",
            role="FARMER",
        )
        agent = DiseasePestCatalog(
            code=f"TEST_{uuid.uuid4().hex[:8]}",
            kind="DISEASE",
            name_en="Test agent",
            name_hi="Test agent",
            name_mr="Test agent",
        )
        db.add_all([user, agent])
        db.flush()
        return user, agent

    def _observation(self, user, agent, status: str) -> Observation:
        return Observation(
            reported_by=user.id,
            latitude=19.0,
            longitude=75.0,
            geom=text("ST_SetSRID(ST_MakePoint(75.0,19.0),4326)"),
            source_type="FIELD_OBSERVATION",
            verification_status=status,
            final_agent_id=agent.id,
        )

    @pytest.mark.parametrize("status", ["PREDICTED", "PENDING_REVIEW", "REJECTED"])
    def test_unverified_status_cannot_carry_a_final_agent(
        self, db_session: Session, status: str
    ) -> None:
        user, agent = self._setup(db_session)
        db_session.add(self._observation(user, agent, status))
        with pytest.raises((IntegrityError, DBAPIError)) as exc:
            db_session.flush()
        assert "ck_obs_final_agent_requires_verification" in str(exc.value)

    @pytest.mark.parametrize("status", ["CONFIRMED", "CORRECTED"])
    def test_verified_status_may_carry_a_final_agent(
        self, db_session: Session, status: str
    ) -> None:
        user, agent = self._setup(db_session)
        observation = self._observation(user, agent, status)
        db_session.add(observation)
        db_session.flush()
        assert observation.final_agent_id == agent.id

    def test_status_and_verification_status_are_independent(self, db_session: Session) -> None:
        """Pipeline state must never be collapsed into truth state (TRD 20.2)."""
        user, _ = self._setup(db_session)
        observation = Observation(
            reported_by=user.id,
            latitude=19.0,
            longitude=75.0,
            geom=text("ST_SetSRID(ST_MakePoint(75.0,19.0),4326)"),
            source_type="FIELD_OBSERVATION",
            status="COMPLETED",
            verification_status="PENDING_REVIEW",
        )
        db_session.add(observation)
        db_session.flush()
        assert observation.status == "COMPLETED"
        assert observation.verification_status == "PENDING_REVIEW"


class TestCoordinateConstraints:
    def _user(self, db: Session) -> User:
        user = User(
            full_name="Coord Tester",
            phone=f"+9196{uuid.uuid4().hex[:8]}",
            password_hash="x",
            role="FARMER",
        )
        db.add(user)
        db.flush()
        return user

    @pytest.mark.parametrize("lat,lon", [(91.0, 75.0), (-91.0, 75.0), (19.0, 181.0)])
    def test_out_of_range_coordinates_rejected(
        self, db_session: Session, lat: float, lon: float
    ) -> None:
        user = self._user(db_session)
        db_session.add(
            Observation(
                reported_by=user.id,
                latitude=lat,
                longitude=lon,
                geom=text(f"ST_SetSRID(ST_MakePoint({lon},{lat}),4326)"),
                source_type="FIELD_OBSERVATION",
            )
        )
        with pytest.raises((IntegrityError, DBAPIError)):
            db_session.flush()

    @pytest.mark.parametrize("severity", [0, 6, -1])
    def test_severity_must_be_1_to_5(self, db_session: Session, severity: int) -> None:
        user = self._user(db_session)
        db_session.add(
            Observation(
                reported_by=user.id,
                latitude=19.0,
                longitude=75.0,
                geom=text("ST_SetSRID(ST_MakePoint(75.0,19.0),4326)"),
                source_type="FIELD_OBSERVATION",
                reported_severity=severity,
            )
        )
        with pytest.raises((IntegrityError, DBAPIError)):
            db_session.flush()
