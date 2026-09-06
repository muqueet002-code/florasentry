"""Advisory endpoint tests (Phase 6).

Covers: advisory reflects the current diagnosis+risk state, low-confidence/awaiting-
review cases get only generic guidance (never specific treatment), a rejected
observation gets a resubmit prompt, and language selection is honoured.
"""

from __future__ import annotations

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


def _unique_agent(db_session: Session, kind: str):
    """A freshly-coded agent, so a test never depends on what a pre-seeded
    catalog row happens to already have as its `kind`."""
    return ensure_agent(db_session, f"TEST_{kind}_{uuid.uuid4().hex[:8]}", kind=kind)


@pytest.fixture(autouse=True)
def _reset_ai_state():
    FakeRunner.confidence = 0.92
    FakeRunner.should_fail = False
    inference_service.RUNNERS[FAKE_RUNNER_PATH] = FakeRunner
    inference_service.reset_runner_cache()
    yield
    inference_service.reset_runner_cache()


@pytest.fixture
def farmer_headers(db_session: Session, make_user, auth_headers):
    return auth_headers(make_user(UserRole.FARMER))


@pytest.fixture
def expert_headers(db_session: Session, make_user, auth_headers):
    return auth_headers(make_user(UserRole.EXTENSION_WORKER))


def _get_advisory(client: TestClient, obs_id: str, headers: dict, **params):
    return client.get(f"/api/v1/observations/{obs_id}/advisory", headers=headers, params=params)


class TestAdvisoryGeneration:
    def test_high_confidence_prediction_gets_a_full_advisory(
        self,
        db_client: TestClient,
        db_session: Session,
        farmer_headers,
        register_model,  # noqa: F811
    ) -> None:
        ensure_agent(
            db_session, "HEALTHY", kind="HEALTHY"
        )  # code must match FakeRunner's predicted_class
        register_model()  # FakeRunner predicts "HEALTHY" at confidence 0.92 (>= high threshold)

        _, body = create_observation(db_client, farmer_headers)
        obs_id = body["data"]["id"]

        response = _get_advisory(db_client, obs_id, farmer_headers)
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["verification_status"] == "PREDICTED"
        assert data["tier"] == "ai_unconfirmed"
        assert len(data["sections"]) > 0
        assert data["ruleset_version"]
        assert data["disclaimer_key"] == "advisory.prototype_disclaimer"

    def test_advisory_contains_no_pesticide_or_dose_terms(
        self,
        db_client: TestClient,
        db_session: Session,
        farmer_headers,
        register_model,  # noqa: F811
    ) -> None:
        """The ruleset must never surface a chemical name, dose or waiting period."""
        ensure_agent(db_session, "HEALTHY", kind="HEALTHY")
        register_model()
        _, body = create_observation(db_client, farmer_headers)
        obs_id = body["data"]["id"]

        response = _get_advisory(db_client, obs_id, farmer_headers)
        section_keys = " ".join(s["key"] for s in response.json()["data"]["sections"]).lower()
        for banned in ("mg/l", "ml/l", "kg/ha", "ppm", "fungicide-", "insecticide-", "dose"):
            assert banned not in section_keys

    def test_confirmed_diagnosis_yields_confirmed_tier(
        self, db_client: TestClient, db_session: Session, farmer_headers, expert_headers
    ) -> None:
        agent = _unique_agent(db_session, "DISEASE")
        _, body = create_observation(db_client, farmer_headers)
        obs_id = body["data"]["id"]
        obs_uuid = uuid.UUID(obs_id)
        db_session.query(Observation).filter(Observation.id == obs_uuid).update(
            {"verification_status": "PENDING_REVIEW"}
        )
        db_session.flush()

        decision = db_client.post(
            f"/api/v1/reviews/{obs_id}/decision",
            headers=expert_headers,
            json={"decision": "CORRECT", "corrected_agent_id": str(agent.id)},
        )
        assert decision.status_code == 200

        response = _get_advisory(db_client, obs_id, farmer_headers)
        data = response.json()["data"]
        assert data["tier"] == "confirmed"
        assert data["verification_status"] == "CORRECTED"
        assert data["match_basis"] == "CONFIRMED_AGENT"

    def test_rejected_observation_gets_resubmit_guidance_only(
        self, db_client: TestClient, db_session: Session, farmer_headers, expert_headers
    ) -> None:
        _, body = create_observation(db_client, farmer_headers)
        obs_id = body["data"]["id"]
        db_session.query(Observation).filter(Observation.id == uuid.UUID(obs_id)).update(
            {"verification_status": "PENDING_REVIEW"}
        )
        db_session.flush()

        decision = db_client.post(
            f"/api/v1/reviews/{obs_id}/decision",
            headers=expert_headers,
            json={"decision": "REJECT"},
        )
        assert decision.status_code == 200

        response = _get_advisory(db_client, obs_id, farmer_headers)
        data = response.json()["data"]
        assert data["tier"] == "rejected"
        section_names = [s["key"] for s in data["sections"]]
        assert any("resubmit" in s for s in section_names)
        # No IPM/treatment sections leak through for an unsupported observation.
        assert not any("ipm_" in s for s in section_names)


class TestLowConfidenceSafety:
    def test_low_confidence_never_gets_specific_ipm_guidance(
        self,
        db_client: TestClient,
        db_session: Session,
        farmer_headers,
        register_model,  # noqa: F811
    ) -> None:
        """A low-confidence prediction is routed to PENDING_REVIEW by the existing
        confidence gate (Phase 2); the advisory for that tier must stay generic."""
        # agent_kind is irrelevant here: the "awaiting_review" tier ignores it entirely.
        register_model(high=0.95, low=0.40)  # FakeRunner's 0.92 confidence is now "low"

        _, body = create_observation(db_client, farmer_headers)
        obs_id = body["data"]["id"]
        assert body["data"]["verification_status"] == "PENDING_REVIEW"

        response = _get_advisory(db_client, obs_id, farmer_headers)
        data = response.json()["data"]
        assert data["tier"] == "awaiting_review"
        section_names = [s["key"] for s in data["sections"]]
        assert not any("ipm_" in s for s in section_names)
        assert any("contact_expert" in s for s in section_names)

    def test_unavailable_ai_gets_generic_guidance_and_expert_contact(
        self, db_client: TestClient, farmer_headers
    ) -> None:
        """No model registered at all: the confidence gate (Phase 2) routes this to
        PENDING_REVIEW exactly as a low-confidence prediction would, and the advisory
        for that tier is generic - there is no separate "AI never ran" tier to reach,
        because PENDING_REVIEW already means "no assessment is available yet"."""
        _, body = create_observation(db_client, farmer_headers)
        obs_id = body["data"]["id"]
        assert body["data"]["prediction"] is None
        assert body["data"]["verification_status"] == "PENDING_REVIEW"

        response = _get_advisory(db_client, obs_id, farmer_headers)
        data = response.json()["data"]
        assert data["tier"] == "awaiting_review"
        section_names = [s["key"] for s in data["sections"]]
        assert any("contact_expert" in s for s in section_names)
        assert not any("ipm_" in s for s in section_names)

    def test_no_verification_status_falls_back_to_generic_advisory(self) -> None:
        """Defensive path in the engine itself: a caller passing no status at all
        (not reachable through the API today - observations.verification_status is
        NOT NULL - but the engine is a reusable unit, not just this one endpoint)
        still gets a safe, generic result rather than an error."""
        from app.advisory.engine import AdvisoryEngine

        result = AdvisoryEngine().evaluate(
            verification_status=None, agent_kind=None, risk_level=None
        )
        assert result.tier == "unavailable"
        assert not any("ipm_" in s.key for s in result.sections)
        assert any("contact_expert" in s.key for s in result.sections)


class TestAdvisoryLanguage:
    def test_language_query_param_is_honoured(
        self, db_client: TestClient, db_session: Session, farmer_headers, expert_headers
    ) -> None:
        # `ensure_agent`/`_unique_agent` give every language column the same value,
        # which can never demonstrate localisation - build one with real per-language
        # names instead, the way the seeded reference catalogue actually looks.
        from app.models.catalog import DiseasePestCatalog

        agent = DiseasePestCatalog(
            code=f"TEST_LANG_{uuid.uuid4().hex[:8]}",
            kind="DISEASE",
            name_en="English Name",
            name_hi="Hindi Name",
            name_mr="Marathi Name",
        )
        db_session.add(agent)
        db_session.flush()

        _, body = create_observation(db_client, farmer_headers)
        obs_id = body["data"]["id"]
        db_session.query(Observation).filter(Observation.id == uuid.UUID(obs_id)).update(
            {"verification_status": "PENDING_REVIEW"}
        )
        db_session.flush()
        db_client.post(
            f"/api/v1/reviews/{obs_id}/decision",
            headers=expert_headers,
            json={"decision": "CORRECT", "corrected_agent_id": str(agent.id)},
        )

        en = _get_advisory(db_client, obs_id, farmer_headers, lang="en").json()["data"]
        mr = _get_advisory(db_client, obs_id, farmer_headers, lang="mr").json()["data"]
        assert en["language"] == "en"
        assert mr["language"] == "mr"
        # Same underlying agent, different localised label.
        assert en["agent_name"] != mr["agent_name"]

    def test_unauthenticated_request_is_rejected(self, db_client: TestClient) -> None:
        response = db_client.get(f"/api/v1/observations/{uuid.uuid4()}/advisory")
        assert response.status_code == 401

    def test_other_farmer_cannot_view_the_advisory(
        self, db_client: TestClient, farmer_headers, make_user, auth_headers
    ) -> None:
        _, body = create_observation(db_client, farmer_headers)
        obs_id = body["data"]["id"]

        other_headers = auth_headers(make_user(UserRole.FARMER))
        response = _get_advisory(db_client, obs_id, other_headers)
        assert response.status_code == 404
