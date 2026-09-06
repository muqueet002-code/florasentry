"""End-to-end observation pipeline tests (Phase 2 + 3).

Covers the full slice against a real database: image -> AI -> confidence gate ->
weather -> context -> risk -> API response.

A fake ModelRunner is registered so the confidence gate can be exercised
deterministically. It is clearly labelled and lives only in the test suite - the
application itself never substitutes a prediction.
"""

from __future__ import annotations

import io
import json
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.ai import inference_service
from app.ai.interface import (
    ClassScore,
    InferenceFailedError,
    ModelMetadata,
    ModelRunner,
    ModelUnavailableError,
    PredictionResult,
)
from app.core.rbac import UserRole
from app.integrations.weather.interface import (
    WeatherProvider,
    WeatherReading,
    WeatherUnavailable,
)
from app.models.prediction import AiModelRegistry, AiPrediction
from app.models.risk import RiskAssessment
from app.models.weather import WeatherObservation
from app.services.weather_service import WeatherService, grid_cell

pytestmark = pytest.mark.integration

# Inside the configured operating bbox (Maharashtra).
LAT, LON = 19.75, 75.71


def make_image(width: int = 400, height: int = 300) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), color=(60, 120, 60)).save(buffer, format="JPEG")
    return buffer.getvalue()


# ---- test doubles ------------------------------------------------------------


class FakeRunner(ModelRunner):
    """Deterministic runner for testing the gate. NOT used by the application."""

    confidence = 0.92
    should_fail = False

    def __init__(self, metadata: ModelMetadata) -> None:
        self._metadata = metadata
        self._loaded = False

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def metadata(self) -> ModelMetadata:
        return self._metadata

    def load(self, artifact_path: str) -> None:
        self._loaded = True

    def warmup(self) -> None:
        return None

    def predict(self, image_bytes: bytes) -> PredictionResult:
        if FakeRunner.should_fail:
            raise InferenceFailedError("Simulated inference failure")
        confidence = FakeRunner.confidence
        return PredictionResult(
            predicted_class="HEALTHY",
            confidence=confidence,
            top_k=[
                ClassScore("HEALTHY", confidence),
                ClassScore("UNKNOWN", round(1 - confidence, 4)),
            ],
            inference_ms=7,
            runtime_device="cpu",
        )


class UnloadableRunner(FakeRunner):
    """Simulates weights that cannot be loaded (the real repository's state)."""

    def load(self, artifact_path: str) -> None:
        raise ModelUnavailableError("Model artifact not found")


FAKE_RUNNER_PATH = "tests.FakeRunner"
UNLOADABLE_RUNNER_PATH = "tests.UnloadableRunner"


class StubWeatherProvider(WeatherProvider):
    name = "stub"
    supports_historical = False
    calls = 0

    def __init__(self, fail: bool = False) -> None:
        self.fail = fail

    def get_current(self, latitude: float, longitude: float) -> WeatherReading:
        StubWeatherProvider.calls += 1
        if self.fail:
            raise WeatherUnavailable("stub provider is down")
        return WeatherReading(
            observed_at=datetime.now(UTC).replace(microsecond=0),
            temperature_c=26.0,
            humidity_pct=88.0,
            rainfall_mm=1.2,
            wind_speed_ms=2.5,
            pressure_hpa=955.0,
            raw={"stub": True},
        )

    def get_forecast(self, latitude: float, longitude: float, days: int) -> list[WeatherReading]:
        StubWeatherProvider.calls += 1
        if self.fail:
            raise WeatherUnavailable("stub provider is down")
        base = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        return [
            WeatherReading(
                observed_at=base + timedelta(days=i),
                temperature_c=27.0,
                humidity_pct=80.0,
                rainfall_mm=2.0,
            )
            for i in range(min(days, 3))
        ]


# ---- fixtures ----------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_ai_state():
    FakeRunner.confidence = 0.92
    FakeRunner.should_fail = False
    StubWeatherProvider.calls = 0
    inference_service.RUNNERS[FAKE_RUNNER_PATH] = FakeRunner
    inference_service.RUNNERS[UNLOADABLE_RUNNER_PATH] = UnloadableRunner
    inference_service.reset_runner_cache()
    yield
    inference_service.reset_runner_cache()


@pytest.fixture
def register_model(db_session: Session):
    """Register an active model row pointing at a test runner."""

    def _register(
        runner_path: str = FAKE_RUNNER_PATH,
        high: float = 0.75,
        low: float = 0.40,
    ) -> AiModelRegistry:
        # Exactly one active CLASSIFICATION model is enforced by a DB constraint
        # (uq_active_model_per_task); deactivate any prior one from this test first.
        db_session.query(AiModelRegistry).filter(
            AiModelRegistry.task == "CLASSIFICATION", AiModelRegistry.is_active.is_(True)
        ).update({"is_active": False})
        db_session.flush()

        row = AiModelRegistry(
            model_version=f"test-model-{uuid.uuid4().hex[:8]}",
            task="CLASSIFICATION",
            framework="test",
            runner_class=runner_path,
            artifact_key="test.pt",
            artifact_checksum="0" * 64,
            input_size="224x224",
            class_list=["HEALTHY", "UNKNOWN"],
            high_confidence_threshold=Decimal(str(high)),
            low_confidence_threshold=Decimal(str(low)),
            is_active=True,
            # Never pre-filled: no evaluation run has happened.
            evaluation_metrics=None,
        )
        db_session.add(row)
        db_session.flush()
        inference_service.reset_runner_cache()
        return row

    return _register


@pytest.fixture
def farmer_headers(db_session: Session, make_user, auth_headers):
    user = make_user(UserRole.FARMER)
    return user, auth_headers(user)


def create_observation(
    client: TestClient, headers: dict, *, image: bytes | None = None, **overrides
) -> tuple[int, dict]:
    payload = {"latitude": LAT, "longitude": LON, "observation_type": "IMAGE", **overrides}
    files = {"image": ("leaf.jpg", image if image is not None else make_image(), "image/jpeg")}
    response = client.post(
        "/api/v1/observations",
        headers=headers,
        data={"payload": json.dumps(payload)},
        files=files,
    )
    return response.status_code, response.json()


# ---- AI: model unavailable ---------------------------------------------------


class TestAiUnavailable:
    def test_no_registered_model_reports_unavailable(
        self, db_client: TestClient, farmer_headers
    ) -> None:
        """The repository's real state: no model registered."""
        _, headers = farmer_headers
        response = db_client.get("/api/v1/ai/models/active", headers=headers)
        data = response.json()["data"]
        assert data["ok"] is False
        assert data["state"] == "AI_MODEL_UNAVAILABLE"
        assert data["model_version"] is None

    def test_observation_survives_with_no_model(
        self, db_client: TestClient, farmer_headers, db_session: Session
    ) -> None:
        """The governing rule: the observation must survive AI unavailability."""
        _, headers = farmer_headers
        status_code, body = create_observation(db_client, headers)

        assert status_code == 201
        observation = body["data"]
        assert observation["id"]
        assert observation["prediction"] is None, "no model means no prediction, not a fake one"
        # Routed to a human rather than presented as an assessment.
        assert observation["verification_status"] == "PENDING_REVIEW"
        assert observation["processing_errors"]["ai"]["code"] == "AI_MODEL_UNAVAILABLE"
        assert any(w["code"] == "AI_MODEL_UNAVAILABLE" for w in body["warnings"])

        # It is genuinely persisted.
        stored = db_session.execute(
            text("SELECT count(*) FROM observations WHERE id = :id"),
            {"id": observation["id"]},
        ).scalar_one()
        assert stored == 1

    def test_unloadable_artifact_reports_unavailable(
        self, db_client: TestClient, farmer_headers, register_model
    ) -> None:
        register_model(runner_path=UNLOADABLE_RUNNER_PATH)
        _, headers = farmer_headers
        status_code, body = create_observation(db_client, headers)

        assert status_code == 201
        assert body["data"]["prediction"] is None
        assert body["data"]["processing_errors"]["ai"]["code"] == "AI_MODEL_UNAVAILABLE"

    def test_inference_failure_records_and_preserves(
        self, db_client: TestClient, farmer_headers, register_model
    ) -> None:
        register_model()
        FakeRunner.should_fail = True
        _, headers = farmer_headers
        status_code, body = create_observation(db_client, headers)

        assert status_code == 201
        observation = body["data"]
        assert observation["status"] == "AI_FAILED"
        assert observation["verification_status"] == "PENDING_REVIEW"
        assert observation["processing_errors"]["ai"]["code"] == "AI_INFERENCE_FAILED"
        assert observation["prediction"] is None

    def test_analyze_endpoint_refuses_rather_than_inventing(
        self, db_client: TestClient, db_session: Session, make_user, auth_headers
    ) -> None:
        worker = make_user(UserRole.EXTENSION_WORKER)
        response = db_client.post(
            "/api/v1/ai/analyze",
            headers=auth_headers(worker),
            files={"image": ("leaf.jpg", make_image(), "image/jpeg")},
        )
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "AI_MODEL_UNAVAILABLE"
        assert "confidence" not in response.text


# ---- AI: confidence gate -----------------------------------------------------


class TestConfidenceGate:
    def test_high_confidence_yields_predicted(
        self, db_client: TestClient, farmer_headers, register_model
    ) -> None:
        register_model(high=0.75)
        FakeRunner.confidence = 0.92
        _, headers = farmer_headers
        _, body = create_observation(db_client, headers)

        observation = body["data"]
        assert observation["verification_status"] == "PREDICTED"
        assert observation["prediction"]["is_low_confidence"] is False
        # A prediction is still not a diagnosis: only an expert sets final_agent_id.
        assert observation["final_agent_id"] is None

    def test_low_confidence_routes_to_expert_review(
        self, db_client: TestClient, farmer_headers, register_model
    ) -> None:
        register_model(high=0.75)
        FakeRunner.confidence = 0.42
        _, headers = farmer_headers
        _, body = create_observation(db_client, headers)

        observation = body["data"]
        assert observation["verification_status"] == "PENDING_REVIEW"
        assert observation["prediction"]["is_low_confidence"] is True
        assert observation["final_agent_id"] is None
        assert any(w["code"] == "AI_LOW_CONFIDENCE" for w in body["warnings"])

    def test_threshold_is_configurable_per_model(
        self, db_client: TestClient, farmer_headers, register_model
    ) -> None:
        """The same confidence lands either side of the gate as the threshold moves."""
        FakeRunner.confidence = 0.60
        _, headers = farmer_headers

        register_model(high=0.75)
        _, low_gate = create_observation(db_client, headers)
        assert low_gate["data"]["verification_status"] == "PENDING_REVIEW"

        register_model(high=0.50)
        _, high_gate = create_observation(db_client, headers)
        assert high_gate["data"]["verification_status"] == "PREDICTED"

    def test_prediction_is_persisted_with_metadata(
        self, db_client: TestClient, farmer_headers, register_model, db_session: Session
    ) -> None:
        model = register_model()
        FakeRunner.confidence = 0.88
        _, headers = farmer_headers
        _, body = create_observation(db_client, headers)

        observation_id = uuid.UUID(body["data"]["id"])
        stored = (
            db_session.query(AiPrediction)
            .filter(AiPrediction.observation_id == observation_id)
            .one()
        )
        assert stored.predicted_class == "HEALTHY"
        assert float(stored.confidence) == pytest.approx(0.88, abs=1e-4)
        assert stored.model_version == model.model_version
        assert stored.inference_ms is not None
        assert stored.top_k and len(stored.top_k) == 2
        assert stored.is_low_confidence is False


# ---- Weather -----------------------------------------------------------------


class TestWeatherService:
    def test_live_fetch_is_persisted(self, db_session: Session) -> None:
        service = WeatherService(db_session, StubWeatherProvider())
        snapshot = service.get_snapshot(LAT, LON)

        assert snapshot.available is True
        assert snapshot.is_stale is False
        assert snapshot.cache_hit is False
        assert snapshot.reading.humidity_pct == 88.0

        # Scoped by provider too: a real open_meteo row for this same cell may already
        # exist from manual/live testing against the shared dev database.
        rows = (
            db_session.query(WeatherObservation)
            .filter(
                WeatherObservation.grid_cell == grid_cell(LAT, LON),
                WeatherObservation.provider == "stub",
            )
            .count()
        )
        assert rows == 1

    def test_second_call_hits_the_cache(self, db_session: Session) -> None:
        """Nearby requests must not each cost a provider call."""
        service = WeatherService(db_session, StubWeatherProvider())
        service.get_snapshot(LAT, LON)
        calls_after_first = StubWeatherProvider.calls

        second = service.get_snapshot(LAT, LON)
        assert second.cache_hit is True
        assert second.available is True
        assert StubWeatherProvider.calls == calls_after_first, "no extra provider call"

    def test_nearby_coordinates_share_a_grid_cell(self, db_session: Session) -> None:
        service = WeatherService(db_session, StubWeatherProvider())
        service.get_snapshot(LAT, LON)
        calls = StubWeatherProvider.calls
        # ~100 m away: same rounded cell at 2 dp.
        nearby = service.get_snapshot(LAT + 0.001, LON + 0.001)
        assert nearby.cache_hit is True
        assert StubWeatherProvider.calls == calls

    def test_provider_failure_falls_back_to_stale_cache(self, db_session: Session) -> None:
        WeatherService(db_session, StubWeatherProvider()).get_snapshot(LAT, LON)

        # Age the cached row beyond the fresh TTL but inside the stale window.
        db_session.execute(
            text("UPDATE weather_observations SET fetched_at = :ts WHERE grid_cell = :cell"),
            {"ts": datetime.now(UTC) - timedelta(hours=5), "cell": grid_cell(LAT, LON)},
        )
        db_session.flush()

        degraded = WeatherService(db_session, StubWeatherProvider(fail=True))
        snapshot = degraded.get_snapshot(LAT, LON)

        assert snapshot.available is True, "stale but real data is still usable"
        assert snapshot.is_stale is True
        assert snapshot.age_hours > 1

    def test_no_cache_and_dead_provider_reports_unavailable(self, db_session: Session) -> None:
        """No invented values, no zeros - an explicit unavailable result."""
        service = WeatherService(db_session, StubWeatherProvider(fail=True))
        snapshot = service.get_snapshot(LAT, LON)

        assert snapshot.available is False
        assert snapshot.reading is None
        assert snapshot.unavailable_reason

    def test_weather_endpoint_reports_unavailable(
        self, db_client: TestClient, farmer_headers, monkeypatch
    ) -> None:
        from app.integrations.weather import providers

        monkeypatch.setattr(
            providers, "get_weather_provider", lambda: StubWeatherProvider(fail=True)
        )
        _, headers = farmer_headers
        response = db_client.get(f"/api/v1/weather/current?lat={LAT}&lon={LON}", headers=headers)
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "WEATHER_UNAVAILABLE"


# ---- Context + risk ----------------------------------------------------------


class TestContextAndRisk:
    def test_context_is_built_from_available_inputs(self, db_session: Session, make_user) -> None:
        from app.models.observation import Observation
        from app.risk.context import ContextEngine

        user = make_user(UserRole.FARMER)
        observation = Observation(
            reported_by=user.id,
            latitude=Decimal(str(LAT)),
            longitude=Decimal(str(LON)),
            geom=text(f"ST_SetSRID(ST_MakePoint({LON},{LAT}),4326)"),
            source_type="FIELD_OBSERVATION",
            observed_at=datetime.now(UTC),
        )
        db_session.add(observation)
        db_session.flush()

        context = ContextEngine(
            db_session, WeatherService(db_session, StubWeatherProvider())
        ).build(observation, None)

        assert context.latitude == pytest.approx(LAT)
        assert context.weather_available is True
        assert context.nearby is not None
        # No AI, no crop, no stage were supplied - all recorded as missing.
        missing = {m["factor"] for m in context.missing}
        assert {"AI_SIGNAL", "CROP", "GROWTH_STAGE"} <= missing

    def test_risk_is_persisted_with_full_explanation(
        self, db_client: TestClient, farmer_headers, register_model, db_session: Session
    ) -> None:
        register_model()
        _, headers = farmer_headers
        _, body = create_observation(db_client, headers)

        risk = body["data"]["risk"]
        assert risk is not None
        assert 0 <= risk["risk_score"] <= 100
        assert risk["risk_level"] in {"LOW", "MEDIUM", "HIGH"}
        assert risk["contributing_factors"]
        assert risk["method"] == "RULE_BASED_V1"
        assert risk["ruleset_version"]
        assert risk["disclaimer_key"] == "risk.prototype_disclaimer"

        stored = (
            db_session.query(RiskAssessment)
            .filter(RiskAssessment.observation_id == uuid.UUID(body["data"]["id"]))
            .one()
        )
        assert float(stored.risk_score) == risk["risk_score"]

    def test_missing_weather_is_reported_in_the_risk_response(
        self, db_client: TestClient, farmer_headers, monkeypatch
    ) -> None:
        from app.integrations.weather import providers

        monkeypatch.setattr(
            providers, "get_weather_provider", lambda: StubWeatherProvider(fail=True)
        )
        _, headers = farmer_headers
        _, body = create_observation(db_client, headers)

        risk = body["data"]["risk"]
        assert risk is not None, "risk still computes without weather"
        missing = {m["factor"] for m in risk["missing_factors"]}
        assert "WEATHER" in missing
        assert any(w["code"] == "WEATHER_UNAVAILABLE" for w in body["warnings"])
        assert body["data"]["weather"]["available"] is False

    def test_ruleset_endpoint_states_it_is_not_validated(
        self, db_client: TestClient, farmer_headers
    ) -> None:
        _, headers = farmer_headers
        response = db_client.get("/api/v1/risk/ruleset", headers=headers)
        data = response.json()["data"]
        assert data["validation_status"] == "PROTOTYPE_NOT_SCIENTIFICALLY_VALIDATED"
        assert data["factors"], "the full ruleset is exposed for auditing"


# ---- End-to-end --------------------------------------------------------------


class TestEndToEnd:
    def test_full_pipeline(
        self, db_client: TestClient, farmer_headers, register_model, db_session: Session
    ) -> None:
        """image -> AI -> confidence -> weather -> context -> risk -> API."""
        model = register_model(high=0.75)
        FakeRunner.confidence = 0.91
        user, headers = farmer_headers

        # A field gives the observation crop context and a district.
        field_response = db_client.post(
            "/api/v1/fields",
            headers=headers,
            json={"name": f"E2E plot {uuid.uuid4().hex[:6]}", "latitude": LAT, "longitude": LON},
        )
        assert field_response.status_code == 201
        field_id = field_response.json()["data"]["id"]

        status_code, body = create_observation(
            db_client, headers, field_id=field_id, reported_severity=3, notes="spots on leaves"
        )
        assert status_code == 201
        observation = body["data"]

        # Image
        assert observation["image"]["url"].startswith("/api/v1/images/")
        assert observation["image"]["quality_flags"] is not None

        # AI prediction and confidence
        prediction = observation["prediction"]
        assert prediction["predicted_class"] == "HEALTHY"
        assert prediction["confidence"] == pytest.approx(0.91, abs=1e-3)
        assert prediction["model_version"] == model.model_version
        assert prediction["inference_ms"] is not None

        # Verification status is separate from the prediction and is not a diagnosis.
        assert observation["verification_status"] == "PREDICTED"
        assert observation["final_agent_id"] is None

        # Weather and risk
        assert observation["weather"]["provider"]
        assert observation["risk"]["risk_level"] in {"LOW", "MEDIUM", "HIGH"}
        assert observation["risk"]["contributing_factors"]

        # Provenance
        assert observation["provenance"]["source_type"] == "FIELD_OBSERVATION"
        assert observation["provenance"]["model_version"] == model.model_version

        # The detail endpoint returns the same combined result.
        detail = db_client.get(f"/api/v1/observations/{observation['id']}", headers=headers)
        assert detail.status_code == 200
        detail_body = detail.json()["data"]
        assert detail_body["prediction"]["predicted_class"] == "HEALTHY"
        assert detail_body["risk"]["risk_score"] == observation["risk"]["risk_score"]

        # The image is retrievable through the authorising endpoint.
        image = db_client.get(observation["image"]["url"], headers=headers)
        assert image.status_code == 200
        assert image.headers["content-type"] == "image/jpeg"

    def test_invalid_image_creates_no_observation(
        self, db_client: TestClient, farmer_headers, db_session: Session
    ) -> None:
        """Validation happens before persistence, so a bad upload leaves no row."""
        _, headers = farmer_headers
        before = db_session.execute(text("SELECT count(*) FROM observations")).scalar_one()

        status_code, body = create_observation(db_client, headers, image=b"not an image")
        assert status_code == 422
        assert body["error"]["code"] == "IMAGE_INVALID"

        after = db_session.execute(text("SELECT count(*) FROM observations")).scalar_one()
        assert after == before

    def test_coordinates_outside_operating_area_are_rejected(
        self, db_client: TestClient, farmer_headers
    ) -> None:
        _, headers = farmer_headers
        status_code, body = create_observation(db_client, headers, latitude=51.5, longitude=-0.12)
        assert status_code == 422
        assert body["error"]["code"] == "COORDINATES_OUT_OF_BOUNDS"

    def test_another_farmer_cannot_read_the_observation(
        self, db_client: TestClient, farmer_headers, make_user, auth_headers
    ) -> None:
        _, headers = farmer_headers
        _, body = create_observation(db_client, headers)
        observation_id = body["data"]["id"]

        other = make_user(UserRole.FARMER)
        response = db_client.get(
            f"/api/v1/observations/{observation_id}", headers=auth_headers(other)
        )
        assert response.status_code == 404

    def test_observation_requires_authentication(self, db_client: TestClient) -> None:
        response = db_client.post(
            "/api/v1/observations",
            data={"payload": json.dumps({"latitude": LAT, "longitude": LON})},
            files={"image": ("leaf.jpg", make_image(), "image/jpeg")},
        )
        assert response.status_code == 401
