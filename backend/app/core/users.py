"""Konta zarejestrowanych użytkowników w SQLite (obok konta technicznego z `.env`).

Plik bazy leży na wolumenie (`USERS_DB_PATH`), bo kontener API ma system plików tylko do
odczytu. Hasła przechowujemy wyłącznie jako hash argon2id. Każda operacja otwiera własne
połączenie: endpointy synchroniczne działają w puli wątków FastAPI.
"""

import sqlite3
from contextlib import closing
from functools import lru_cache
from pathlib import Path

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_password_hasher = PasswordHasher()

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    username TEXT PRIMARY KEY COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
)
"""


class UsernameTakenError(Exception):
    """Login jest już zajęty (bez rozróżniania wielkości liter)."""


@lru_cache(maxsize=1)
def _dummy_hash() -> str:
    """Hash porównawczy dla nieistniejącego loginu - wyrównuje czas odpowiedzi."""
    return _password_hasher.hash("nieistniejacy-uzytkownik")


class UserStore:
    def __init__(self, path: Path) -> None:
        self._path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as db, db:
            db.execute(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._path, timeout=5)

    def create(self, username: str, password: str) -> None:
        password_hash = _password_hasher.hash(password)
        try:
            with closing(self._connect()) as db, db:
                db.execute(
                    "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                    (username, password_hash),
                )
        except sqlite3.IntegrityError as exc:
            raise UsernameTakenError(username) from exc

    def verify(self, username: str, password: str) -> bool:
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT password_hash FROM users WHERE username = ?", (username,)
            ).fetchone()
        stored_hash = row[0] if row else _dummy_hash()
        ok: bool
        try:
            ok = _password_hasher.verify(stored_hash, password)
        except VerificationError, InvalidHashError:
            ok = False
        return ok and row is not None
