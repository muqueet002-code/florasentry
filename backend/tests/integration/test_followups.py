"""Follow-up workflow tests (Phase 7).

Covers: scheduling, submission with and without an image (reusing the existing
observation pipeline either way), outcome persistence, authorization, and the
guarantee that a follow-up never touches the parent observation's own diagnosis.
"""

from __future__ import annotations

import io
import json

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy.orm import Session

from app.ai import inference_service
from app.core.rbac import UserRole
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


def _make_image_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (400, 300), color=(40, 100, 40)).save(buffer, format="JPEG")
    return buffer.getvalue()


class TestScheduling:
    def test_create_schedules_a_followup(self, db_client: TestClient, farmer_headers) -> None:
        _, body = create_observation(db_client, farmer_headers)
        obs_id = body["data"]["id"]

        response = db_client.post(
            "/api/v1/followups", headers=farmer_headers, json={"observation_id": obs_id}
        )
        assert response.status_code == 201
        data = response.json()["data"]
        assert data["parent_observation_id"] == obs_id
        assert data["status"] == "SCHEDULED"
        assert data["outcome"] is None
        assert data["scheduled_for"]

    def test_scheduled_for_can_be_overridden(self, db_client: TestClient, farmer_headers) -> None:
        _, body = create_observation(db_client, farmer_headers)
        obs_id = body["data"]["id"]
        due = "2026-01-01T00:00:00Z"

        response = db_client.post(
            "/api/v1/followups",
            headers=farmer_headers,
            json={"observation_id": obs_id, "scheduled_for": due},
        )
        assert response.status_code == 201
        assert response.json()["data"]["scheduled_for"].startswith("2026-01-01")

    def test_cannot_schedule_for_someone_elses_observation(
        self, db_client: TestClient, farmer_headers, make_user, auth_headers
    ) -> None:
        _, body = create_observation(db_client, farmer_headers)
        obs_id = body["data"]["id"]

        other_headers = auth_headers(make_user(UserRole.FARMER))
        response = db_client.post(
            "/api/v1/followups", headers=other_headers, json={"observation_id": obs_id}
        )
        assert response.status_code == 404  # not visible, so not found rather than forbidden

    def test_list_filters_by_observation(self, db_client: TestClient, farmer_headers) -> None:
        _, body = create_observation(db_client, farmer_headers)
        obs_id = body["data"]["id"]
        db_client.post("/api/v1/followups", headers=farmer_headers, json={"observation_id": obs_id})

        response = db_client.get(
            "/api/v1/followups", headers=farmer_headers, params={"observation_id": obs_id}
        )
        assert response.status_code == 200
        items = response.json()["data"]
        assert len(items) == 1
        assert items[0]["parent_observation_id"] == obs_id


class TestSubmission:
    def _schedule(self, client: TestClient, headers: dict, obs_id: str) -> str:
        response = client.post(
            "/api/v1/followups", headers=headers, json={"observation_id": obs_id}
        )
        return response.json()["data"]["id"]

    def test_submit_without_image_creates_a_manual_report_observation(
        self, db_client: TestClient, farmer_headers
    ) -> None:
        _, body = create_observation(db_client, farmer_headers)
        obs_id = body["data"]["id"]
        followup_id = self._schedule(db_client, farmer_headers, obs_id)

        response = db_client.post(
            f"/api/v1/followups/{followup_id}/submit",
            headers=farmer_headers,
            data={"payload": json.dumps({"outcome": "IMPROVED", "notes": "Looking better"})},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["status"] == "SUBMITTED"
        assert data["outcome"] == "IMPROVED"
        assert data["followup_observation_id"] is not None
        assert data["linked_observation"]["observation_type"] == "MANUAL_REPORT"
        # Reused the real pipeline: risk was computed for the child observation too.
        assert data["linked_observation"]["risk"] is not None

    def test_submit_with_image_creates_an_image_observation(
        self,
        db_client: TestClient,
        farmer_headers,
        register_model,  # noqa: F811
    ) -> None:
        register_model()
        _, body = create_observation(db_client, farmer_headers)
        obs_id = body["data"]["id"]
        followup_id = self._schedule(db_client, farmer_headers, obs_id)

        response = db_client.post(
            f"/api/v1/followups/{followup_id}/submit",
            headers=farmer_headers,
            data={"payload": json.dumps({"outcome": "WORSENED"})},
            files={"image": ("followup.jpg", _make_image_bytes(), "image/jpeg")},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["linked_observation"]["observation_type"] == "IMAGE"
        # AI ran again on the follow-up image, through the same pipeline.
        assert data["linked_observation"]["prediction"] is not None

    def test_outcome_must_be_a_controlled_value(
        self, db_client: TestClient, farmer_headers
    ) -> None:
        _, body = create_observation(db_client, farmer_headers)
        obs_id = body["data"]["id"]
        followup_id = self._schedule(db_client, farmer_headers, obs_id)

        response = db_client.post(
            f"/api/v1/followups/{followup_id}/submit",
            headers=farmer_headers,
            data={"payload": json.dumps({"outcome": "PROBABLY_FINE"})},
        )
        assert response.status_code == 422

    def test_cannot_submit_the_same_followup_twice(
        self, db_client: TestClient, farmer_headers
    ) -> None:
        _, body = create_observation(db_client, farmer_headers)
        obs_id = body["data"]["id"]
        followup_id = self._schedule(db_client, farmer_headers, obs_id)

        first = db_client.post(
            f"/api/v1/followups/{followup_id}/submit",
            headers=farmer_headers,
            data={"payload": json.dumps({"outcome": "RESOLVED"})},
        )
        assert first.status_code == 200

        second = db_client.post(
            f"/api/v1/followups/{followup_id}/submit",
            headers=farmer_headers,
            data={"payload": json.dumps({"outcome": "IMPROVED"})},
        )
        assert second.status_code == 409
        assert second.json()["error"]["code"] == "FOLLOWUP_ALREADY_SUBMITTED"

    def test_other_farmer_cannot_submit(
        self, db_client: TestClient, farmer_headers, make_user, auth_headers
    ) -> None:
        _, body = create_observation(db_client, farmer_headers)
        obs_id = body["data"]["id"]
        followup_id = self._schedule(db_client, farmer_headers, obs_id)

        other_headers = auth_headers(make_user(UserRole.FARMER))
        response = db_client.post(
            f"/api/v1/followups/{followup_id}/submit",
            headers=other_headers,
            data={"payload": json.dumps({"outcome": "IMPROVED"})},
        )
        assert response.status_code == 404


class TestDataIntegrity:
    def test_parent_diagnosis_is_unchanged_after_a_followup(
        self,
        db_client: TestClient,
        db_session: Session,
        farmer_headers,
        register_model,  # noqa: F811
    ) -> None:
        """A worsening follow-up must never retroactively alter the original
        observation's own verification_status, final_agent_id or prediction."""
        register_model()
        _, body = create_observation(db_client, farmer_headers)
        obs_id = body["data"]["id"]
        before_status = body["data"]["verification_status"]
        before_final_agent = body["data"]["final_agent_id"]

        followup_id = self._schedule_helper(db_client, farmer_headers, obs_id)
        db_client.post(
            f"/api/v1/followups/{followup_id}/submit",
            headers=farmer_headers,
            data={"payload": json.dumps({"outcome": "WORSENED"})},
            files={"image": ("followup.jpg", _make_image_bytes(), "image/jpeg")},
        )

        parent = db_client.get(f"/api/v1/observations/{obs_id}", headers=farmer_headers).json()[
            "data"
        ]
        assert parent["verification_status"] == before_status
        assert parent["final_agent_id"] == before_final_agent

    def test_followup_observation_is_distinct_from_parent(
        self, db_client: TestClient, farmer_headers
    ) -> None:
        _, body = create_observation(db_client, farmer_headers)
        obs_id = body["data"]["id"]
        followup_id = self._schedule_helper(db_client, farmer_headers, obs_id)

        response = db_client.post(
            f"/api/v1/followups/{followup_id}/submit",
            headers=farmer_headers,
            data={"payload": json.dumps({"outcome": "UNCHANGED"})},
        )
        child_id = response.json()["data"]["linked_observation"]["id"]
        assert child_id != obs_id

    def test_worsened_followups_are_discoverable_for_expert_triage(
        self, db_client: TestClient, db_session: Session, farmer_headers, make_user, auth_headers
    ) -> None:
        """`GET /followups?outcome=WORSENED` is how an expert identifies cases that
        need attention, without a separate dashboard."""
        _, body = create_observation(db_client, farmer_headers)
        obs_id = body["data"]["id"]
        followup_id = self._schedule_helper(db_client, farmer_headers, obs_id)
        db_client.post(
            f"/api/v1/followups/{followup_id}/submit",
            headers=farmer_headers,
            data={"payload": json.dumps({"outcome": "WORSENED"})},
        )

        expert_headers = auth_headers(make_user(UserRole.EXTENSION_WORKER))
        response = db_client.get(
            "/api/v1/followups", headers=expert_headers, params={"outcome": "WORSENED"}
        )
        assert response.status_code == 200
        ids = [f["id"] for f in response.json()["data"]]
        assert followup_id in ids

    @staticmethod
    def _schedule_helper(client: TestClient, headers: dict, obs_id: str) -> str:
        response = client.post(
            "/api/v1/followups", headers=headers, json={"observation_id": obs_id}
        )
        return response.json()["data"]["id"]


class TestDueFlag:
    def test_future_followup_is_not_due(self, db_client: TestClient, farmer_headers) -> None:
        _, body = create_observation(db_client, farmer_headers)
        obs_id = body["data"]["id"]
        response = db_client.post(
            "/api/v1/followups",
            headers=farmer_headers,
            json={"observation_id": obs_id, "scheduled_for": "2099-01-01T00:00:00Z"},
        )
        assert response.json()["data"]["is_due"] is False

    def test_past_scheduled_followup_is_due(self, db_client: TestClient, farmer_headers) -> None:
        _, body = create_observation(db_client, farmer_headers)
        obs_id = body["data"]["id"]
        response = db_client.post(
            "/api/v1/followups",
            headers=farmer_headers,
            json={"observation_id": obs_id, "scheduled_for": "2020-01-01T00:00:00Z"},
        )
        assert response.json()["data"]["is_due"] is True
