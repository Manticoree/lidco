"""Structured logging setup for LIDCO.

Provides two output formats:
- ``pretty``: Human-readable coloured output (default for interactive use)
- ``json``: Machine-parseable JSON lines for log aggregators / production

Usage::

    from lidco.core.logging import setup_logging
    setup_logging(format="json", level="INFO")
"""

from __future__ import annotations

import json
import logging
import sys
from typing import Any


class _JsonFormatter(logging.Formatter):
    """Emit one JSON object per log record.

    Output format::

        {"ts": "2024-01-01T12:00:00.000Z", "level": "INFO",
         "logger": "lidco.agents.graph", "msg": "...",
         "session_id": "...", "agent_name": "coder", ...}

    Extra fields set on the ``LogRecord`` (e.g. via ``extra=`` kwarg to the
    logger) are merged into the top-level JSON object.
    """

    _RESERVED = frozenset(
        {
            "args",
            "created",
            "exc_info",
            "exc_text",
            "filename",
            "funcName",
            "levelname",
            "levelno",
            "lineno",
            "message",
            "module",
            "msecs",
            "msg",
            "name",
            "pathname",
            "process",
            "processName",
            "relativeCreated",
            "stack_info",
            "taskName",
            "thread",
            "threadName",
        }
    )

    def format(self, record: logging.LogRecord) -> str:
        record.message = record.getMessage()
        ts = self.formatTime(record, "%Y-%m-%dT%H:%M:%S")
        # Include milliseconds
        ts = f"{ts}.{record.msecs:03.0f}Z"

        obj: dict[str, Any] = {
            "ts": ts,
            "level": record.levelname,
            "logger": record.name,
            "msg": record.message,
        }

        # Merge extra fields (skip internal LogRecord attrs)
        for key, val in record.__dict__.items():
            if key not in self._RESERVED and not key.startswith("_"):
                obj[key] = val

        if record.exc_info:
            obj["exc"] = self.formatException(record.exc_info)

        return json.dumps(obj, default=str)


def setup_logging(
    format: str = "pretty",
    level: str = "INFO",
    log_file: str = "",
) -> None:
    """Configure root logging for LIDCO.

    Args:
        format: ``"pretty"`` for human-readable output, ``"json"`` for JSON lines.
        level: Log level string (``"DEBUG"``, ``"INFO"``, ``"WARNING"``, etc.).
        log_file: Optional path to write logs to in addition to stderr. Empty =
            stderr only.
    """
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    handlers: list[logging.Handler] = []

    stderr_handler = logging.StreamHandler(sys.stderr)
    if format == "json":
        stderr_handler.setFormatter(_JsonFormatter())
    else:
        stderr_handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt="%H:%M:%S",
            )
        )
    handlers.append(stderr_handler)

    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(_JsonFormatter())  # always JSON in files
        handlers.append(file_handler)

    logging.basicConfig(
        level=numeric_level,
        handlers=handlers,
        force=True,  # override any previously set handlers
    )

    # Silence noisy third-party loggers regardless of level
    for noisy in ("httpx", "httpcore", "openai", "litellm", "LiteLLM", "chromadb"):
        logging.getLogger(noisy).setLevel(logging.ERROR)
