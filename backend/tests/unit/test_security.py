"""Password hashing and JWT tests (TRD 13.1, 13.2)."""

from __future__ import annotations

import time
import uuid

import pytest

from app.core.errors import TokenExpiredError, ValidationError
from app.core.security import (
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    validate_password_strength,
    verify_password,
)


class TestPasswordHashing:
    def test_hash_is_not_plaintext(self) -> None:
        password = "correct-horse-battery"
        hashed = hash_password(password)
        assert password not in hashed
        assert hashed.startswith("$argon2id$"), "must use Argon2id per TRD 13.2"

    def test_hash_is_salted_so_two_hashes_differ(self) -> None:
        password = "correct-horse-battery"
        assert hash_password(password) != hash_password(password)

    def test_verify_accepts_correct_and_rejects_wrong(self) -> None:
        hashed = hash_password("correct-horse-battery")
        assert verify_password("correct-horse-battery", hashed) is True
        assert verify_password("wrong-password-here", hashed) is False

    def test_verify_against_missing_hash_returns_false(self) -> None:
        """A missing user must still cost a hash comparison (no timing oracle)."""
        assert verify_password("anything-at-all", None) is False

    def test_verify_missing_user_takes_comparable_time(self) -> None:
        """Guards the constant-time property in TRD 13.2.

        Generous bounds: this asserts the dummy-hash path is actually exercised, not a
        precise timing guarantee (which a shared CI runner cannot provide).
        """
        hashed = hash_password("correct-horse-battery")

        start = time.perf_counter()
        verify_password("wrong-password-here", hashed)
        real_user_duration = time.perf_counter() - start

        start = time.perf_counter()
        verify_password("wrong-password-here", None)
        missing_user_duration = time.perf_counter() - start

        assert missing_user_duration > real_user_duration / 10


class TestPasswordStrength:
    def test_rejects_too_short(self) -> None:
        with pytest.raises(ValidationError) as exc:
            validate_password_strength("short")
        assert exc.value.code == "VALIDATION_ERROR"

    def test_rejects_common_password(self) -> None:
        with pytest.raises(ValidationError):
            validate_password_strength("password123")

    def test_accepts_reasonable_password(self) -> None:
        validate_password_strength("a-reasonable-farmer-password")


class TestAccessTokens:
    def test_roundtrip_carries_claims(self) -> None:
        user_id = uuid.uuid4()
        token, expires_in = create_access_token(user_id=user_id, role="FARMER")
        payload = decode_access_token(token)

        assert payload["sub"] == str(user_id)
        assert payload["role"] == "FARMER"
        assert payload["type"] == "access"
        assert "jti" in payload
        assert expires_in > 0

    def test_tampered_token_is_rejected(self) -> None:
        from app.core.errors import AuthenticationError

        token, _ = create_access_token(user_id=uuid.uuid4(), role="FARMER")
        tampered = token[:-4] + ("aaaa" if not token.endswith("aaaa") else "bbbb")
        with pytest.raises(AuthenticationError):
            decode_access_token(tampered)

    def test_expired_token_raises_expired_not_generic(self, monkeypatch) -> None:
        """The client must be able to tell "refresh me" from "you are not allowed"."""
        from app.core import security

        monkeypatch.setattr(security.settings, "JWT_ACCESS_TTL_MIN", -1)
        token, _ = create_access_token(user_id=uuid.uuid4(), role="FARMER")
        with pytest.raises(TokenExpiredError):
            decode_access_token(token)

    def test_refresh_token_cannot_be_used_as_access_token(self) -> None:
        """A refresh token is opaque, so it can never decode as an access token."""
        from app.core.errors import AuthenticationError

        raw, _ = generate_refresh_token()
        with pytest.raises(AuthenticationError):
            decode_access_token(raw)


class TestRefreshTokens:
    def test_only_the_hash_is_storable(self) -> None:
        raw, hashed = generate_refresh_token()
        assert raw != hashed
        assert len(hashed) == 64, "sha256 hex digest"
        assert hash_refresh_token(raw) == hashed

    def test_tokens_are_unique(self) -> None:
        tokens = {generate_refresh_token()[0] for _ in range(50)}
        assert len(tokens) == 50
