from pathlib import Path
from typing import Any

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from tests.unit.fakes import FakeLlmClient

TOKEN = "/api/v1/auth/token"  # noqa: S105 - ścieżka, nie sekret
REGISTER = "/api/v1/auth/register"
OPTIONS = "/api/v1/auth/options"
PROTECTED = "/api/v1/dictionaries"


def _client(tmp_path: Path, **overrides: Any) -> TestClient:
    kw: dict[str, Any] = {
        "app_env": "development",
        "jwt_secret": "x" * 48,
        "api_user": "admin",
        "api_password_hash": PasswordHasher().hash("admin-haslo"),
        "users_db_path": tmp_path / "users.db",
        "_env_file": None,
    }
    kw.update(overrides)
    return TestClient(create_app(Settings(**kw), llm_client=FakeLlmClient([]), converter=None))


def _register(
    client: TestClient,
    username: str = "anna",
    password: str = "dlugie-haslo",  # noqa: S107 - dane testowe
) -> Any:
    return client.post(REGISTER, json={"username": username, "password": password})


def _login(client: TestClient, username: str, password: str) -> Any:
    return client.post(TOKEN, data={"username": username, "password": password})


def test_register_returns_token_that_opens_protected_routes(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        response = _register(client)
        assert response.status_code == 201
        token = response.json()["access_token"]
        protected = client.get(PROTECTED, headers={"Authorization": f"Bearer {token}"})
    assert protected.status_code == 200


def test_registered_user_can_log_in(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        _register(client)
        response = _login(client, "anna", "dlugie-haslo")
    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"  # noqa: S105


def test_registered_user_with_wrong_password_is_rejected(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        _register(client)
        response = _login(client, "anna", "zle-haslo-123")
    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_CREDENTIALS"


def test_technical_account_still_logs_in(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        response = _login(client, "admin", "admin-haslo")
    assert response.status_code == 200


def test_taken_username_is_conflict(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        _register(client)
        response = _register(client, "ANNA")
    assert response.status_code == 409
    assert response.json()["code"] == "USERNAME_TAKEN"


def test_technical_account_name_cannot_be_registered(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        response = _register(client, "Admin")
    assert response.status_code == 409
    assert response.json()["code"] == "USERNAME_TAKEN"


@pytest.mark.parametrize(
    ("username", "password"),
    [
        ("an", "dlugie-haslo"),  # login za krótki
        ("anna kowalska", "dlugie-haslo"),  # spacja w loginie
        ("anna", "krotkie"),  # hasło krótsze niż 8 znaków
        ("anna", "x" * 129),  # hasło dłuższe niż 128 znaków
    ],
)
def test_invalid_registration_data_is_rejected(
    tmp_path: Path, username: str, password: str
) -> None:
    with _client(tmp_path) as client:
        response = _register(client, username, password)
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


def test_registration_can_be_disabled(tmp_path: Path) -> None:
    with _client(tmp_path, registration_enabled=False) as client:
        response = _register(client)
        options = client.get(OPTIONS).json()
    assert response.status_code == 403
    assert response.json()["code"] == "REGISTRATION_DISABLED"
    assert options == {"registration_enabled": False}


def test_registration_needs_a_users_database(tmp_path: Path) -> None:
    with _client(tmp_path, users_db_path=None) as client:
        response = _register(client)
        options = client.get(OPTIONS).json()
    assert response.status_code == 403
    assert options == {"registration_enabled": False}


def test_options_report_enabled_registration(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        assert client.get(OPTIONS).json() == {"registration_enabled": True}
