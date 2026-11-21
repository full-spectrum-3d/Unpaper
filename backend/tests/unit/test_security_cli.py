"""`python -m app.core.security hash-password --stdin` (scripts/init-env.sh)."""

import io

import pytest
from argon2 import PasswordHasher

from app.core import security


def test_hash_password_from_stdin(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("tajne hasło\n"))
    assert security.main(["hash-password", "--stdin"]) == 0
    hashed = capsys.readouterr().out.strip()
    assert hashed.startswith("$argon2id$")
    assert PasswordHasher().verify(hashed, "tajne hasło")


def test_hash_password_rejects_empty_stdin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("\n"))
    assert security.main(["hash-password", "--stdin"]) == 1
