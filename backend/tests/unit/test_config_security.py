"""Walidacja konfiguracji przy starcie: RODO_CLAUSE_URL, rola przy tokenach z brokera."""

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from pydantic import ValidationError

from app.core.config import Settings


def _public_pem() -> str:
    return (
        rsa.generate_private_key(public_exponent=65537, key_size=2048)
        .public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )


@pytest.mark.parametrize("url", ["javascript:alert(1)", "http://bip.example.org/rodo"])
def test_rodo_url_must_be_https(url: str) -> None:
    with pytest.raises(ValidationError, match="https://"):
        Settings(app_env="development", auth_enabled=False, rodo_clause_url=url, _env_file=None)


def test_empty_rodo_url_is_none() -> None:
    s = Settings(app_env="development", auth_enabled=False, rodo_clause_url=" ", _env_file=None)
    assert s.rodo_clause_url is None


def test_production_rs256_verify_only_requires_role() -> None:
    public = _public_pem()
    with pytest.raises(ValidationError, match="JWT_REQUIRED_ROLE"):
        Settings(jwt_algorithm="RS256", jwt_public_key=public, _env_file=None)
    s = Settings(
        jwt_algorithm="RS256", jwt_public_key=public, jwt_required_role="coi", _env_file=None
    )
    assert not s.token_issuing_enabled
