"""GIS map and hotspot tests (Phase 4).

Reuses the observation-creation helper and fixtures from the Phase 2/3 pipeline test
rather than duplicating the multipart-upload plumbing.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.rbac import UserRole
from app.models.catalog import DiseasePestCatalog
from tests.integration.test_observation_pipeline import LAT, LON, create_observation

pytestmark = pytest.mark.integration

# A point still inside the app's operating bbox (observation creation rejects
# anything outside it) but far from LAT/LON - the opposite corner of the
# Maharashtra window used throughout these tests.
FAR_LAT, FAR_LON = 21.0, 79.5

# A coordinate distinct from LAT/LON, used only for the clustering tests below. The
# shared dev database this suite runs against accumulates real rows near LAT/LON from
# manual/live testing across sessions; clustering and classification assertions count
# and aggregate ALL nearby observations, so they need an area with no ambient data
# rather than the "any extra row nearby is fine" tolerance plain bbox/nearby tests have.
CLUSTER_LAT, CLUSTER_LON = 20.111111, 76.222222

# Small offsets (~tens of metres) so multiple observations cluster within the default
# HOTSPOT_RADIUS_M without leaving the bbox used by the queries below.
NEAR_OFFSETS = [(0.0, 0.0), (0.0005, 0.0), (0.0, 0.0005), (0.0007, 0.0007)]


def ensure_agent(db: Session, code: str, kind: str = "DISEASE") -> DiseasePestCatalog:
    existing = db.query(DiseasePestCatalog).filter(DiseasePestCatalog.code == code).first()
    if existing:
        return existing
    agent = DiseasePestCatalog(
        code=code, kind=kind, name_en=code.title(), name_hi=code.title(), name_mr=code.title()
    )
    db.add(agent)
    db.flush()
    return agent


@pytest.fixture
def farmer(db_session: Session, make_user, auth_headers):
    user = make_user(UserRole.FARMER)
    return user, auth_headers(user)


@pytest.fixture
def official_headers(db_session: Session, make_user, auth_headers):
    return auth_headers(make_user(UserRole.OFFICIAL))


class TestBboxQuery:
    def test_observation_within_bbox_is_returned(
        self, db_client: TestClient, farmer, official_headers
    ) -> None:
        _, headers = farmer
        status_code, body = create_observation(db_client, headers)
        assert status_code == 201
        obs_id = body["data"]["id"]

        bbox = "72.6,15.6,80.9,22.1"  # matches the app's default operating area
        response = db_client.get(
            "/api/v1/gis/observations", params={"bbox": bbox}, headers=official_headers
        )
        assert response.status_code == 200
        features = response.json()["data"]["features"]
        assert any(f["properties"]["id"] == obs_id for f in features)

    def test_observation_outside_bbox_is_excluded(
        self, db_client: TestClient, farmer, official_headers
    ) -> None:
        _, headers = farmer
        status_code, body = create_observation(
            db_client, headers, latitude=FAR_LAT, longitude=FAR_LON
        )
        assert status_code == 201
        obs_id = body["data"]["id"]

        # A small bbox around LAT/LON that does not reach FAR_LAT/FAR_LON.
        bbox = "75.0,19.0,76.5,20.5"
        response = db_client.get(
            "/api/v1/gis/observations", params={"bbox": bbox}, headers=official_headers
        )
        features = response.json()["data"]["features"]
        assert all(f["properties"]["id"] != obs_id for f in features)

    def test_feature_carries_provenance(
        self, db_client: TestClient, farmer, official_headers
    ) -> None:
        _, headers = farmer
        _, body = create_observation(db_client, headers)
        response = db_client.get(
            "/api/v1/gis/observations",
            params={"bbox": "72.6,15.6,80.9,22.1"},
            headers=official_headers,
        )
        features = response.json()["data"]["features"]
        assert features, "expected at least one feature"
        props = features[0]["properties"]
        assert props["source_type"] == "FIELD_OBSERVATION"
        assert "verification_status" in props

    def test_invalid_bbox_is_rejected(self, db_client: TestClient, official_headers) -> None:
        response = db_client.get(
            "/api/v1/gis/observations", params={"bbox": "not,a,bbox"}, headers=official_headers
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "BBOX_INVALID"

    def test_demo_data_excluded_by_default(
        self, db_client: TestClient, db_session: Session, farmer, official_headers
    ) -> None:
        _, headers = farmer
        status_code, body = create_observation(db_client, headers)
        assert status_code == 201
        obs_id = uuid.UUID(body["data"]["id"])

        from app.models.observation import Observation

        db_session.query(Observation).filter(Observation.id == obs_id).update(
            {"source_type": "DEMO_SIMULATION"}
        )
        db_session.flush()

        default_response = db_client.get(
            "/api/v1/gis/observations",
            params={"bbox": "72.6,15.6,80.9,22.1"},
            headers=official_headers,
        )
        default_ids = {f["properties"]["id"] for f in default_response.json()["data"]["features"]}
        assert str(obs_id) not in default_ids

        included_response = db_client.get(
            "/api/v1/gis/observations",
            params={"bbox": "72.6,15.6,80.9,22.1", "include_demo": "true"},
            headers=official_headers,
        )
        included_ids = {f["properties"]["id"] for f in included_response.json()["data"]["features"]}
        assert str(obs_id) in included_ids


class TestNearbyQuery:
    def test_nearby_finds_a_close_observation(
        self, db_client: TestClient, farmer, official_headers
    ) -> None:
        _, headers = farmer
        create_observation(db_client, headers)

        response = db_client.get(
            "/api/v1/gis/nearby",
            params={"lat": LAT, "lon": LON, "radius_m": 5000},
            headers=official_headers,
        )
        assert response.status_code == 200
        assert response.json()["data"]["features"]

    def test_nearby_excludes_a_far_observation(
        self, db_client: TestClient, farmer, official_headers
    ) -> None:
        _, headers = farmer
        status_code, body = create_observation(
            db_client, headers, latitude=FAR_LAT, longitude=FAR_LON
        )
        assert status_code == 201
        far_id = body["data"]["id"]

        response = db_client.get(
            "/api/v1/gis/nearby",
            params={"lat": LAT, "lon": LON, "radius_m": 5000},
            headers=official_headers,
        )
        # Rather than asserting an empty list: the shared dev database this suite runs
        # against may already hold unrelated real rows near LAT/LON from manual
        # testing. The one thing this test can actually guarantee is that the FAR
        # observation it just created does not come back.
        ids = {f["properties"]["id"] for f in response.json()["data"]["features"]}
        assert far_id not in ids


class TestHotspots:
    def _create_cluster(
        self, db_client: TestClient, headers: dict, count: int, *, farmer_id: str
    ) -> list[str]:
        ids = []
        for dlat, dlon in NEAR_OFFSETS[:count]:
            status_code, body = create_observation(
                db_client, headers, latitude=CLUSTER_LAT + dlat, longitude=CLUSTER_LON + dlon
            )
            assert status_code == 201
            ids.append(body["data"]["id"])
        return ids

    def test_no_hotspot_below_min_observations(
        self, db_client: TestClient, farmer, official_headers
    ) -> None:
        user, headers = farmer
        create_observation(db_client, headers)  # a single, isolated observation

        response = db_client.get(
            "/api/v1/gis/hotspots",
            params={"bbox": "72.6,15.6,80.9,22.1", "min_points": 3},
            headers=official_headers,
        )
        assert response.status_code == 200
        clusters = response.json()["data"]
        # ST_ClusterDBSCAN with minpoints=3 never returns a cluster smaller than 3.
        assert not any(len(c["observation_ids"]) < 3 for c in clusters)

    def test_cluster_forms_above_min_observations(
        self, db_client: TestClient, farmer, official_headers
    ) -> None:
        user, headers = farmer
        obs_ids = self._create_cluster(db_client, headers, 4, farmer_id=str(user.id))

        response = db_client.get(
            "/api/v1/gis/hotspots",
            params={"bbox": "72.6,15.6,80.9,22.1", "min_points": 3, "radius_m": 2000},
            headers=official_headers,
        )
        assert response.status_code == 200
        clusters = response.json()["data"]
        matching = [c for c in clusters if set(obs_ids) & set(c["observation_ids"])]
        assert matching, "expected the 4 nearby observations to form a cluster"
        assert matching[0]["observation_count"] >= 3

    def test_all_predicted_cluster_is_a_potential_hotspot(
        self, db_client: TestClient, farmer, official_headers
    ) -> None:
        user, headers = farmer
        self._create_cluster(db_client, headers, 3, farmer_id=str(user.id))

        response = db_client.get(
            "/api/v1/gis/hotspots",
            params={"bbox": "72.6,15.6,80.9,22.1", "min_points": 3, "radius_m": 2000},
            headers=official_headers,
        )
        clusters = response.json()["data"]
        assert clusters, "expected at least one cluster"
        assert clusters[0]["hotspot_type"] == "PREDICTED"
        assert clusters[0]["label"] == "Potential hotspot"
        assert clusters[0]["confirmed_count"] == 0

    def test_fully_confirmed_cluster_is_a_confirmed_hotspot(
        self,
        db_client: TestClient,
        db_session: Session,
        farmer,
        official_headers,
        make_user,
        auth_headers,
    ) -> None:
        user, headers = farmer
        obs_ids = self._create_cluster(db_client, headers, 3, farmer_id=str(user.id))

        agent = ensure_agent(db_session, "HEALTHY", kind="HEALTHY")
        expert_headers = auth_headers(make_user(UserRole.EXTENSION_WORKER))

        for obs_id in obs_ids:
            # Every prediction in this suite resolves to a mapped agent only if the
            # catalog has that code; force a deterministic diagnosis instead so the
            # test does not depend on what the fake AI runner happened to predict.
            from app.models.observation import Observation

            db_session.query(Observation).filter(Observation.id == uuid.UUID(obs_id)).update(
                {"verification_status": "PENDING_REVIEW"}
            )
        db_session.flush()

        for obs_id in obs_ids:
            response = db_client.post(
                f"/api/v1/reviews/{obs_id}/decision",
                headers=expert_headers,
                json={"decision": "CORRECT", "corrected_agent_id": str(agent.id)},
            )
            assert response.status_code == 200, response.text

        response = db_client.get(
            "/api/v1/gis/hotspots",
            params={"bbox": "72.6,15.6,80.9,22.1", "min_points": 3, "radius_m": 2000},
            headers=official_headers,
        )
        clusters = response.json()["data"]
        matching = [c for c in clusters if set(obs_ids) & set(c["observation_ids"])]
        assert matching, "expected the confirmed cluster to be reported"
        assert matching[0]["hotspot_type"] == "CONFIRMED"
        assert matching[0]["label"] == "Confirmed hotspot"
        assert matching[0]["confirmed_count"] == matching[0]["observation_count"]

    def test_hotspot_disclaimer_is_always_present(
        self, db_client: TestClient, farmer, official_headers
    ) -> None:
        user, headers = farmer
        self._create_cluster(db_client, headers, 3, farmer_id=str(user.id))
        response = db_client.get(
            "/api/v1/gis/hotspots",
            params={"bbox": "72.6,15.6,80.9,22.1", "min_points": 3, "radius_m": 2000},
            headers=official_headers,
        )
        clusters = response.json()["data"]
        assert clusters
        assert all(c["disclaimer_key"] == "hotspot.prototype_disclaimer" for c in clusters)

    def test_hotspots_require_permission(self, db_client: TestClient, farmer) -> None:
        _, headers = farmer
        response = db_client.get(
            "/api/v1/gis/hotspots", params={"bbox": "72.6,15.6,80.9,22.1"}, headers=headers
        )
        # FARMER does not hold VIEW_HOTSPOTS.
        assert response.status_code == 403
