"""Dokumentacja OpenAPI (Swagger UI pod /docs, ReDoc pod /redoc).

Opisy błędów pochodzą z jednego miejsca: `ErrorCode` + `_ERROR_META` (status, tytuł)
w `app.core.errors` i `ERROR_DOCS` (kiedy występuje) tutaj. Endpoint wymienia swoje
kody przez `problem_responses(...)`; status HTTP, opis i przykłady składamy automatycznie.
"""

from collections import defaultdict
from typing import Any

from fastapi import FastAPI

from app.core.errors import (
    PROBLEM_MEDIA_TYPE,
    PROBLEM_TYPE_BASE,
    REQUEST_ID_HEADER,
    ErrorCode,
    ProblemDetail,
    error_meta,
)

# Kiedy serwer zwraca dany kod. Test pilnuje, żeby każdy `ErrorCode` miał opis.
ERROR_DOCS: dict[ErrorCode, str] = {
    ErrorCode.NOT_AUTHENTICATED: "Brak nagłówka `Authorization: Bearer <token>`.",
    ErrorCode.INVALID_TOKEN: "Token jest uszkodzony, wygasł, ma zły podpis, wydawcę albo "
    "odbiorcę, albo brakuje w nim wymaganych claimów.",
    ErrorCode.INVALID_CREDENTIALS: "Login lub hasło nie pasują do konta technicznego ani "
    "do żadnego zarejestrowanego konta.",
    ErrorCode.FORBIDDEN: "Token jest poprawny, ale nie ma roli wymaganej przez "
    "konfigurację (`JWT_REQUIRED_ROLE`).",
    ErrorCode.USERNAME_TAKEN: "Konto o tym loginie (bez rozróżniania wielkości liter) już "
    "istnieje albo login jest zarezerwowany dla konta technicznego.",
    ErrorCode.REGISTRATION_DISABLED: "Rejestracja kont jest wyłączona w konfiguracji serwera.",
    ErrorCode.MALFORMED_REQUEST: "Ciało nie jest poprawnym `multipart/form-data`: brak lub "
    "zły `Content-Type`, brak granicy, uszkodzone nagłówki albo struktura części.",
    ErrorCode.FILE_MISSING: "W żądaniu nie ma pliku: brak części `file`, plik wysłany "
    "w polu o innej nazwie albo pusta nazwa pliku.",
    ErrorCode.TOO_MANY_FILES: "Przesłano więcej niż jeden plik; endpoint przyjmuje dokładnie "
    "jeden.",
    ErrorCode.FILENAME_TOO_LONG: "Nazwa pliku przekracza dopuszczalną długość.",
    ErrorCode.FILENAME_FORBIDDEN_CHARS: "Nazwa pliku zawiera ścieżkę, znaki sterujące albo "
    "inne niedozwolone znaki.",
    ErrorCode.FILE_TOO_LARGE: "Plik (albo całe ciało żądania) przekracza `MAX_FILE_SIZE_MB`.",
    ErrorCode.FILE_EMPTY: "Przesłany plik ma 0 bajtów.",
    ErrorCode.UNSUPPORTED_EXTENSION: "Rozszerzenie spoza listy pdf, doc, docx, ods, xlsx, jpg, "
    "jpeg, png; także DOC/ODS, gdy w obrazie nie ma LibreOffice.",
    ErrorCode.MIME_MISMATCH: "Rzeczywista zawartość pliku (sygnatura) nie odpowiada "
    "rozszerzeniu, np. plik .pdf, który jest obrazem PNG.",
    ErrorCode.ARCHIVE_TOO_LARGE: "Dokument OOXML/ODF po rozpakowaniu przekracza limit "
    "(ochrona przed zip bombą).",
    ErrorCode.DOCUMENT_TOO_COMPLEX: "Za dużo stron, arkuszy, komórek albo pikseli obrazu "
    "jak na limity przetwarzania.",
    ErrorCode.DOCUMENT_UNREADABLE: "Pliku nie da się otworzyć ani odczytać: uszkodzony, "
    "obcięty albo w nieobsługiwanym wariancie formatu.",
    ErrorCode.DOCUMENT_PASSWORD_REQUIRED: "Dokument jest zaszyfrowany hasłem. Wyślij go "
    "ponownie z polem `password`.",
    ErrorCode.DOCUMENT_PASSWORD_INVALID: "Podane `password` nie otwiera dokumentu.",
    ErrorCode.LLM_UNAVAILABLE: "Serwer modelu (Ollama) nie odpowiada albo nie ma pobranego "
    "modelu `LLM_MODEL`. Konwersja wtedy działa dalej regułami (ostrzeżenie W01), więc ten "
    "kod zwraca tylko `/health/ready`.",
    ErrorCode.PROCESSING_TIMEOUT: "Odbiór, walidacja i konwersja pliku nie zmieściły się "
    "w `REQUEST_TIMEOUT_S`.",
    ErrorCode.SERVER_BUSY: "Wszystkie miejsca w kolejce (`MAX_CONCURRENT_JOBS`) są zajęte "
    "dłużej niż limit czasu żądania. Ponów po czasie z nagłówka `Retry-After`.",
    ErrorCode.SERVICE_UNAVAILABLE: "W obrazie brakuje libmagic albo Tesseracta; bez nich "
    "żadna konwersja się nie uda.",
    ErrorCode.VALIDATION_ERROR: "Parametry lub ciało żądania nie spełniają schematu; "
    "szczegóły w `errors[]` (`loc`, `msg`, `type`). Także nieznany parametr `model`.",
    ErrorCode.NOT_FOUND: "Nie ma takiej ścieżki.",
    ErrorCode.METHOD_NOT_ALLOWED: "Ścieżka istnieje, ale nie obsługuje tej metody HTTP.",
    ErrorCode.HTTP_ERROR: "Inny błąd protokołu HTTP zgłoszony przez serwer; `title` to "
    "standardowa fraza statusu.",
    ErrorCode.INTERNAL_ERROR: "Nieoczekiwany błąd serwera. Zgłaszając go, podaj "
    "`request_id` - pozwala znaleźć wpis w logach.",
}

# Przykładowe `detail` tam, gdzie serwer go zwykle wypełnia.
_EXAMPLE_DETAIL: dict[ErrorCode, str] = {
    ErrorCode.MALFORMED_REQUEST: "Brak nagłówka Content-Type",
    ErrorCode.FILE_MISSING: "Plik musi być przesłany w polu 'file', otrzymano 'files'",
    ErrorCode.TOO_MANY_FILES: "Żądanie zawiera więcej niż jeden plik",
    ErrorCode.FILE_TOO_LARGE: "Plik przekracza limit 20 MB",
    ErrorCode.UNSUPPORTED_EXTENSION: "Rozszerzenie .txt nie jest obsługiwane. Dozwolone: .pdf, "
    ".doc, .docx, .ods, .xlsx, .jpg, .jpeg, .png",
    ErrorCode.DOCUMENT_TOO_COMPLEX: "Liczba stron: 120, dopuszczalna: 50",
    ErrorCode.SERVER_BUSY: "Serwer przetwarza inne pliki - spróbuj ponownie",
    ErrorCode.LLM_UNAVAILABLE: "brak modelu qwen3:8b",
}

_EXAMPLE_REQUEST_ID = "0b7c5f1e-3a43-4c8e-9f57-2d6a1c9e8b10"


def problem_example(code: ErrorCode, instance: str = "/api/v1/forms/convert") -> dict[str, Any]:
    """Przykładowa odpowiedź problem+json dla kodu (taka, jaką zwraca serwer)."""
    status, title = error_meta(code)
    example: dict[str, Any] = {
        "type": f"{PROBLEM_TYPE_BASE}{code}",
        "title": title,
        "status": status,
        "code": str(code),
    }
    detail = _EXAMPLE_DETAIL.get(code)
    if detail:
        example["detail"] = detail
    example |= {"instance": instance, "request_id": _EXAMPLE_REQUEST_ID}
    if code is ErrorCode.VALIDATION_ERROR:
        example["errors"] = [
            {
                "loc": ["query", "identitySource"],
                "msg": "Input should be 'PESEL' or 'MLPZ'",
                "type": "literal_error",
            }
        ]
    return example


_HEADER_DOCS: dict[ErrorCode, dict[str, Any]] = {
    ErrorCode.SERVER_BUSY: {
        "Retry-After": {"schema": {"type": "integer"}, "description": "Po ilu sekundach ponowić"}
    },
    ErrorCode.NOT_AUTHENTICATED: {
        "WWW-Authenticate": {"schema": {"type": "string"}, "description": "`Bearer`"}
    },
    ErrorCode.INVALID_TOKEN: {
        "WWW-Authenticate": {
            "schema": {"type": "string"},
            "description": '`Bearer error="invalid_token"`',
        }
    },
}

_REQUEST_ID_HEADER_DOC = {
    REQUEST_ID_HEADER: {
        "schema": {"type": "string", "format": "uuid"},
        "description": "Identyfikator żądania nadany przez serwer (ten sam co `request_id`)",
    }
}


def problem_responses(
    *codes: ErrorCode, instance: str = "/api/v1/forms/convert"
) -> dict[int | str, dict[str, Any]]:
    """Odpowiedzi błędów do `responses=`: kody pogrupowane po statusie HTTP, z przykładami.

    Opis statusu wymienia każdy kod z wyjaśnieniem, kiedy występuje; Swagger UI pokazuje
    przykłady w liście rozwijanej.
    """
    by_status: dict[int, list[ErrorCode]] = defaultdict(list)
    for code in codes:
        by_status[error_meta(code)[0]].append(code)
    responses: dict[int | str, dict[str, Any]] = {}
    for status, group in sorted(by_status.items()):
        headers = dict(_REQUEST_ID_HEADER_DOC)
        for code in group:
            headers |= _HEADER_DOCS.get(code, {})
        responses[status] = {
            "description": "\n".join(f"- `{code}` - {ERROR_DOCS[code]}" for code in group),
            "headers": headers,
            "content": {
                PROBLEM_MEDIA_TYPE: {
                    "schema": {"$ref": "#/components/schemas/ProblemDetail"},
                    "examples": {
                        str(code): {
                            "summary": error_meta(code)[1],
                            "value": problem_example(code, instance),
                        }
                        for code in group
                    },
                }
            },
        }
    return responses


def _error_table() -> str:
    rows = [
        f"| `{code}` | {error_meta(code)[0]} | {error_meta(code)[1]} | {ERROR_DOCS[code]} |"
        for code in ErrorCode
    ]
    return "\n".join(
        ["| Kod (`code`) | HTTP | Tytuł (`title`) | Kiedy występuje |", "|---|---|---|---|", *rows]
    )


API_DESCRIPTION = f"""
Konwersja formularzy papierowych (PDF, DOC, DOCX, ODS, XLSX, JPG, PNG) na konfigurację
formularza w formacie importu Generatora Formularzy COI.

## Typowy przebieg

1. `POST /api/v1/auth/token` - login i hasło → token JWT (przycisk **Authorize** powyżej
   robi to samo).
2. `POST /api/v1/forms/convert?report=true` - jeden plik → `{{form, report}}`.
3. Opcjonalnie popraw formularz i sprawdź go przez `POST /api/v1/forms/validate`.

## Uwierzytelnianie

Endpointy z tagów `forms` i `catalog` wymagają nagłówka `Authorization: Bearer <token>`.
Token wydaje `POST /api/v1/auth/token` (OAuth2 password flow) albo zewnętrzny dostawca
tożsamości (RS256) - wtedy endpointów `/auth` nie ma. `health` i `auth` są publiczne.

## Identyfikator żądania

Każda odpowiedź ma nagłówek `{REQUEST_ID_HEADER}` z identyfikatorem nadanym przez serwer;
w błędach ta sama wartość jest w polu `request_id`. Klient może wysłać własny UUID w tym
nagłówku - serwer zapisze go w logach obok swojego, ale go nie przejmie.

## Limity

- Rozmiar pliku i ciała żądania: `MAX_FILE_SIZE_MB` (413 `FILE_TOO_LARGE`).
- Czas żądania: `REQUEST_TIMEOUT_S` (504 `PROCESSING_TIMEOUT`).
- Równoległe konwersje: `MAX_CONCURRENT_JOBS`; po przekroczeniu czasu oczekiwania
  503 `SERVER_BUSY` z nagłówkiem `Retry-After`.

## Błędy

Wszystkie błędy mają typ `{PROBLEM_MEDIA_TYPE}` (RFC 9457) i schemat `ProblemDetail`.
O rodzaju błędu decyduje pole `code` (stałe, do obsługi w kodzie klienta); `title` to
krótki opis po polsku, a `detail` - opcjonalne szczegóły konkretnego przypadku. `type`
to `{PROBLEM_TYPE_BASE}<code>`. Błędy walidacji (`VALIDATION_ERROR`) mają dodatkowo
listę `errors[]` z polami `loc`, `msg`, `type`.

Przykład:

```json
{{
  "type": "{PROBLEM_TYPE_BASE}FILE_TOO_LARGE",
  "title": "Plik jest zbyt duży",
  "status": 413,
  "code": "FILE_TOO_LARGE",
  "detail": "Maksymalny rozmiar pliku to 20 MB",
  "instance": "/api/v1/forms/convert",
  "request_id": "{_EXAMPLE_REQUEST_ID}"
}}
```

### Wszystkie kody błędów

{_error_table()}

Każdy endpoint może dodatkowo zwrócić `404 NOT_FOUND`, `405 METHOD_NOT_ALLOWED`
i `500 INTERNAL_ERROR`.
"""

OPENAPI_TAGS: list[dict[str, Any]] = [
    {
        "name": "forms",
        "description": "Konwersja dokumentu na formularz i weryfikacja JSON-a formularza. "
        "Wymaga tokenu.",
    },
    {
        "name": "catalog",
        "description": "Katalogi używane przy budowie formularza: słowniki, drzewo TERYT, "
        "źródła danych inicjalnych. Wymaga tokenu.",
    },
    {
        "name": "auth",
        "description": "Logowanie, rejestracja i wydawanie tokenów JWT. Dostępne tylko, gdy "
        "API samo wydaje tokeny.",
    },
    {
        "name": "health",
        "description": "Sondy dla orkiestratora (liveness/readiness). Publiczne.",
    },
]

SWAGGER_UI_PARAMETERS: dict[str, Any] = {
    "persistAuthorization": True,
    "displayRequestDuration": True,
    "filter": True,
    "docExpansion": "list",
    "defaultModelsExpandDepth": 1,
}


def _install_problem_schemas(spec: dict[str, Any]) -> None:
    """`ProblemDetail` jest tylko w `$ref` odpowiedzi błędów - dopisujemy go do komponentów."""
    schema = ProblemDetail.model_json_schema(ref_template="#/components/schemas/{model}")
    schemas = spec.setdefault("components", {}).setdefault("schemas", {})
    schemas |= schema.pop("$defs", {})
    schemas["ProblemDetail"] = schema


def _replace_default_422(spec: dict[str, Any]) -> None:
    """Domyślne 422 FastAPI (`HTTPValidationError`) nie odpowiada temu, co zwraca serwer."""
    ours = problem_responses(ErrorCode.VALIDATION_ERROR)[422]
    default_ref = "#/components/schemas/HTTPValidationError"
    for path_item in spec.get("paths", {}).values():
        for operation in path_item.values():
            response = operation.get("responses", {}).get("422")
            if response and default_ref in str(response):
                operation["responses"]["422"] = ours
    schemas = spec.get("components", {}).get("schemas", {})
    if default_ref not in str(spec.get("paths")):
        schemas.pop("HTTPValidationError", None)
        schemas.pop("ValidationError", None)


def install_openapi(app: FastAPI) -> None:
    """Podmienia `app.openapi` na wersję z poprawkami powyżej (wynik jest cache'owany)."""
    build = app.openapi

    def openapi() -> dict[str, Any]:
        if app.openapi_schema is None:
            spec = build()
            _install_problem_schemas(spec)
            _replace_default_422(spec)
            app.openapi_schema = spec
        return app.openapi_schema

    app.openapi = openapi  # type: ignore[method-assign]
