"""Limit rozmiaru body działa przed uwierzytelnieniem (FastAPI czyta JSON przed zależnościami)."""

from collections.abc import Iterator

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from tests.unit.fakes import FakeLlmClient

VALIDATE = "/api/v1/forms/validate"
LIMIT = 2 * 1024 * 1024  # max_file_size_mb=1 + 1 MiB narzutu


@pytest.fixture
def client() -> Iterator[TestClient]:
    public = (
        rsa.generate_private_key(public_exponent=65537, key_size=2048)
        .public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )
    settings = Settings(
        app_env="development",
        jwt_algorithm="RS256",
        jwt_public_key=public,
        max_file_size_mb=1,
        _env_file=None,
    )
    with TestClient(create_app(settings, llm_client=FakeLlmClient([]), converter=None)) as c:
        yield c


def _json(size: int) -> bytes:
    return b'{"x":"' + b"a" * (size - 8) + b'"}'


def test_oversized_json_is_rejected_before_auth(client: TestClient) -> None:
    response = client.post(
        VALIDATE, content=_json(LIMIT + 1), headers={"Content-Type": "application/json"}
    )
    # Przy znanym Content-Length Starlette sam odpowiada 413 (text/plain), zanim zadziała handler.
    assert response.status_code == 413


def test_oversized_chunked_json_is_rejected(client: TestClient) -> None:
    body = _json(LIMIT + 1)
    chunks = (body[i : i + 65536] for i in range(0, len(body), 65536))
    response = client.post(VALIDATE, content=chunks, headers={"Content-Type": "application/json"})
    assert response.status_code == 413
    assert response.json()["code"] == "FILE_TOO_LARGE"


def test_small_body_still_needs_token(client: TestClient) -> None:
    response = client.post(VALIDATE, json={}, headers={"Content-Type": "application/json"})
    assert response.status_code == 401
