"""Logi aplikacji na stdout w JSON, jedna linia na zdarzenie (spec §10.3, §12 LOG_LEVEL).

Uvicorn konfiguruje tylko własne loggery, więc bez tego komunikaty `app.*` poniżej
WARNING znikają. Logi zawierają wyłącznie metadane - moduły nie logują treści dokumentów.
"""

import json
import logging
import sys
from datetime import UTC, datetime

_HANDLER_NAME = "coi-cf-json"


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, object] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            entry["exc"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False)


def configure_logging(level: str) -> None:
    """Handler JSON na loggerze `app`; ponowne wywołanie zmienia tylko poziom."""
    logger = logging.getLogger("app")
    logger.setLevel(level)
    if any(h.get_name() == _HANDLER_NAME for h in logger.handlers):
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.set_name(_HANDLER_NAME)
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
