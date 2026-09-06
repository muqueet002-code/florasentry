"""Structured operational logging (TRD 33.2).

Operational logs answer "is the system working?" and go to stdout as JSON.
Business audit logs are a separate concern and live in the `audit_logs` table (TRD 33.1).

Redaction (TRD 33.3) is applied to every record: no password, secret, token, key,
authorization header, phone number or email may reach the log stream.
"""

from __future__ import annotations

import json
import logging
import re
import sys
from contextvars import ContextVar
from typing import Any

from app.core.config import settings

# Correlates every log line, audit row and API response for one request (TRD 33.2).
trace_id_ctx: ContextVar[str] = ContextVar("trace_id", default="-")

SENSITIVE_KEY_RE = re.compile(
    r"(password|secret|token|api[_-]?key|authorization|phone|email)", re.IGNORECASE
)
REDACTED = "[REDACTED]"

_RESERVED = {
    "name",
    "msg",
    "args",
    "levelname",
    "levelno",
    "pathname",
    "filename",
    "module",
    "exc_info",
    "exc_text",
    "stack_info",
    "lineno",
    "funcName",
    "created",
    "msecs",
    "relativeCreated",
    "thread",
    "threadName",
    "processName",
    "process",
    "taskName",
    "message",
    "asctime",
}


def redact(value: Any) -> Any:
    """Recursively redact sensitive keys from a structure before it is logged."""
    if isinstance(value, dict):
        return {
            k: (REDACTED if SENSITIVE_KEY_RE.search(str(k)) else redact(v))
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact(v) for v in value]
    return value


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S.%03dZ"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "trace_id": trace_id_ctx.get(),
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            # Exception type only. Stack traces stay out of the structured field and
            # are never returned to clients (TRD 6.5).
            payload["exc_type"] = record.exc_info[0].__name__ if record.exc_info[0] else None
            payload["exc_detail"] = self.formatException(record.exc_info)
        return json.dumps(redact(payload), default=str)


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        for key in list(record.__dict__):
            if key not in _RESERVED and SENSITIVE_KEY_RE.search(key):
                record.__dict__[key] = REDACTED
        return True


def configure_logging() -> None:
    """Idempotently configure root logging for the process."""
    root = logging.getLogger()
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    if settings.LOG_FORMAT == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)-8s %(name)s :: %(message)s")
        )
    handler.addFilter(RedactingFilter())

    root.addHandler(handler)
    root.setLevel(settings.LOG_LEVEL.upper())

    # uvicorn's own access log duplicates our request middleware log line.
    logging.getLogger("uvicorn.access").disabled = True
    logging.getLogger("uvicorn.error").propagate = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
