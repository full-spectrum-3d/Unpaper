"""Eksport schematu OpenAPI backendu do pliku (argument: ścieżka wyjściowa).

Ustawienia są stałe i fikcyjne: eksport nie może zależeć od `.env` ani zmiennych
środowiskowych (inaczej schemat różniłby się między maszynami, np. brak `/auth`
przy AUTH_ENABLED=false) i nie używa prawdziwych sekretów. Stała wartość = determinizm.
"""

import json
import os
import sys
from pathlib import Path

from app.core.config import Settings
from app.main import create_app

# Settings czyta też zmienne środowiskowe - usuwamy te, które pasują do jego pól.
for _name in Settings.model_fields:
    for _key in [k for k in os.environ if k.lower() == _name]:
        del os.environ[_key]

settings = Settings(
    _env_file=None,
    _secrets_dir=None,
    jwt_secret="openapi-export-" + "x" * 32,
    api_user="openapi",
    api_password_hash="$argon2id$v=19$m=65536,t=3,p=4$b3BlbmFwaQ$b3BlbmFwaQ",
)
spec = create_app(settings).openapi()
Path(sys.argv[1]).write_text(
    json.dumps(spec, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8"
)
