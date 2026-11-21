"""POST /forms/convert i /forms/validate, GET /initial-data-sources - przez HTTP (spec §6)."""

import asyncio
import io
from typing import Any

import docx
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.pipeline.llm_client import LlmReply, LlmUnavailableError
from app.pipeline.verify import verify_form
from tests.unit.fakes import FakeLlmClient, fixture_reply

CONVERT = "/api/v1/forms/convert"
VALIDATE = "/api/v1/forms/validate"


def _settings(**kw: Any) -> Settings:
    return Settings(app_env="development", auth_enabled=False, _env_file=None, **kw)


def _client(
    replies: list[LlmReply | Exception] | None = None, **settings: Any
) -> tuple[TestClient, FakeLlmClient]:
    fake = FakeLlmClient(replies if replies is not None else [fixture_reply("wniosek1_valid")])
    app = create_app(_settings(**settings), llm_client=fake, converter=None)
    return TestClient(app), fake


def _docx() -> bytes:
    document = docx.Document()
    document.add_paragraph("Wójt Gminy Elbląg")
    document.add_heading("WNIOSEK O USTALENIE NUMERU PORZĄDKOWEGO", level=1)
    document.add_paragraph("w miejscowości ……………… przy ulicy ………………")
    document.add_paragraph("nr ewidencyjny działki ……………… w obrębie ………………")
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def _post(
    client: TestClient, name: str = "wniosek.docx", data: bytes | None = None, **params: Any
) -> Any:
    files = {"file": (name, _docx() if data is None else data, "application/octet-stream")}
    return client.post(CONVERT, files=files, params=params)


def test_convert_returns_valid_import_json() -> None:
    client, fake = _client()
    with client:
        response = _post(client)
    assert response.status_code == 200, response.text
    form = response.json()
    assert form["title"] == "Wniosek o ustalenie numeru porządkowego nieruchomości"
    assert [tab["type"] for tab in form["tabs"]][-1] == "FINISH"
    assert verify_form(form, autofix=False).valid
    assert int(response.headers["X-Conversion-Warnings"]) >= 0
    assert "<dokument>" in fake.calls[0]["messages"][-1]["content"]


def test_convert_with_report() -> None:
    client, _ = _client()
    with client:
        response = _post(client, report="true")
    body = response.json()
    assert set(body) == {"form", "report"}
    report = body["report"]
    assert report["sourceFile"]["name"] == "wniosek.docx"
    assert report["extraction"]["method"] == "docx"
    assert report["llm"]["model"] == "qwen3:8b" and report["llm"]["fallback"] is False
    assert report["stats"]["tabs"] == len(body["form"]["tabs"]) >= 2
    assert report["stats"]["fields"] > 0 and report["durationMs"] >= 0
    assert set(report["timings"]) == {"normalizeMs", "extractMs", "analyzeMs", "buildMs"}
    assert int(response.headers["X-Conversion-Warnings"]) == len(report["warnings"])


def test_llm_unavailable_still_returns_form() -> None:
    client, _ = _client([LlmUnavailableError("brak serwera")])
    with client:
        response = _post(client, report="true")
    assert response.status_code == 200
    report = response.json()["report"]
    codes = [w["code"] for w in report["warnings"]]
    assert report["llm"]["fallback"] is True and codes[0] == "W01_LLM_FALLBACK"
    assert "W24_RULE_BASED_DRAFT" in codes  # pola z wykropkowań zamiast pustego szkieletu
    assert verify_form(response.json()["form"], autofix=False).valid


@pytest.mark.parametrize(
    ("name", "data", "status", "code"),
    [
        ("wniosek.exe", b"MZ\x90\x00", 415, "UNSUPPORTED_EXTENSION"),
        ("wniosek:1.docx", None, 400, "FILENAME_FORBIDDEN_CHARS"),
        ("a" * 251 + ".pdf", b"%PDF-1.7", 400, "FILENAME_TOO_LONG"),
        ("wniosek.pdf", None, 415, "MIME_MISMATCH"),
    ],
)
def test_invalid_upload_is_problem_json(
    name: str, data: bytes | None, status: int, code: str
) -> None:
    client, fake = _client([])
    with client:
        response = _post(client, name=name, data=data)
    assert response.status_code == status
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == code and fake.calls == []


def test_missing_file_field() -> None:
    client, _ = _client([])
    with client:
        response = client.post(CONVERT, files={"other": ("a.pdf", b"%PDF", "application/pdf")})
    assert response.status_code == 400 and response.json()["code"] == "FILE_MISSING"


def test_file_size_limit_from_settings() -> None:
    client, _ = _client([], max_file_size_mb=1)
    with client:
        response = _post(client, name="duzy.pdf", data=b"%PDF-1.7\n" + b"0" * (1024 * 1024 + 10))
    assert response.status_code == 413 and response.json()["code"] == "FILE_TOO_LARGE"


def test_corrupted_doc_is_unreadable() -> None:
    # Nagłówek OLE bez treści dokumentu Word. Brak LibreOffice (415) sprawdza test_normalize.
    ole = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 504
    client, _ = _client([])
    with client:
        response = _post(client, name="wniosek.doc", data=ole)
    assert response.status_code == 422 and response.json()["code"] == "DOCUMENT_UNREADABLE"


def test_busy_server_times_out() -> None:
    client, fake = _client(request_timeout_s=1)
    with client:
        client.app.state.job_semaphore = asyncio.Semaphore(0)  # type: ignore[attr-defined]
        response = _post(client)
    assert response.status_code == 504 and response.json()["code"] == "PROCESSING_TIMEOUT"
    assert fake.calls == []


def test_convert_requires_token() -> None:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    public = (
        rsa.generate_private_key(public_exponent=65537, key_size=2048)
        .public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )
    # RS256 z samym kluczem publicznym: tryb weryfikacji, bez konta technicznego.
    settings = Settings(
        app_env="development", jwt_algorithm="RS256", jwt_public_key=public, _env_file=None
    )
    app = create_app(settings, llm_client=FakeLlmClient([]), converter=None)
    with TestClient(app) as client:
        response = _post(client)
    assert response.status_code == 401
    assert response.json()["code"] == "NOT_AUTHENTICATED"


def test_validate_reports_errors_without_fixing() -> None:
    client, _ = _client()
    with client:
        form = _post(client).json()
        ok = client.post(VALIDATE, json=form).json()
        broken = client.post(VALIDATE, json={**form, "tabs": form["tabs"][-1:]}).json()
    assert ok == {"valid": True, "errors": [], "warnings": ok["warnings"]}
    assert broken["valid"] is False
    assert any(e["code"] == "R02_TABS" for e in broken["errors"])


def test_validate_rejects_non_object() -> None:
    client, _ = _client([])
    with client:
        response = client.post(VALIDATE, json=[1, 2])
    assert response.status_code == 422 and response.json()["code"] == "VALIDATION_ERROR"


def test_initial_data_sources() -> None:
    client, _ = _client([])
    with client:
        sources = client.get("/api/v1/initial-data-sources").json()
    counts = {s["source"]: len(s["attributes"]) for s in sources}
    assert counts == {"PESEL": 16, "PESEL_ADDRESS": 18, "MLPZ": 17}
    mlpz = next(s for s in sources if s["source"] == "MLPZ")
    assert mlpz["name"] == "Dane zalogowanego użytkownika"
    assert {"attribute": "name", "ref": "MLPZ.name"}.items() <= mlpz["attributes"][0].items()


def test_convert_uses_model_from_query_when_allowed() -> None:
    client, fake = _client(llm_models="qwen3.5:35b-a3b")
    with client:
        response = _post(client, report="true", model="qwen3.5:35b-a3b")
    assert response.status_code == 200, response.text
    assert response.json()["report"]["llm"]["model"] == "qwen3.5:35b-a3b"
    assert {call["model"] for call in fake.calls} == {"qwen3.5:35b-a3b"}


def test_convert_rejects_model_outside_allowlist() -> None:
    client, fake = _client(llm_models="qwen3.5:35b-a3b")
    with client:
        response = _post(client, model="llama3:70b")
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"
    assert not fake.calls


def _identity_prefixes(source: str | None, default: str = "MLPZ") -> set[str]:
    client, _ = _client(initial_data_identity_source=default)
    params = {} if source is None else {"identitySource": source}
    with client:
        response = _post(client, **params)
    assert response.status_code == 200, response.text
    refs: set[str] = set()
    for tab in response.json()["tabs"]:
        for question in tab["questions"]:
            field = question["field"]
            if field["techName"] != "twoje_dane":
                continue
            for child in field["repeatingSectionGrid"]:
                data = child["field"].get("defaultValue")
                if isinstance(data, str) and data.startswith(("PESEL.", "MLPZ.")):
                    refs.add(data.split(".")[0])
    return refs


@pytest.mark.parametrize("source", ["PESEL", "MLPZ"])
def test_identity_source_per_request(source: str) -> None:
    other = "MLPZ" if source == "PESEL" else "PESEL"
    assert _identity_prefixes(source, default=other) == {source}


def test_identity_source_defaults_to_settings() -> None:
    assert _identity_prefixes(None, default="PESEL") == {"PESEL"}
    assert _identity_prefixes(None, default="MLPZ") == {"MLPZ"}


def test_identity_source_invalid_is_validation_error() -> None:
    client, _ = _client([])
    with client:
        response = _post(client, identitySource="ZUS")
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


def test_missing_rodo_url_warns_in_report() -> None:
    def codes(**settings: Any) -> set[str]:
        client, _ = _client(**settings)
        with client:
            body = _post(client, report="true").json()
        return {w["code"] for w in body["report"]["warnings"]}

    assert "W28_RODO_CLAUSE_URL_MISSING" in codes()
    assert "W28_RODO_CLAUSE_URL_MISSING" not in codes(rodo_clause_url="https://bip.example.org/r")
