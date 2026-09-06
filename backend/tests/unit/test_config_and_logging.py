"""Configuration validation and log redaction tests (TRD 33.3, 36.10)."""

from __future__ import annotations

import pytest

from app.core.config import EXAMPLE_JWT_SECRET, Settings
from app.core.logging import REDACTED, redact


class TestStartupValidation:
    """A misconfigured system must not start and pretend to work (TRD 36.10)."""

    def test_production_rejects_the_example_secret(self) -> None:
        with pytest.raises(Exception, match="JWT_SECRET"):
            Settings(APP_ENV="production", JWT_SECRET=EXAMPLE_JWT_SECRET)

    def test_production_rejects_short_secret(self) -> None:
        with pytest.raises(Exception, match="JWT_SECRET"):
            Settings(APP_ENV="production", JWT_SECRET="too-short")

    def test_production_rejects_debug_true(self) -> None:
        with pytest.raises(Exception, match="DEBUG"):
            Settings(APP_ENV="production", JWT_SECRET="x" * 40, DEBUG=True)

    def test_wildcard_cors_is_rejected_in_every_environment(self) -> None:
        with pytest.raises(Exception, match="CORS"):
            Settings(APP_ENV="local", CORS_ALLOWED_ORIGINS="*")

    def test_local_permits_relaxed_values(self) -> None:
        settings = Settings(APP_ENV="local", JWT_SECRET=EXAMPLE_JWT_SECRET, DEBUG=True)
        assert settings.is_local

    def test_default_language_must_be_supported(self) -> None:
        with pytest.raises(Exception, match="DEFAULT_LANGUAGE"):
            Settings(DEFAULT_LANGUAGE="fr", SUPPORTED_LANGUAGES="en,hi,mr")


class TestBoundingBox:
    def test_malformed_bbox_is_rejected(self) -> None:
        with pytest.raises(Exception, match="GIS_OPERATING_BBOX"):
            Settings(GIS_OPERATING_BBOX="1,2,3")

    def test_inverted_bbox_is_rejected(self) -> None:
        with pytest.raises(Exception, match="GIS_OPERATING_BBOX"):
            Settings(GIS_OPERATING_BBOX="80,22,72,15")

    def test_valid_bbox_parses(self) -> None:
        settings = Settings(GIS_OPERATING_BBOX="72.6,15.6,80.9,22.1")
        assert settings.operating_bbox == (72.6, 15.6, 80.9, 22.1)


class TestLogRedaction:
    """Passwords, tokens and personal identifiers must never reach the log stream."""

    @pytest.mark.parametrize(
        "key",
        [
            "password",
            "Password",
            "new_password",
            "secret",
            "jwt_secret",
            "token",
            "refresh_token",
            "api_key",
            "authorization",
            "phone",
            "email",
        ],
    )
    def test_sensitive_keys_are_redacted(self, key: str) -> None:
        assert redact({key: "sensitive-value"})[key] == REDACTED

    def test_nested_structures_are_redacted(self) -> None:
        payload = {
            "user": {"full_name": "Kept", "password": "secret", "phone": "+919999999999"},
            "items": [{"token": "abc"}, {"safe": "kept"}],
        }
        result = redact(payload)
        assert result["user"]["full_name"] == "Kept"
        assert result["user"]["password"] == REDACTED
        assert result["user"]["phone"] == REDACTED
        assert result["items"][0]["token"] == REDACTED
        assert result["items"][1]["safe"] == "kept"

    def test_non_sensitive_values_survive(self) -> None:
        payload = {"observation_id": "abc-123", "status": "PROCESSING", "count": 3}
        assert redact(payload) == payload
