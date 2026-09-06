"""Expert review workflow tests (Phase 5).

Covers confirm/correct/reject, authorization, and the one guarantee that matters most:
the original AI prediction is never modified by a review decision.

Uses the same FakeRunner test double as the Phase 2 pipeline tests, registered against
a real `disease_pest_catalog` agent so the observation pipeline produces a genuine
`ai_predictions` row (with a real `model_version` foreign key) rather than one
hand-crafted in the test, which would violate that constraint.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.ai import inference_service
from app.core.rbac import UserRole
from app.models.observation import Observation
from app.models.prediction import AiPrediction
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
def farmer_headers(db_session: Session, make_user, auth_headers):
    return auth_headers(make_user(UserRole.FARMER))


@pytest.fixture
def expert_headers(db_session: Session, make_user, auth_headers):
    return auth_headers(make_user(UserRole.EXTENSION_WORKER))


@pytest.fixture
def pending_observation(
    db_session: Session,
    db_client: TestClient,
    farmer_headers,
    register_model,  # noqa: F811 - pytest fixture-by-parameter-name, not a redefinition
):
    """A real observation with a real AI prediction, forced into PENDING_REVIEW.

    The FakeRunner always predicts class "HEALTHY"; registering the catalog agent
    first means the pipeline resolves a real `predicted_agent_id`.
    """
    ensure_agent(db_session, "HEALTHY", kind="HEALTHY")
    register_model()

    status_code, body = create_observation(db_client, farmer_headers)
    assert status_code == 201
    obs_id = body["data"]["id"]

    db_session.query(Observation).filter(Observation.id == uuid.UUID(obs_id)).update(
        {"verification_status": "PENDING_REVIEW"}
    )
    db_session.flush()
    return obs_id


class TestReviewQueue:
    def test_pending_observation_appears_in_queue(
        self, db_client: TestClient, pending_observation, expert_headers
    ) -> None:
        response = db_client.get("/api/v1/reviews/queue", headers=expert_headers)
        assert response.status_code == 200
        ids = [item["id"] for item in response.json()["data"]]
        assert pending_observation in ids

    def test_confirmed_observation_leaves_the_queue(
        self, db_client: TestClient, pending_observation, expert_headers
    ) -> None:
        decision = db_client.post(
            f"/api/v1/reviews/{pending_observation}/decision",
            headers=expert_headers,
            json={"decision": "CONFIRM"},
        )
        assert decision.status_code == 200

        queue = db_client.get("/api/v1/reviews/queue", headers=expert_headers)
        ids = [item["id"] for item in queue.json()["data"]]
        assert pending_observation not in ids

    def test_farmer_cannot_view_the_queue(self, db_client: TestClient, farmer_headers) -> None:
        response = db_client.get("/api/v1/reviews/queue", headers=farmer_headers)
        assert response.status_code == 403


class TestConfirm:
    def test_confirm_sets_confirmed_status_and_final_agent(
        self, db_client: TestClient, pending_observation, expert_headers
    ) -> None:
        response = db_client.post(
            f"/api/v1/reviews/{pending_observation}/decision",
            headers=expert_headers,
            json={"decision": "CONFIRM", "note": "Looks right to me"},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["verification_status"] == "CONFIRMED"
        assert data["final_agent_id"] is not None
        assert data["provenance"]["verified_by"] is not None
        assert data["provenance"]["verified_at"] is not None

    def test_confirm_without_a_prediction_is_rejected(
        self, db_client: TestClient, db_session: Session, farmer_headers, expert_headers
    ) -> None:
        # No model registered at all in this test: the observation is created
        # directly with PENDING_REVIEW and no ai_predictions row.
        status_code, body = create_observation(db_client, farmer_headers)
        assert status_code == 201
        obs_id = uuid.UUID(body["data"]["id"])
        db_session.query(Observation).filter(Observation.id == obs_id).update(
            {"verification_status": "PENDING_REVIEW"}
        )
        db_session.flush()
        assert (
            db_session.query(AiPrediction).filter(AiPrediction.observation_id == obs_id).first()
            is None
        )

        response = db_client.post(
            f"/api/v1/reviews/{obs_id}/decision",
            headers=expert_headers,
            json={"decision": "CONFIRM"},
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "NO_PREDICTION_TO_CONFIRM"


class TestCorrect:
    def test_correct_requires_an_agent_id(
        self, db_client: TestClient, pending_observation, expert_headers
    ) -> None:
        response = db_client.post(
            f"/api/v1/reviews/{pending_observation}/decision",
            headers=expert_headers,
            json={"decision": "CORRECT"},
        )
        assert response.status_code == 422

    def test_correct_sets_corrected_status_and_chosen_agent(
        self, db_client: TestClient, db_session: Session, pending_observation, expert_headers
    ) -> None:
        other_agent = ensure_agent(db_session, "UNKNOWN", kind="UNKNOWN")

        response = db_client.post(
            f"/api/v1/reviews/{pending_observation}/decision",
            headers=expert_headers,
            json={"decision": "CORRECT", "corrected_agent_id": str(other_agent.id)},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["verification_status"] == "CORRECTED"
        assert data["final_agent_id"] == str(other_agent.id)

    def test_correct_with_unknown_agent_id_is_404(
        self, db_client: TestClient, pending_observation, expert_headers
    ) -> None:
        response = db_client.post(
            f"/api/v1/reviews/{pending_observation}/decision",
            headers=expert_headers,
            json={"decision": "CORRECT", "corrected_agent_id": str(uuid.uuid4())},
        )
        assert response.status_code == 404

    def test_ai_prediction_is_unchanged_after_correction(
        self, db_client: TestClient, db_session: Session, pending_observation, expert_headers
    ) -> None:
        """The one guarantee that matters most: correcting an observation must never
        rewrite what the model actually predicted."""
        obs_id = uuid.UUID(pending_observation)
        before = (
            db_session.query(AiPrediction)
            .filter(AiPrediction.observation_id == obs_id)
            .order_by(AiPrediction.created_at.desc())
            .first()
        )
        assert before is not None
        before_class, before_confidence, before_agent = (
            before.predicted_class,
            before.confidence,
            before.predicted_agent_id,
        )

        other_agent = ensure_agent(db_session, "UNKNOWN", kind="UNKNOWN")
        response = db_client.post(
            f"/api/v1/reviews/{pending_observation}/decision",
            headers=expert_headers,
            json={"decision": "CORRECT", "corrected_agent_id": str(other_agent.id)},
        )
        assert response.status_code == 200

        db_session.expire_all()
        after = (
            db_session.query(AiPrediction)
            .filter(AiPrediction.observation_id == obs_id)
            .order_by(AiPrediction.created_at.desc())
            .first()
        )
        assert after.predicted_class == before_class
        assert after.confidence == before_confidence
        assert after.predicted_agent_id == before_agent
        # The prediction disagrees with the correction - that disagreement is exactly
        # what "AI prediction != expert-confirmed diagnosis" means in the data.
        assert after.predicted_agent_id != other_agent.id


class TestReject:
    def test_reject_sets_rejected_status_with_no_final_agent(
        self, db_client: TestClient, pending_observation, expert_headers
    ) -> None:
        response = db_client.post(
            f"/api/v1/reviews/{pending_observation}/decision",
            headers=expert_headers,
            json={"decision": "REJECT", "note": "Image is unusable"},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["verification_status"] == "REJECTED"
        assert data["final_agent_id"] is None


class TestAuthorizationAndState:
    def test_farmer_cannot_submit_a_decision(
        self, db_client: TestClient, pending_observation, farmer_headers
    ) -> None:
        response = db_client.post(
            f"/api/v1/reviews/{pending_observation}/decision",
            headers=farmer_headers,
            json={"decision": "CONFIRM"},
        )
        assert response.status_code == 403

    def test_cannot_decide_an_observation_not_awaiting_review(
        self, db_client: TestClient, pending_observation, expert_headers
    ) -> None:
        first = db_client.post(
            f"/api/v1/reviews/{pending_observation}/decision",
            headers=expert_headers,
            json={"decision": "REJECT"},
        )
        assert first.status_code == 200

        second = db_client.post(
            f"/api/v1/reviews/{pending_observation}/decision",
            headers=expert_headers,
            json={"decision": "CONFIRM"},
        )
        assert second.status_code == 409
        assert second.json()["error"]["code"] == "OBSERVATION_NOT_REVIEWABLE"

    def test_decision_is_audited(
        self, db_client: TestClient, db_session: Session, pending_observation, expert_headers
    ) -> None:
        db_client.post(
            f"/api/v1/reviews/{pending_observation}/decision",
            headers=expert_headers,
            json={"decision": "CONFIRM"},
        )

        from sqlalchemy import text

        count = db_session.execute(
            text(
                "SELECT count(*) FROM audit_logs WHERE action = 'OBSERVATION_REVIEWED' "
                "AND entity_id = :id"
            ),
            {"id": pending_observation},
        ).scalar_one()
        assert count == 1
