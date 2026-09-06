"""Application startup, health/readiness, error envelope and phase-boundary tests.

These run WITHOUT a database, which is itself the point: the app must boot and report
its own degradation rather than crashing when the database is unreachable (TRD 32.2).
"""

from __future__ import annotations

from fastapi.testclient import TestClient


class TestApplicationStartup:
    def test_app_boots_and_serves_root(self, client: TestClient) -> None:
        response = client.get("/")
        assert response.status_code == 200
        assert response.json()["name"] == "FloraSentry V2"

    def test_openapi_schema_is_generated(self, client: TestClient) -> None:
        response = client.get("/openapi.json")
        assert response.status_code == 200
        paths = response.json()["paths"]
        assert "/api/v1/auth/login" in paths
        assert "/api/v1/fields" in paths

    def test_every_response_carries_a_trace_id(self, client: TestClient) -> None:
        response = client.get("/")
        assert response.headers.get("X-Trace-Id")

    def test_supplied_request_id_is_honoured(self, client: TestClient) -> None:
        response = client.get("/", headers={"X-Request-Id": "my-trace-1234"})
        assert response.headers["X-Trace-Id"] == "my-trace-1234"


class TestHealthEndpoint:
    def test_health_is_200_even_when_degraded(self, client: TestClient) -> None:
        """Liveness stays 200 while the process is alive; the BODY reports degradation."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["status"] in {"OK", "DEGRADED"}
        assert set(data["components"]) == {"database", "postgis", "ai_model", "weather_provider"}

    def test_health_reports_unconfigured_modules_honestly(self, client: TestClient) -> None:
        """No model is registered in this environment - say so, never imply working."""
        components = client.get("/health").json()["data"]["components"]
        assert components["ai_model"]["ok"] is False
        assert components["ai_model"]["state"] in {"AI_MODEL_UNAVAILABLE", "UNKNOWN"}
        # A weather provider is now selected (Phase 3); "ok" reflects selection, not a
        # live reachability check, which happens per request instead.
        assert components["weather_provider"]["state"] in {"CONFIGURED", "DISABLED"}

    def test_readiness_reports_database_state(self, client: TestClient) -> None:
        response = client.get("/health/ready")
        assert response.status_code in {200, 503}
        data = response.json()["data"]
        assert data["ready"] is (response.status_code == 200)
        assert "database" in data["checks"]
        assert "postgis" in data["checks"]


class TestResponseEnvelope:
    def test_success_envelope_shape(self, client: TestClient) -> None:
        body = client.get("/health").json()
        assert body["success"] is True
        assert "data" in body
        assert "trace_id" in body["meta"]
        assert "timestamp" in body["meta"]

    def test_unknown_route_returns_error_envelope(self, client: TestClient) -> None:
        response = client.get("/api/v1/does-not-exist")
        assert response.status_code == 404
        body = response.json()
        assert body["success"] is False
        assert body["error"]["code"] == "NOT_FOUND"
        assert body["error"]["message_key"].startswith("errors.")
        assert body["error"]["retriable"] is False

    def test_validation_error_lists_offending_fields(self, client: TestClient) -> None:
        response = client.post("/api/v1/auth/login", json={"identifier": "x"})
        assert response.status_code == 422
        error = response.json()["error"]
        assert error["code"] == "VALIDATION_ERROR"
        assert any(d["field"] == "password" for d in error["details"])

    def test_unknown_fields_are_rejected(self, client: TestClient) -> None:
        """extra='forbid': an unknown field is an error, not silently ignored."""
        response = client.post(
            "/api/v1/auth/login",
            json={"identifier": "a", "password": "b", "role": "ADMIN"},
        )
        assert response.status_code == 422


class TestPhaseBoundaries:
    """Unimplemented modules must say so, never return fabricated results."""

    def test_planned_endpoints_return_501(self, client: TestClient) -> None:
        # gis/*, reviews/*, advisory, followups and the official dashboard were
        # implemented in Phase 4-8 and moved out of this list; their own tests live in
        # test_gis.py, test_reviews.py, test_advisory.py, test_followups.py and
        # test_dashboards.py. Farmer/expert dashboards remain out of scope.
        for path in [
            "/api/v1/dashboards/farmer",
            "/api/v1/dashboards/expert",
        ]:
            response = client.get(path)
            assert response.status_code == 501, f"{path} should be 501"
            error = response.json()["error"]
            assert error["code"] == "NOT_IMPLEMENTED"
            assert error["details"][0]["planned_phase"].startswith("Phase")

    def test_planned_endpoints_return_no_data_payload(self, client: TestClient) -> None:
        """The failure mode this guards: a stub that returns plausible fake data."""
        body = client.get("/api/v1/dashboards/farmer").json()
        assert body["success"] is False
        assert "data" not in body

    def test_ai_analyze_does_not_fabricate_a_prediction(self, client: TestClient) -> None:
        """No auth header -> 401 first. The no-model case is covered with a real
        session in tests/integration/test_observation_pipeline.py, which is where an
        actual AI_MODEL_UNAVAILABLE response (not a fabricated prediction) is proven."""
        response = client.post("/api/v1/ai/analyze")
        assert response.status_code == 401
        assert "confidence" not in response.text
