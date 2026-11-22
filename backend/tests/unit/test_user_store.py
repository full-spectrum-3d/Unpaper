from pathlib import Path

import pytest

from app.core.users import UsernameTakenError, UserStore


def test_created_user_can_be_verified(tmp_path: Path) -> None:
    store = UserStore(tmp_path / "users.db")
    store.create("anna", "dlugie-haslo")
    assert store.verify("anna", "dlugie-haslo")


def test_wrong_password_is_rejected(tmp_path: Path) -> None:
    store = UserStore(tmp_path / "users.db")
    store.create("anna", "dlugie-haslo")
    assert not store.verify("anna", "inne-haslo")


def test_unknown_user_is_rejected(tmp_path: Path) -> None:
    assert not UserStore(tmp_path / "users.db").verify("nikt", "dlugie-haslo")


def test_duplicate_username_is_rejected_case_insensitively(tmp_path: Path) -> None:
    store = UserStore(tmp_path / "users.db")
    store.create("anna", "dlugie-haslo")
    with pytest.raises(UsernameTakenError):
        store.create("Anna", "inne-haslo")


def test_users_survive_reopening(tmp_path: Path) -> None:
    UserStore(tmp_path / "users.db").create("anna", "dlugie-haslo")
    assert UserStore(tmp_path / "users.db").verify("anna", "dlugie-haslo")


def test_password_is_not_stored_in_plain_text(tmp_path: Path) -> None:
    db = tmp_path / "users.db"
    UserStore(db).create("anna", "dlugie-haslo")
    assert b"dlugie-haslo" not in db.read_bytes()
