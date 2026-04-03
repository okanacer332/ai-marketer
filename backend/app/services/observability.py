from __future__ import annotations

import json
import logging
import time
from typing import Any


LOGGER_NAME = "acrtech.api"


def configure_observability() -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger


def get_logger() -> logging.Logger:
    return logging.getLogger(LOGGER_NAME)


def now_perf() -> float:
    return time.perf_counter()


def duration_ms(started_at: float) -> int:
    return max(0, round((time.perf_counter() - started_at) * 1000))


def log_structured(
    event: str,
    *,
    level: str = "info",
    **fields: Any,
) -> None:
    logger = configure_observability()
    payload = {"event": event, **sanitize_log_fields(fields)}
    message = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    log_method = getattr(logger, level.lower(), logger.info)
    log_method(message)


def sanitize_log_fields(value: Any) -> Any:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                continue
            result[key] = sanitize_log_fields(item)
        return result
    if isinstance(value, list):
        return [sanitize_log_fields(item) for item in value[:64]]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if hasattr(value, "isoformat") and callable(value.isoformat):
        try:
            return value.isoformat()
        except Exception:
            return str(value)
    return str(value)
