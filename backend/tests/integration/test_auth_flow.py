"""End-to-end authentication and authorization tests (TRD 12.1, 13).

Covers the full flow against a real database: register, login, protected access,
refresh rotation with reuse detection, password change, and RBAC enforcement.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.rbac import UserRole

pytestmark = pytest.mark.integration

REGISTRATION = {
    "full_name": "Test Farmer",
    "phone": "+919812345678",
    "password": "a-strong-farmer-password",
    "preferred_language": "mr",
}


class TestRegistration:
    def test_register_creates_farmer_with_tokens(self, db_client: TestClient) -> None:
        response = db_client.post("/api/v1/auth/register", json=REGISTRATION)
        assert response.status_code == 201
        data = response.json()["data"]
        assert data["user"]["role"] == "FARMER"
        assert data["user"]["preferred_language"] == "mr"
        assert data["tokens"]["access_token"]
        assert data["tokens"]["refresh_token"]

    def test_password_is_never_returned(self, db_client: TestClient) -> None:
        response = db_client.post("/api/v1/auth/register", json=REGISTRATION)
        assert "password" not in response.text.lower().replace("password_hash", "")

    def test_duplicate_phone_is_rejected(self, db_client: TestClient) -> None:
        db_client.post("/api/v1/auth/register", json=REGISTRATION)
        response = db_client.post("/api/v1/auth/register", json=REGISTRATION)
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "DUPLICATE_PHONE"

    def test_cannot_self_register_a_privileged_role(self, db_client: TestClient) -> None:
        """Privilege escalation guard: `role` is not an accepted field (TRD 12.1)."""
        response = db_client.post("/api/v1/auth/register", json={**REGISTRATION, "role": "ADMIN"})
        assert response.status_code == 422

    def test_weak_password_is_rejected(self, db_client: TestClient) -> None:
        response = db_client.post(
            "/api/v1/auth/register", json={**REGISTRATION, "password": "password123"}
        )
        assert response.status_code == 422

    def test_password_is_stored_only_as_a_hash(
        self, db_client: TestClient, db_session: Session
    ) -> None:
        db_client.post("/api/v1/auth/register", json=REGISTRATION)
        stored = db_session.execute(
            text("SELECT password_hash FROM users WHERE phone = :p"),
            {"p": REGISTRATION["phone"]},
        ).scalar_one()
        assert stored != REGISTRATION["password"]
        assert stored.startswith("$argon2id$")


class TestLogin:
    def _register(self, client: TestClient) -> None:
        assert client.post("/api/v1/auth/register", json=REGISTRATION).status_code == 201

    def test_login_with_phone_succeeds(self, db_client: TestClient) -> None:
        self._register(db_client)
        response = db_client.post(
            "/api/v1/auth/login",
            json={"identifier": REGISTRATION["phone"], "password": REGISTRATION["password"]},
        )
        assert response.status_code == 200
        assert response.json()["data"]["access_token"]

    def test_wrong_password_is_rejected(self, db_client: TestClient) -> None:
        self._register(db_client)
        response = db_client.post(
            "/api/v1/auth/login",
            json={"identifier": REGISTRATION["phone"], "password": "wrong-password-xyz"},
        )
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "AUTH_INVALID_CREDENTIALS"

    def test_unknown_user_gives_identical_error(self, db_client: TestClient) -> None:
        """No user-existence disclosure (TRD 13.2)."""
        self._register(db_client)
        unknown = db_client.post(
            "/api/v1/auth/login",
            json={"identifier": "+910000000000", "password": "whatever-password"},
        )
        wrong = db_client.post(
            "/api/v1/auth/login",
            json={"identifier": REGISTRATION["phone"], "password": "wrong-password-xyz"},
        )
        assert unknown.status_code == wrong.status_code == 401
        assert unknown.json()["error"] == wrong.json()["error"]

    def test_login_failure_is_audited(self, db_client: TestClient, db_session: Session) -> None:
        self._register(db_client)
        db_client.post(
            "/api/v1/auth/login",
            json={"identifier": REGISTRATION["phone"], "password": "wrong-password-xyz"},
        )
        count = db_session.execute(
            text("SELECT count(*) FROM audit_logs WHERE action = 'LOGIN_FAILURE'")
        ).scalar_one()
        assert count >= 1

    def test_audit_log_never_stores_the_password(
        self, db_client: TestClient, db_session: Session
    ) -> None:
        self._register(db_client)
        db_client.post(
            "/api/v1/auth/login",
            json={"identifier": REGISTRATION["phone"], "password": REGISTRATION["password"]},
        )
        rows = (
            db_session.execute(
                text(
                    "SELECT coalesce(after_state::text,'') || coalesce(before_state::text,'') "
                    "FROM audit_logs"
                )
            )
            .scalars()
            .all()
        )
        assert all(REGISTRATION["password"] not in row for row in rows)


class TestProtectedAccess:
    def _tokens(self, client: TestClient) -> dict:
        client.post("/api/v1/auth/register", json=REGISTRATION)
        return client.post(
            "/api/v1/auth/login",
            json={"identifier": REGISTRATION["phone"], "password": REGISTRATION["password"]},
        ).json()["data"]

    def test_me_requires_authentication(self, db_client: TestClient) -> None:
        response = db_client.get("/api/v1/auth/me")
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "AUTH_REQUIRED"

    def test_me_returns_principal_and_permissions(self, db_client: TestClient) -> None:
        tokens = self._tokens(db_client)
        response = db_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["user"]["role"] == "FARMER"
        assert data["farmer_id"] is not None
        assert "create_observation" in data["permissions"]
        assert "manage_users" not in data["permissions"]

    def test_garbage_token_is_rejected(self, db_client: TestClient) -> None:
        response = db_client.get(
            "/api/v1/auth/me", headers={"Authorization": "Bearer not-a-real-token"}
        )
        assert response.status_code == 401


class TestRefreshRotation:
    def _tokens(self, client: TestClient) -> dict:
        client.post("/api/v1/auth/register", json=REGISTRATION)
        return client.post(
            "/api/v1/auth/login",
            json={"identifier": REGISTRATION["phone"], "password": REGISTRATION["password"]},
        ).json()["data"]

    def test_refresh_issues_a_new_pair(self, db_client: TestClient) -> None:
        tokens = self._tokens(db_client)
        response = db_client.post(
            "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        )
        assert response.status_code == 200
        assert response.json()["data"]["refresh_token"] != tokens["refresh_token"]

    def test_reusing_a_rotated_token_is_detected_and_kills_the_chain(
        self, db_client: TestClient, db_session: Session
    ) -> None:
        """TRD 13.1 reuse detection: assume compromise, revoke everything."""
        tokens = self._tokens(db_client)
        original = tokens["refresh_token"]

        first = db_client.post("/api/v1/auth/refresh", json={"refresh_token": original})
        assert first.status_code == 200
        new_token = first.json()["data"]["refresh_token"]

        replay = db_client.post("/api/v1/auth/refresh", json={"refresh_token": original})
        assert replay.status_code == 401
        assert replay.json()["error"]["code"] == "AUTH_REFRESH_REVOKED"

        # The newly issued token is revoked too, because the chain is assumed compromised.
        after = db_client.post("/api/v1/auth/refresh", json={"refresh_token": new_token})
        assert after.status_code == 401

        # Two detections, not one: presenting the replacement token after the chain
        # was revoked is itself a presentation of a revoked token, so it trips the
        # detector again. That is the intended behaviour - every use of a revoked
        # token is recorded.
        detected = db_session.execute(
            text("SELECT count(*) FROM audit_logs WHERE action='REFRESH_TOKEN_REUSE_DETECTED'")
        ).scalar_one()
        assert detected == 2

    def test_logout_revokes_the_token(self, db_client: TestClient) -> None:
        tokens = self._tokens(db_client)
        assert (
            db_client.post(
                "/api/v1/auth/logout", json={"refresh_token": tokens["refresh_token"]}
            ).status_code
            == 204
        )
        assert (
            db_client.post(
                "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
            ).status_code
            == 401
        )

    def test_only_the_hash_is_stored(self, db_client: TestClient, db_session: Session) -> None:
        tokens = self._tokens(db_client)
        hashes = db_session.execute(text("SELECT token_hash FROM refresh_tokens")).scalars().all()
        assert tokens["refresh_token"] not in hashes


class TestPasswordChange:
    def _access(self, client: TestClient) -> str:
        client.post("/api/v1/auth/register", json=REGISTRATION)
        return client.post(
            "/api/v1/auth/login",
            json={"identifier": REGISTRATION["phone"], "password": REGISTRATION["password"]},
        ).json()["data"]["access_token"]

    def test_requires_the_correct_current_password(self, db_client: TestClient) -> None:
        token = self._access(db_client)
        response = db_client.post(
            "/api/v1/auth/change-password",
            headers={"Authorization": f"Bearer {token}"},
            json={"current_password": "wrong-one-here", "new_password": "another-good-one"},
        )
        assert response.status_code == 401

    def test_successful_change_allows_new_password_only(self, db_client: TestClient) -> None:
        token = self._access(db_client)
        assert (
            db_client.post(
                "/api/v1/auth/change-password",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "current_password": REGISTRATION["password"],
                    "new_password": "brand-new-strong-password",
                },
            ).status_code
            == 200
        )

        assert (
            db_client.post(
                "/api/v1/auth/login",
                json={"identifier": REGISTRATION["phone"], "password": REGISTRATION["password"]},
            ).status_code
            == 401
        )
        assert (
            db_client.post(
                "/api/v1/auth/login",
                json={
                    "identifier": REGISTRATION["phone"],
                    "password": "brand-new-strong-password",
                },
            ).status_code
            == 200
        )


class TestRoleEnforcement:
    """Unauthorized (401) and forbidden (403) must be distinct and both enforced."""

    def test_unauthenticated_field_creation_is_401(self, db_client: TestClient) -> None:
        response = db_client.post(
            "/api/v1/fields", json={"name": "F", "latitude": 19.0, "longitude": 75.0}
        )
        assert response.status_code == 401

    def test_official_cannot_create_a_field(
        self, db_client: TestClient, make_user, auth_headers
    ) -> None:
        official = make_user(UserRole.OFFICIAL)
        response = db_client.post(
            "/api/v1/fields",
            headers=auth_headers(official),
            json={"name": "Not allowed", "latitude": 19.0, "longitude": 75.0},
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "FORBIDDEN_ROLE"

    def test_lab_expert_cannot_create_a_field(
        self, db_client: TestClient, make_user, auth_headers
    ) -> None:
        response = db_client.post(
            "/api/v1/fields",
            headers=auth_headers(make_user(UserRole.LAB_EXPERT)),
            json={"name": "Not allowed", "latitude": 19.0, "longitude": 75.0},
        )
        assert response.status_code == 403

    def test_farmer_can_create_a_field(
        self, db_client: TestClient, make_user, auth_headers
    ) -> None:
        response = db_client.post(
            "/api/v1/fields",
            headers=auth_headers(make_user(UserRole.FARMER)),
            json={"name": "North plot", "latitude": 19.0, "longitude": 75.0},
        )
        assert response.status_code == 201

    def test_deactivated_user_token_stops_working(
        self, db_client: TestClient, make_user, auth_headers, db_session: Session
    ) -> None:
        """A token can outlive deactivation; the account is re-checked per request."""
        user = make_user(UserRole.FARMER)
        headers = auth_headers(user)
        assert db_client.get("/api/v1/auth/me", headers=headers).status_code == 200

        user.is_active = False
        db_session.flush()

        response = db_client.get("/api/v1/auth/me", headers=headers)
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "AUTH_ACCOUNT_INACTIVE"
