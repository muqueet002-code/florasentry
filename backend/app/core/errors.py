"""Exception hierarchy and error codes (TRD 6.5, 11.3, 11.4).

Every error reaching a client is converted into the standard envelope. Stack traces
are never returned; they are logged against the request's trace_id instead.
"""

from __future__ import annotations

from typing import Any


class FloraSentryError(Exception):
    """Base class. `status_code` and `code` drive the HTTP response."""

    status_code: int = 500
    code: str = "INTERNAL_ERROR"
    message: str = "An unexpected error occurred."
    message_key: str = "errors.internal"
    retriable: bool = True

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        details: list[dict[str, Any]] | None = None,
        message_key: str | None = None,
    ) -> None:
        self.message = message or self.message
        self.code = code or self.code
        self.message_key = message_key or self.message_key
        self.details = details or []
        super().__init__(self.message)


# ---- 4xx ---------------------------------------------------------------------


class ValidationError(FloraSentryError):
    status_code = 422
    code = "VALIDATION_ERROR"
    message = "Request validation failed."
    message_key = "errors.validation"
    retriable = False


class AuthenticationError(FloraSentryError):
    status_code = 401
    code = "AUTH_REQUIRED"
    message = "Authentication required."
    message_key = "errors.auth_required"
    retriable = False


class InvalidCredentialsError(AuthenticationError):
    code = "AUTH_INVALID_CREDENTIALS"
    # Deliberately identical for unknown-user and wrong-password (TRD 29.1).
    message = "Invalid credentials."
    message_key = "errors.auth_invalid_credentials"


class TokenExpiredError(AuthenticationError):
    code = "AUTH_TOKEN_EXPIRED"
    message = "Access token has expired."
    message_key = "errors.auth_token_expired"
    retriable = True  # the client should refresh and retry


class AuthorizationError(FloraSentryError):
    status_code = 403
    code = "FORBIDDEN_ROLE"
    message = "Your role does not permit this action."
    message_key = "errors.forbidden_role"
    retriable = False


class OwnershipError(AuthorizationError):
    code = "FORBIDDEN_OWNERSHIP"
    message = "This record belongs to another user."
    message_key = "errors.forbidden_ownership"


class NotFoundError(FloraSentryError):
    status_code = 404
    code = "NOT_FOUND"
    message = "Resource not found."
    message_key = "errors.not_found"
    retriable = False

    def __init__(self, entity: str = "Resource", **kwargs: Any) -> None:
        code = kwargs.pop("code", f"{entity.upper().replace(' ', '_')}_NOT_FOUND")
        super().__init__(
            f"{entity} not found.",
            code=code,
            message_key=f"errors.{entity.lower().replace(' ', '_')}_not_found",
            **kwargs,
        )


class ConflictError(FloraSentryError):
    status_code = 409
    code = "CONFLICT"
    message = "The request conflicts with the current state."
    message_key = "errors.conflict"
    retriable = False


class LastAdminError(ConflictError):
    code = "LAST_ADMIN"
    message = "Cannot remove the last remaining administrator."
    message_key = "errors.last_admin"


class RateLimitError(FloraSentryError):
    status_code = 429
    code = "RATE_LIMITED"
    message = "Too many requests."
    message_key = "errors.rate_limited"
    retriable = True


class NotImplementedForPhaseError(FloraSentryError):
    """A route boundary that exists but whose module lands in a later phase.

    This is deliberately explicit: the endpoint states that it is not implemented
    rather than returning a fabricated result (Phase 1 rule: no fake endpoints).
    """

    status_code = 501
    code = "NOT_IMPLEMENTED"
    message = "This endpoint is not implemented yet."
    message_key = "errors.not_implemented"
    retriable = False

    def __init__(self, feature: str, phase: str) -> None:
        super().__init__(
            f"'{feature}' is not implemented in the current build. Planned for {phase}.",
            details=[{"feature": feature, "planned_phase": phase}],
        )


# ---- 5xx ---------------------------------------------------------------------


class ExternalServiceError(FloraSentryError):
    status_code = 503
    code = "EXTERNAL_SERVICE_UNAVAILABLE"
    message = "An external service is unavailable."
    message_key = "errors.external_unavailable"
    retriable = True


class StorageUnavailableError(ExternalServiceError):
    code = "STORAGE_UNAVAILABLE"
    message = "Image storage is unavailable."
    message_key = "errors.storage_unavailable"


class DatabaseUnavailableError(FloraSentryError):
    status_code = 503
    code = "DATABASE_UNAVAILABLE"
    message = "The database is unavailable."
    message_key = "errors.database_unavailable"
    retriable = True


class InternalError(FloraSentryError):
    status_code = 500
    code = "INTERNAL_ERROR"
    message = "An unexpected error occurred."
    message_key = "errors.internal"
    retriable = True
