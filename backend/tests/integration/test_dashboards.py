"""Official dashboard tests (Phase 8) + the Phase 9 end-to-end workflow check.

The dashboard computes nothing new - every assertion here is really checking that an
aggregate query correctly reflects rows the existing observation/AI/risk/review/
follow-up pipelines already wrote, and that RBAC gates the route the same way it gates
every other official-only resource.
"""

from __future__ import annotations

import json
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.ai import inference_service
from app.core.rbac import UserRole
from app.models.observation import Observation
from tests.integration.test_gis import ensure_agent
from tests.integration.test_observation_pipeline import (
    FAKE_RUNNER_PATH,
    FakeRunner,
    create_observation,
    register_model,  # noqa: F401 - used as a fixture
)

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _reset_ai_state():
    FakeRunner.confidence = 0.92
    FakeRunner.should_fail = False
    inference_service.RUNNERS[FAKE_RUNNER_PATH] = FakeRunner
    inference_service.reset_runner_cache()
    yield
    inference_service.reset_runner_cache()


@pytest.fixture
def farmer(db_session: Session, make_user, auth_headers):
    user = make_user(UserRole.FARMER)
    return user, auth_headers(user)


@pytest.fixture
def official_headers(db_session: Session, make_user, auth_headers):
    return auth_headers(make_user(UserRole.OFFICIAL))


@pytest.fixture
def expert_headers(db_session: Session, make_user, auth_headers):
    return auth_headers(make_user(UserRole.EXTENSION_WORKER))


def _get_dashboard(client: TestClient, headers: dict) -> dict:
    response = client.get("/api/v1/dashboards/official", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["data"]


class TestAccessControl:
    def test_official_can_open_the_dashboard(self, db_client: TestClient, official_headers) -> None:
        response = db_client.get("/api/v1/dashboards/official", headers=official_headers)
        assert response.status_code == 200

    def test_farmer_cannot_open_the_dashboard(self, db_client: TestClient, farmer) -> None:
        _, headers = farmer
        response = db_client.get("/api/v1/dashboards/official", headers=headers)
        assert response.status_code == 403

    def test_extension_worker_cannot_open_the_official_dashboard(
        self, db_client: TestClient, expert_headers
    ) -> None:
        """The official dashboard is its own permission - an expert role does not
        implicitly inherit it just because both are 'not a farmer'."""
        response = db_client.get("/api/v1/dashboards/official", headers=expert_headers)
        assert response.status_code == 403

    def test_unauthenticated_request_is_rejected(self, db_client: TestClient) -> None:
        response = db_client.get("/api/v1/dashboards/official")
        assert response.status_code == 401


class TestOverviewReflectsRealData:
    def test_new_observation_increments_total(
        self, db_client: TestClient, farmer, official_headers
    ) -> None:
        before = _get_dashboard(db_client, official_headers)["overview"]["total_observations"]

        _, headers = farmer
        status_code, _ = create_observation(db_client, headers)
        assert status_code == 201

        after = _get_dashboard(db_client, official_headers)["overview"]["total_observations"]
        assert after == before + 1

    def test_ai_unavailable_observation_counts_as_pending_review(
        self, db_client: TestClient, farmer, official_headers
    ) -> None:
        """No model registered in this test -> AI_MODEL_UNAVAILABLE -> PENDING_REVIEW,
        exactly like the farmer-facing pipeline test - the dashboard must count it."""
        before = _get_dashboard(db_client, official_headers)["overview"]["pending_expert_reviews"]

        _, headers = farmer
        status_code, body = create_observation(db_client, headers)
        assert status_code == 201
        assert body["data"]["verification_status"] == "PENDING_REVIEW"

        after = _get_dashboard(db_client, official_headers)["overview"]["pending_expert_reviews"]
        assert after == before + 1

    def test_expert_confirmation_increments_confirmed_cases(
        self,
        db_client: TestClient,
        db_session: Session,
        farmer,
        expert_headers,
        official_headers,
        register_model,  # noqa: F811
    ) -> None:
        ensure_agent(db_session, "HEALTHY", kind="HEALTHY")
        register_model()

        _, farmer_headers = farmer
        status_code, body = create_observation(db_client, farmer_headers)
        assert status_code == 201
        obs_id = body["data"]["id"]
        # Force into the review queue regardless of the confidence gate outcome, same
        # as the review-workflow tests do.
        db_session.query(Observation).filter(Observation.id == uuid.UUID(obs_id)).update(
            {"verification_status": "PENDING_REVIEW"}
        )
        db_session.flush()

        before = _get_dashboard(db_client, official_headers)["overview"]["confirmed_cases"]

        decision = db_client.post(
            f"/api/v1/reviews/{obs_id}/decision",
            headers=expert_headers,
            json={"decision": "CONFIRM"},
        )
        assert decision.status_code == 200

        after = _get_dashboard(db_client, official_headers)["overview"]["confirmed_cases"]
        assert after == before + 1

    def test_dashboard_shape_has_every_required_section(
        self, db_client: TestClient, official_headers
    ) -> None:
        data = _get_dashboard(db_client, official_headers)
        assert set(data["overview"]) >= {
            "total_observations",
            "high_risk_observations",
            "pending_expert_reviews",
            "confirmed_cases",
            "active_hotspots",
            "followups_requiring_attention",
        }
        assert "top_threats" in data["disease_pest_summary"]
        assert "affected_crops" in data["disease_pest_summary"]
        assert "risk_distribution" in data["disease_pest_summary"]
        assert "diagnosis_basis" in data["disease_pest_summary"]
        assert isinstance(data["priority_areas"], list)
        assert set(data["recent_activity"]) == {
            "observations",
            "expert_validations",
            "high_risk_cases",
            "worsening_followups",
        }


class TestDiseasePestSummary:
    def test_resolved_agent_appears_in_top_threats(
        self,
        db_client: TestClient,
        db_session: Session,
        farmer,
        official_headers,
        register_model,  # noqa: F811
    ) -> None:
        ensure_agent(db_session, "HEALTHY", kind="HEALTHY")
        register_model()

        _, headers = farmer
        status_code, _ = create_observation(db_client, headers)
        assert status_code == 201

        data = _get_dashboard(db_client, official_headers)
        codes = [t["agent_code"] for t in data["disease_pest_summary"]["top_threats"]]
        assert "HEALTHY" in codes


class TestRecentActivityAndFollowups:
    def test_new_observation_appears_in_recent_activity(
        self, db_client: TestClient, farmer, official_headers
    ) -> None:
        _, headers = farmer
        status_code, body = create_observation(db_client, headers)
        assert status_code == 201
        obs_id = body["data"]["id"]

        data = _get_dashboard(db_client, official_headers)
        ids = [o["id"] for o in data["recent_activity"]["observations"]]
        assert obs_id in ids

    def test_worsened_followup_is_surfaced_for_attention(
        self, db_client: TestClient, farmer, official_headers
    ) -> None:
        _, headers = farmer
        status_code, body = create_observation(db_client, headers)
        assert status_code == 201
        obs_id = body["data"]["id"]

        before = _get_dashboard(db_client, official_headers)["overview"][
            "followups_requiring_attention"
        ]

        create_resp = db_client.post(
            "/api/v1/followups", headers=headers, json={"observation_id": obs_id}
        )
        assert create_resp.status_code == 201
        followup_id = create_resp.json()["data"]["id"]

        submit_resp = db_client.post(
            f"/api/v1/followups/{followup_id}/submit",
            headers=headers,
            data={"payload": json.dumps({"outcome": "WORSENED", "notes": "getting worse"})},
        )
        assert submit_resp.status_code == 200

        data = _get_dashboard(db_client, official_headers)
        assert data["overview"]["followups_requiring_attention"] == before + 1
        worsening_ids = [
            f["parent_observation_id"] for f in data["recent_activity"]["worsening_followups"]
        ]
        assert obs_id in worsening_ids


class TestDemoDataExclusion:
    """A demo/simulated observation must never appear in the official dashboard's
    real-data views unless `include_demo` is explicitly requested - this is the same
    guarantee the map/hotspot layer already gives, extended to the dashboard's own
    recent-activity and follow-up-attention lists."""

    def test_demo_observation_excluded_from_recent_activity_by_default(
        self, db_client: TestClient, db_session: Session, farmer, official_headers
    ) -> None:
        _, headers = farmer
        status_code, body = create_observation(db_client, headers)
        assert status_code == 201
        obs_id = body["data"]["id"]
        db_session.query(Observation).filter(Observation.id == uuid.UUID(obs_id)).update(
            {"source_type": "DEMO_SIMULATION"}
        )
        db_session.flush()

        default_data = _get_dashboard(db_client, official_headers)
        default_ids = [o["id"] for o in default_data["recent_activity"]["observations"]]
        assert obs_id not in default_ids
        assert default_data["includes_demo_data"] is False

        response = db_client.get(
            "/api/v1/dashboards/official",
            params={"include_demo": "true"},
            headers=official_headers,
        )
        with_demo_ids = [
            o["id"] for o in response.json()["data"]["recent_activity"]["observations"]
        ]
        assert obs_id in with_demo_ids
        assert response.json()["data"]["includes_demo_data"] is True

    def test_demo_followup_excluded_from_attention_count_by_default(
        self, db_client: TestClient, db_session: Session, farmer, official_headers
    ) -> None:
        _, headers = farmer
        status_code, body = create_observation(db_client, headers)
        assert status_code == 201
        obs_id = body["data"]["id"]
        db_session.query(Observation).filter(Observation.id == uuid.UUID(obs_id)).update(
            {"source_type": "DEMO_SIMULATION"}
        )
        db_session.flush()

        # Baselines under each mode separately: this suite runs against a shared dev
        # database that may already carry other WORSENED demo rows (from a manual
        # demo-data seed, say), so "before" must be measured in the SAME mode it will
        # later be compared against, not assumed to be zero or equal across modes.
        before_default = _get_dashboard(db_client, official_headers)["overview"][
            "followups_requiring_attention"
        ]
        before_with_demo = db_client.get(
            "/api/v1/dashboards/official",
            params={"include_demo": "true"},
            headers=official_headers,
        ).json()["data"]["overview"]["followups_requiring_attention"]

        create_resp = db_client.post(
            "/api/v1/followups", headers=headers, json={"observation_id": obs_id}
        )
        assert create_resp.status_code == 201
        followup_id = create_resp.json()["data"]["id"]
        submit_resp = db_client.post(
            f"/api/v1/followups/{followup_id}/submit",
            headers=headers,
            data={"payload": json.dumps({"outcome": "WORSENED", "notes": "demo worsening"})},
        )
        assert submit_resp.status_code == 200

        # Excluded by default.
        default_data = _get_dashboard(db_client, official_headers)
        assert default_data["overview"]["followups_requiring_attention"] == before_default
        assert obs_id not in [
            f["parent_observation_id"]
            for f in default_data["recent_activity"]["worsening_followups"]
        ]

        # Present when explicitly requested.
        response = db_client.get(
            "/api/v1/dashboards/official",
            params={"include_demo": "true"},
            headers=official_headers,
        )
        with_demo = response.json()["data"]
        assert with_demo["overview"]["followups_requiring_attention"] == before_with_demo + 1
        assert obs_id in [
            f["parent_observation_id"] for f in with_demo["recent_activity"]["worsening_followups"]
        ]

    def test_demo_observations_own_followup_history_still_visible(
        self, db_client: TestClient, db_session: Session, farmer
    ) -> None:
        """A single observation's OWN follow-up history must not be hidden just
        because that observation happens to be demo data - `include_demo` only
        governs district-wide listings, never a single-record lookup."""
        _, headers = farmer
        status_code, body = create_observation(db_client, headers)
        assert status_code == 201
        obs_id = body["data"]["id"]
        db_session.query(Observation).filter(Observation.id == uuid.UUID(obs_id)).update(
            {"source_type": "DEMO_SIMULATION"}
        )
        db_session.flush()

        create_resp = db_client.post(
            "/api/v1/followups", headers=headers, json={"observation_id": obs_id}
        )
        assert create_resp.status_code == 201

        listing = db_client.get(
            "/api/v1/followups", params={"observation_id": obs_id}, headers=headers
        )
        assert listing.status_code == 200
        assert listing.json()["meta"]["pagination"]["total_items"] == 1
