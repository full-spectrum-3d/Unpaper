"""Logi `app.*` w JSON na stdout (LOG_LEVEL)."""

import json
import logging

from app.core.logging import JsonFormatter, configure_logging


def test_json_formatter() -> None:
    record = logging.LogRecord("app.x", logging.INFO, __file__, 1, "plik=%s", ("abc",), None)
    entry = json.loads(JsonFormatter().format(record))
    assert entry["level"] == "INFO" and entry["logger"] == "app.x" and entry["msg"] == "plik=abc"


def test_configure_logging_is_idempotent() -> None:
    logger = logging.getLogger("app")
    before = list(logger.handlers)
    try:
        configure_logging("INFO")
        configure_logging("DEBUG")
        added = [h for h in logger.handlers if h not in before]
        assert len(added) <= 1 and logger.level == logging.DEBUG
    finally:
        for handler in logger.handlers[:]:
            if handler not in before:
                logger.removeHandler(handler)
        logger.setLevel(logging.NOTSET)
