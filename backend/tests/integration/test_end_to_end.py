"""Phase 9 - one full walk of the coherent demo story, end to end.

    farmer submits an observation (image + GPS)
      -> AI prediction + weather/context -> risk computed
      -> observation appears on the map
      -> expert confirms it -> verification state changes
      -> advisory stays linked and reflects the confirmed state
      -> farmer submits a follow-up
      -> official dashboard reflects the observation and its current state

Every step calls the same endpoint a real client would; nothing here is a shortcut
through internal services. This does not replace the focused suites (test_gis.py,
test_reviews.py, test_advisory.py, test_followups.py, test_dashboards.py) - it exists
to prove those modules agree on ONE record, which the focused suites (each working
with their own fixtures) do not individually guarantee.
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


def test_full_farmer_to_official_flow(
    db_client: TestClient,
    db_session: Session,
    make_user,
    auth_headers,
    register_model,  # noqa: F811
) -> None:
    ensure_agent(db_session, "HEALTHY", kind="HEALTHY")
    register_model()

    farmer = make_user(UserRole.FARMER)
    expert = make_user(UserRole.EXTENSION_WORKER)
    official = make_user(UserRole.OFFICIAL)
    farmer_headers = auth_headers(farmer)
    expert_headers = auth_headers(expert)
    official_headers = auth_headers(official)

    # 1-2. Farmer submits an observation; it reaches the AI + risk pipeline.
    status_code, body = create_observation(db_client, farmer_headers)
    assert status_code == 201
    obs = body["data"]
    obs_id = obs["id"]
    assert obs["prediction"] is not None, "AI prediction did not run"
    assert obs["risk"] is not None, "risk was not computed"

    # Force into the review queue so step 4 has something to decide (mirrors the
    # confidence-gate outcome the review test suite already exercises directly).
    db_session.query(Observation).filter(Observation.id == uuid.UUID(obs_id)).update(
        {"verification_status": "PENDING_REVIEW"}
    )
    db_session.flush()

    # 3. Observation appears on the map, scoped for an official/expert viewer.
    gis_resp = db_client.get(
        "/api/v1/gis/observations",
        params={"bbox": "72.6,15.6,80.9,22.1"},
        headers=official_headers,
    )
    assert gis_resp.status_code == 200
    map_ids = [f["properties"]["id"] for f in gis_resp.json()["data"]["features"]]
    assert obs_id in map_ids

    # 4-5. Expert confirms it; the verification state visibly changes.
    decision_resp = db_client.post(
        f"/api/v1/reviews/{obs_id}/decision",
        headers=expert_headers,
        json={"decision": "CONFIRM", "note": "Looks healthy"},
    )
    assert decision_resp.status_code == 200
    assert decision_resp.json()["data"]["verification_status"] == "CONFIRMED"

    farmer_view = db_client.get(f"/api/v1/observations/{obs_id}", headers=farmer_headers)
    assert farmer_view.json()["data"]["verification_status"] == "CONFIRMED"

    # Map/hotspot layer picks up the same confirmed state (no separate copy of it).
    gis_resp_2 = db_client.get(
        "/api/v1/gis/observations",
        params={"bbox": "72.6,15.6,80.9,22.1", "verification_status": "CONFIRMED"},
        headers=official_headers,
    )
    assert obs_id in [f["properties"]["id"] for f in gis_resp_2.json()["data"]["features"]]

    # 6. Advisory remains linked and reflects the now-confirmed diagnosis.
    advisory_resp = db_client.get(f"/api/v1/observations/{obs_id}/advisory", headers=farmer_headers)
    assert advisory_resp.status_code == 200
    advisory = advisory_resp.json()["data"]
    assert advisory["observation_id"] == obs_id
    assert advisory["tier"] == "confirmed"

    # 7. Farmer submits a follow-up.
    create_fu = db_client.post(
        "/api/v1/followups", headers=farmer_headers, json={"observation_id": obs_id}
    )
    assert create_fu.status_code == 201
    followup_id = create_fu.json()["data"]["id"]

    submit_fu = db_client.post(
        f"/api/v1/followups/{followup_id}/submit",
        headers=farmer_headers,
        data={"payload": json.dumps({"outcome": "IMPROVED", "notes": "looking better"})},
    )
    assert submit_fu.status_code == 200
    assert submit_fu.json()["data"]["outcome"] == "IMPROVED"

    # The original observation's own verification/diagnosis columns are untouched by
    # the follow-up (TRD provenance guarantee, Phase 7 Part G).
    original = db_session.get(Observation, uuid.UUID(obs_id))
    db_session.refresh(original)
    assert original.verification_status == "CONFIRMED"

    # 8. Official dashboard reflects the observation and its current state.
    dashboard = db_client.get("/api/v1/dashboards/official", headers=official_headers).json()[
        "data"
    ]
    assert obs_id in [o["id"] for o in dashboard["recent_activity"]["observations"]]
    assert obs_id in [o["id"] for o in dashboard["recent_activity"]["expert_validations"]]
    assert dashboard["overview"]["confirmed_cases"] >= 1

    # 9. RBAC still prevents a farmer from opening the official dashboard or the
    # expert review queue.
    assert db_client.get("/api/v1/dashboards/official", headers=farmer_headers).status_code == 403
    assert db_client.get("/api/v1/reviews/queue", headers=farmer_headers).status_code == 403
