"""Standard API response envelope and exception handlers (TRD 11).

Success:  {success, data, meta[, warnings]}
Error:    {success: false, error: {code, message, message_key, details, retriable}, meta}
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Generic, TypeVar

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.errors import FloraSentryError, InternalError
from app.core.logging import get_logger, trace_id_ctx

logger = get_logger(__name__)

T = TypeVar("T")


class Pagination(BaseModel):
    page: int
    page_size: int
    total_items: int
    total_pages: int


class Meta(BaseModel):
    trace_id: str
    timestamp: datetime
    pagination: Pagination | None = None
    filters_applied: dict[str, Any] | None = None
    truncated: bool | None = None


class Warning_(BaseModel):
    """Degraded-success warning (TRD 11.5). A warning is not an error."""

    code: str
    message_key: str
    detail: dict[str, Any] | None = None


class ErrorBody(BaseModel):
    code: str
    message: str
    message_key: str
    details: list[dict[str, Any]] = Field(default_factory=list)
    retriable: bool


class SuccessResponse(BaseModel, Generic[T]):
    success: bool = True
    data: T
    meta: Meta
    warnings: list[Warning_] | None = None


class ErrorResponse(BaseModel):
    success: bool = False
    error: ErrorBody
    meta: Meta


def _meta(**kwargs: Any) -> dict[str, Any]:
    return {
        "trace_id": trace_id_ctx.get(),
        "timestamp": datetime.now(UTC).isoformat(),
        **kwargs,
    }


def success(
    data: Any,
    *,
    warnings: list[dict[str, Any]] | None = None,
    **meta_kwargs: Any,
) -> dict[str, Any]:
    """Wrap a payload in the success envelope."""
    body: dict[str, Any] = {"success": True, "data": data, "meta": _meta(**meta_kwargs)}
    if warnings:
        body["warnings"] = warnings
    return body


def paginated(
    items: list[Any], *, page: int, page_size: int, total_items: int, **meta_kwargs: Any
) -> dict[str, Any]:
    total_pages = (total_items + page_size - 1) // page_size if page_size else 0
    return success(
        items,
        pagination={
            "page": page,
            "page_size": page_size,
            "total_items": total_items,
            "total_pages": total_pages,
        },
        **meta_kwargs,
    )


def error_body(
    *, code: str, message: str, message_key: str, details: list[dict[str, Any]], retriable: bool
) -> dict[str, Any]:
    return {
        "success": False,
        "error": {
            "code": code,
            "message": message,
            "message_key": message_key,
            "details": details,
            "retriable": retriable,
        },
        "meta": _meta(),
    }


def register_exception_handlers(app: FastAPI) -> None:
    """Convert every exception class into the standard error envelope."""

    @app.exception_handler(FloraSentryError)
    async def _domain(_: Request, exc: FloraSentryError) -> JSONResponse:
        log = logger.warning if exc.status_code < 500 else logger.error
        log(
            "request_failed",
            extra={"error_code": exc.code, "status_code": exc.status_code},
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(
                code=exc.code,
                message=exc.message,
                message_key=exc.message_key,
                details=exc.details,
                retriable=exc.retriable,
            ),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            {
                "field": ".".join(str(p) for p in err.get("loc", []) if p != "body"),
                "issue": err.get("type", "invalid"),
                "message": err.get("msg", ""),
            }
            for err in exc.errors()
        ]
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=error_body(
                code="VALIDATION_ERROR",
                message="Request validation failed.",
                message_key="errors.validation",
                details=details,
                retriable=False,
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {
            401: "AUTH_REQUIRED",
            403: "FORBIDDEN_ROLE",
            404: "NOT_FOUND",
            405: "METHOD_NOT_ALLOWED",
        }.get(exc.status_code, "HTTP_ERROR")
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(
                code=code,
                message=str(exc.detail),
                message_key=f"errors.http_{exc.status_code}",
                details=[],
                retriable=exc.status_code >= 500,
            ),
        )

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        # Log with the trace_id; return a generic body. Never leak internals (TRD 6.5).
        logger.error("unhandled_exception", exc_info=exc)
        fallback = InternalError()
        return JSONResponse(
            status_code=500,
            content=error_body(
                code=fallback.code,
                message=fallback.message,
                message_key=fallback.message_key,
                details=[],
                retriable=True,
            ),
        )
