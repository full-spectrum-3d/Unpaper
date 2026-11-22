"""Dokumentacja OpenAPI: kompletność opisów błędów i zgodność schematów z odpowiedziami."""

import pytest

from app.api.v1.schemas import (
    ConvertWithReport,
    DictionaryCatalog,
    InitialDataSources,
    TerytTree,
    ValidationResult,
)
from app.core.errors import PROBLEM_MEDIA_TYPE, ErrorCode, ProblemDetail
from app.core.openapi import ERROR_DOCS, problem_example
from app.main import create_app
from tests.test_forms_api import VALIDATE, _client, _post, _settings
from tests.unit.fakes import FakeLlmClient


def _spec() -> dict:
    return create_app(_settings(), llm_client=FakeLlmClient(), converter=None).openapi()


def _codes(response: dict) -> set[str]:
    return set(response["content"][PROBLEM_MEDIA_TYPE]["examples"])


def test_every_error_code_is_documented() -> None:
    assert set(ERROR_DOCS) == set(ErrorCode)
    description = _spec()["info"]["description"]
    for code in ErrorCode:
        assert f"`{code}`" in description


def test_examples_are_valid_problem_details() -> None:
    for code in ErrorCode:
        ProblemDetail.model_validate(problem_example(code))


def test_error_responses_use_problem_schema_everywhere() -> None:
    spec = _spec()
    schemas = spec["components"]["schemas"]
    assert "ProblemDetail" in schemas and "HTTPValidationError" not in schemas
    for path, item in spec["paths"].items():
        for method, operation in item.items():
            assert operation.get("summary"), (method, path)
            for status, response in operation["responses"].items():
                if int(status) >= 400:
                    content = response["content"][PROBLEM_MEDIA_TYPE]
                    assert content["schema"] == {"$ref": "#/components/schemas/ProblemDetail"}
            assert "500" in operation["responses"], (method, path)


def test_convert_documents_every_upload_error() -> None:
    responses = _spec()["paths"]["/api/v1/forms/convert"]["post"]["responses"]
    documented = set().union(*(_codes(r) for s, r in responses.items() if int(s) >= 400))
    expected = {
        "MALFORMED_REQUEST", "FILE_MISSING", "TOO_MANY_FILES", "FILENAME_TOO_LONG",
        "FILENAME_FORBIDDEN_CHARS", "FILE_EMPTY", "FILE_TOO_LARGE", "UNSUPPORTED_EXTENSION",
        "MIME_MISMATCH", "ARCHIVE_TOO_LARGE", "DOCUMENT_TOO_COMPLEX", "DOCUMENT_UNREADABLE",
        "DOCUMENT_PASSWORD_REQUIRED", "DOCUMENT_PASSWORD_INVALID", "VALIDATION_ERROR",
        "SERVER_BUSY", "PROCESSING_TIMEOUT", "NOT_AUTHENTICATED", "INVALID_TOKEN", "FORBIDDEN",
        "INTERNAL_ERROR",
    }  # fmt: skip
    assert documented == expected
    assert "Retry-After" in responses["503"]["headers"]


def test_protected_routes_document_auth_errors() -> None:
    spec = _spec()
    for path in ("/api/v1/dictionaries", "/api/v1/forms/validate"):
        operation = next(iter(spec["paths"][path].values()))
        assert _codes(operation["responses"]["401"]) == {"NOT_AUTHENTICATED", "INVALID_TOKEN"}
        assert _codes(operation["responses"]["403"]) == {"FORBIDDEN"}


@pytest.mark.libmagic
def test_documented_schemas_match_real_responses() -> None:
    client, _ = _client()
    with client:
        converted = _post(client, report="true").json()
        validated = client.post(VALIDATE, json=converted["form"]).json()
        dictionaries = client.get("/api/v1/dictionaries").json()
        sources = client.get("/api/v1/initial-data-sources").json()
        teryt = client.get("/api/v1/dictionaries/teryt").json()
    ConvertWithReport.model_validate(converted)
    ValidationResult.model_validate(validated)
    DictionaryCatalog.model_validate(dictionaries)
    InitialDataSources.model_validate(sources)
    TerytTree.model_validate(teryt)


def test_real_error_matches_problem_schema() -> None:
    client, _ = _client([])
    with client:
        response = client.post(VALIDATE, json=[1, 2])
    assert response.headers["content-type"] == PROBLEM_MEDIA_TYPE
    problem = ProblemDetail.model_validate(response.json())
    assert problem.code is ErrorCode.VALIDATION_ERROR and problem.errors
