"""Weryfikacja JWT (`decode_access_token`) i POST /auth/token (spec §10.1)."""

from datetime import UTC, datetime, timedelta
from functools import cache
from typing import Any

import jwt
import pytest
from argon2 import PasswordHasher
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.errors import AppError, ErrorCode
from app.core.security import decode_access_token
from app.main import create_app
from tests.unit.fakes import FakeLlmClient

SECRET = "s" * 40
PASSWORD = "tajne-haslo"  # noqa: S105 - testowe hasło


@cache
def _rsa_pem() -> tuple[str, str]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    public = (
        key.public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )
    return private, public


def _hs256(**kw: Any) -> Settings:
    # HS256 = API wydaje tokeny, więc konfiguracja wymaga konta technicznego.
    account = {"api_user": "api", "api_password_hash": "$argon2id$nieuzywany"}
    return Settings(app_env="development", jwt_secret=SECRET, _env_file=None, **account | kw)


def _rs256(**kw: Any) -> Settings:
    return Settings(
        app_env="development",
        jwt_algorithm="RS256",
        jwt_public_key=_rsa_pem()[1],
        _env_file=None,
        **kw,
    )


def _claims(**overrides: Any) -> dict[str, Any]:
    now = datetime.now(UTC)
    claims: dict[str, Any] = {
        "sub": "jan",
        "iss": "coi-cf",
        "aud": "coi-cf-api",
        "iat": now,
        "exp": now + timedelta(minutes=5),
    }
    claims.update(overrides)
    return claims


def _hs_token(**overrides: Any) -> str:
    return jwt.encode(_claims(**overrides), SECRET, algorithm="HS256")


def _rs_token(**overrides: Any) -> str:
    return jwt.encode(_claims(**overrides), _rsa_pem()[0], algorithm="RS256")


def _code(settings: Settings, token: str) -> ErrorCode:
    with pytest.raises(AppError) as info:
        decode_access_token(settings, token)
    return info.value.code


def test_valid_token_gives_principal() -> None:
    assert decode_access_token(_hs256(), _hs_token()).subject == "jan"
    assert decode_access_token(_rs256(), _rs_token()).subject == "jan"


@pytest.mark.parametrize(
    "overrides",
    [
        {"exp": datetime.now(UTC) - timedelta(minutes=5)},  # wygasły (poza leeway 30 s)
        {"aud": "inna-usluga"},
        {"iss": "obcy-wystawca"},
    ],
    ids=["expired", "wrong_aud", "wrong_iss"],
)
def test_bad_claims_are_invalid_token(overrides: dict[str, Any]) -> None:
    assert _code(_hs256(), _hs_token(**overrides)) is ErrorCode.INVALID_TOKEN


def test_hs256_token_rejected_by_rs256_config() -> None:
    # Klasyczny atak: token HS256 podpisany kluczem publicznym RSA jako sekretem.
    forged = jwt.encode(_claims(), "x" * 40, algorithm="HS256")
    assert _code(_rs256(), forged) is ErrorCode.INVALID_TOKEN


def test_rs256_token_rejected_by_hs256_config() -> None:
    assert _code(_hs256(), _rs_token()) is ErrorCode.INVALID_TOKEN


def test_roles_from_nested_claim() -> None:
    settings = _rs256(jwt_roles_claim="realm_access.roles", jwt_required_role="coi")
    token = _rs_token(realm_access={"roles": ["inna", "coi"]})
    assert decode_access_token(settings, token).roles == {"inna", "coi"}


def test_roles_from_space_separated_string() -> None:
    settings = _hs256(jwt_required_role="coi")
    assert decode_access_token(settings, _hs_token(roles="czytelnik coi")).roles == {
        "czytelnik",
        "coi",
    }


def test_missing_role_is_forbidden() -> None:
    settings = _hs256(jwt_required_role="coi")
    with pytest.raises(AppError) as info:
        decode_access_token(settings, _hs_token(roles=["czytelnik"]))
    assert info.value.code is ErrorCode.FORBIDDEN and info.value.status == 403


@pytest.mark.parametrize(
    ("username", "password"),
    [("nieznany", PASSWORD), ("api", "zle-haslo")],
    ids=["bad_user", "bad_password"],
)
def test_token_endpoint_rejects_bad_credentials(username: str, password: str) -> None:
    settings = _hs256(api_user="api", api_password_hash=PasswordHasher().hash(PASSWORD))
    with TestClient(create_app(settings, llm_client=FakeLlmClient([]), converter=None)) as client:
        response = client.post(
            "/api/v1/auth/token", data={"username": username, "password": password}
        )
        ok = client.post("/api/v1/auth/token", data={"username": "api", "password": PASSWORD})
    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_CREDENTIALS"
    assert ok.status_code == 200
