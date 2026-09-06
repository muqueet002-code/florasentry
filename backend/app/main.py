"""FastAPI application factory (TRD 4.1, 6.1).

One process, one deployable, internally partitioned into modules. No microservices.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.health import router as health_router
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging import configure_logging, get_logger, trace_id_ctx
from app.core.responses import register_exception_handlers

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    logger.info(
        "application_starting",
        extra={
            "environment": settings.APP_ENV,
            "version": settings.APP_VERSION,
            "git_sha": settings.GIT_SHA,
        },
    )
    # Phase 2 loads the AI model here; Phase 3 warms the weather cache. Neither
    # exists yet, so nothing is loaded and nothing pretends to be.
    yield
    logger.info("application_stopping")


def create_app() -> FastAPI:
    configure_logging()

    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=(
            "FloraSentry V2 - crop health decision support.\n\n"
            "SIH26131 - Early detection and management of crop diseases and pest "
            "infestations. Team ASTRIX (S83).\n\n"
            "**Phase 1 build.** Implemented: authentication, RBAC, reference data, "
            "fields. Endpoints marked `[Phase N]` return HTTP 501 and never return "
            "simulated results."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # CORS: an explicit origin list, never "*" (enforced by config validation).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept-Language", "X-Request-Id"],
        expose_headers=["X-Trace-Id"],
        max_age=600,
    )

    @app.middleware("http")
    async def trace_and_log(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Assign a trace id, log one line per request, and echo the id to the client.

        The same trace id appears in every log line and audit row for this request, so
        a user reporting a problem can quote a single id that resolves the whole story.
        """
        trace_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        token = trace_id_ctx.set(trace_id)
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.error(
                "request_exception",
                extra={
                    "path": request.url.path,
                    "method": request.method,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                },
                exc_info=True,
            )
            raise
        finally:
            trace_id_ctx.reset(token)

        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        response.headers["X-Trace-Id"] = trace_id
        logger.info(
            "request_completed",
            extra={
                "path": request.url.path,
                "method": request.method,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
                "trace_id": trace_id,
            },
        )
        return response

    register_exception_handlers(app)

    # Health lives outside the versioned prefix so probes never depend on API version.
    app.include_router(health_router)
    app.include_router(api_router, prefix=settings.API_BASE_PATH)

    @app.get("/", include_in_schema=False)
    def root() -> dict[str, str]:
        return {
            "name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "phase": "Phase 1 - foundation",
            "docs": "/docs",
            "health": "/health",
        }

    return app


app = create_app()
