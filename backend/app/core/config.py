"""Konfiguracja aplikacji ze zmiennych środowiskowych (spec §12).

Źródła, od najwyższego priorytetu: zmienne środowiskowe, plik `.env` (lokalne
uruchomienie: `backend/.env`, potem `.env` w katalogu głównym repo), Docker secrets
(plik `/run/secrets/<nazwa_pola>`, np. `/run/secrets/jwt_private_key`), wartości domyślne.
W Dockerze plik `.env` nie trafia do obrazu - zmienne wstrzykuje docker compose.
Konfiguracja jest walidowana przy starcie - błędna lub niebezpieczna
konfiguracja zatrzymuje aplikację.
"""

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal, Self

from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey
from cryptography.hazmat.primitives.serialization import load_pem_private_key, load_pem_public_key
from fastapi import Request
from pydantic import Field, PositiveInt, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

_SECRETS_DIR = Path("/run/secrets")
_BACKEND_DIR = Path(__file__).resolve().parents[2]
# Późniejszy plik ma wyższy priorytet; nieistniejące pliki są pomijane.
_ENV_FILES = (_BACKEND_DIR.parent / ".env", _BACKEND_DIR / ".env")
_MIN_HS256_SECRET_BYTES = 32  # RFC 7518 §3.2: klucz co najmniej tak długi jak skrót (256 bitów)
_ARGON2ID_PREFIX = "$argon2id$"
_CLAIM_PATH_PATTERN = r"^[A-Za-z0-9_:-]+(\.[A-Za-z0-9_:-]+)*$"
# Claimy rejestrowane, których nie wolno nadpisać mapowaniem (sub jest dozwolony).
_RESERVED_CLAIMS = frozenset({"iss", "aud", "exp", "iat", "nbf", "jti"})


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        case_sensitive=False,
        extra="ignore",
        env_file=_ENV_FILES,
        env_file_encoding="utf-8",
        secrets_dir=_SECRETS_DIR if _SECRETS_DIR.is_dir() else None,
    )

    # --- Aplikacja ---
    app_env: Literal["production", "development"] = "production"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # --- Upload i limity przetwarzania ---
    max_file_size_mb: PositiveInt = 20
    max_uncompressed_mb: PositiveInt = 100
    max_pdf_pages: PositiveInt = 30
    max_image_pixels: PositiveInt = 60_000_000
    spool_max_mb: PositiveInt = 10
    max_concurrent_jobs: PositiveInt = 2
    request_timeout_s: PositiveInt = 540

    # --- Uwierzytelnianie (spec §10.1) ---
    auth_enabled: bool = True
    jwt_algorithm: Literal["HS256", "RS256"] = "HS256"
    jwt_secret: SecretStr | None = None
    jwt_public_key: str | None = None
    jwt_private_key: SecretStr | None = None
    jwt_issuer: str = "coi-cf"
    jwt_audience: str = "coi-cf-api"
    jwt_expires_min: Annotated[int, Field(ge=1, le=1440)] = 60
    jwt_leeway_s: Annotated[int, Field(ge=0, le=300)] = 30
    # Mapowanie claimów tokenów z zewnętrznego brokera (np. Keycloak przed Węzłem Krajowym).
    # Ścieżki z kropkami oznaczają zagnieżdżenie: `realm_access.roles`.
    jwt_subject_claim: Annotated[str, Field(pattern=_CLAIM_PATH_PATTERN)] = "sub"
    jwt_roles_claim: Annotated[str, Field(pattern=_CLAIM_PATH_PATTERN)] = "roles"
    jwt_required_role: str | None = None
    api_user: str | None = None
    api_password_hash: SecretStr | None = None

    # --- HTTP ---
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:8080"]

    # --- LLM ---
    llm_base_url: str = "http://llm:11434"
    llm_model: str = "qwen3:8b"
    llm_timeout_s: PositiveInt = 240
    llm_temperature: Annotated[float, Field(ge=0, le=2)] = 0
    llm_seed: int = 42
    llm_num_ctx: PositiveInt = 8192
    # Limit tokenów odpowiedzi: zapętlony model nie zużyje całego budżetu czasu.
    llm_num_predict: PositiveInt = 2048
    # Dłuższy dokument dzielimy na fragmenty: 8b na CPU gubi pola w długim tekście
    # (stypendium), a pojedyncze wywołanie nie mieści się w czasie (odpady, §10.2).
    llm_max_chunk_chars: PositiveInt = 4500
    extraction_vlm_enabled: bool = False
    vlm_model: str = "qwen2.5vl:7b"

    # --- Ekstrakcja i konwersja ---
    ocr_lang: str = "pol"
    ocr_dpi: PositiveInt = 300
    converter_timeout_s: PositiveInt = 60

    # --- Budowa formularza ---
    initial_data_identity_source: Literal["MLPZ", "PESEL"] = "MLPZ"
    finish_page_style: Literal["sample", "info_section"] = "sample"
    max_sections_per_page: PositiveInt = 8
    rodo_clause_url: str | None = None

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("jwt_required_role", mode="before")
    @classmethod
    def _empty_role_is_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value.strip() if isinstance(value, str) else value

    @field_validator("jwt_public_key", mode="before")
    @classmethod
    def _unescape_public_pem(cls, value: object) -> object:
        return _unescape_pem(value)

    @field_validator("jwt_private_key", mode="before")
    @classmethod
    def _unescape_private_pem(cls, value: object) -> object:
        return _unescape_pem(value)

    @property
    def token_issuing_enabled(self) -> bool:
        """Czy API wydaje tokeny. RS256 bez klucza prywatnego = tylko weryfikacja."""
        if not self.auth_enabled:
            return False
        return self.jwt_algorithm == "HS256" or self.jwt_private_key is not None

    @property
    def jwt_signing_key(self) -> str:
        if self.jwt_algorithm == "HS256":
            assert self.jwt_secret is not None  # noqa: S101 - zapewnia walidacja przy starcie
            return self.jwt_secret.get_secret_value()
        assert self.jwt_private_key is not None  # noqa: S101
        return self.jwt_private_key.get_secret_value()

    @property
    def jwt_verification_key(self) -> str:
        if self.jwt_algorithm == "HS256":
            assert self.jwt_secret is not None  # noqa: S101
            return self.jwt_secret.get_secret_value()
        assert self.jwt_public_key is not None  # noqa: S101
        return self.jwt_public_key

    @model_validator(mode="after")
    def _validate_security(self) -> Self:
        if not self.auth_enabled:
            if self.app_env == "production":
                raise ValueError("AUTH_ENABLED=false jest dozwolone tylko przy APP_ENV=development")
            return self

        if self.jwt_algorithm == "HS256":
            self._validate_hs256()
        else:
            self._validate_rs256()

        self._validate_claim_mapping()

        if self.token_issuing_enabled:
            self._validate_technical_account()
        return self

    def _validate_hs256(self) -> None:
        if self.jwt_secret is None:
            raise ValueError("JWT_SECRET jest wymagany dla JWT_ALGORITHM=HS256")
        if len(self.jwt_secret.get_secret_value().encode()) < _MIN_HS256_SECRET_BYTES:
            raise ValueError(f"JWT_SECRET musi mieć co najmniej {_MIN_HS256_SECRET_BYTES} bajty")

    def _validate_rs256(self) -> None:
        if self.jwt_public_key is None:
            raise ValueError("JWT_PUBLIC_KEY jest wymagany dla JWT_ALGORITHM=RS256")
        try:
            public_key = load_pem_public_key(self.jwt_public_key.encode())
        except ValueError as exc:
            raise ValueError("JWT_PUBLIC_KEY nie jest poprawnym kluczem PEM") from exc
        if not isinstance(public_key, RSAPublicKey):
            raise ValueError("JWT_PUBLIC_KEY musi być kluczem RSA")

        if self.jwt_private_key is None:
            return
        try:
            private_key = load_pem_private_key(
                self.jwt_private_key.get_secret_value().encode(), password=None
            )
        except (ValueError, TypeError) as exc:
            raise ValueError(
                "JWT_PRIVATE_KEY nie jest poprawnym, niezaszyfrowanym kluczem PEM"
            ) from exc
        if not isinstance(private_key, RSAPrivateKey):
            raise ValueError("JWT_PRIVATE_KEY musi być kluczem RSA")
        if private_key.public_key().public_numbers() != public_key.public_numbers():
            raise ValueError("JWT_PRIVATE_KEY i JWT_PUBLIC_KEY nie tworzą pary")

    def _validate_claim_mapping(self) -> None:
        subject, roles = self.jwt_subject_claim, self.jwt_roles_claim
        for name, path in (("JWT_SUBJECT_CLAIM", subject), ("JWT_ROLES_CLAIM", roles)):
            if path.split(".")[0] in _RESERVED_CLAIMS:
                raise ValueError(f"{name} nie może wskazywać claimu rejestrowanego ({path})")
        overlap = (
            subject == roles or subject.startswith(f"{roles}.") or roles.startswith(f"{subject}.")
        )
        if overlap:
            raise ValueError("JWT_SUBJECT_CLAIM i JWT_ROLES_CLAIM nie mogą się pokrywać")

    def _validate_technical_account(self) -> None:
        if not self.api_user:
            raise ValueError("API_USER jest wymagany, gdy API wydaje tokeny")
        if self.api_password_hash is None:
            raise ValueError("API_PASSWORD_HASH jest wymagany, gdy API wydaje tokeny")
        if not self.api_password_hash.get_secret_value().startswith(_ARGON2ID_PREFIX):
            raise ValueError(
                "API_PASSWORD_HASH musi być hashem argon2id (wygeneruj: make password-hash)"
            )


def _unescape_pem(value: object) -> object:
    """Pozwala podać PEM w jednej linii zmiennej środowiskowej (`\\n` zamiast nowych linii)."""
    if isinstance(value, str):
        return value.replace("\\n", "\n").strip()
    return value


@lru_cache
def load_settings() -> Settings:
    """Ustawienia ze środowiska, wczytywane raz przy starcie aplikacji."""
    return Settings()


def get_settings(request: Request) -> Settings:
    """Zależność FastAPI: ustawienia aplikacji obsługującej żądanie."""
    settings = request.app.state.settings
    assert isinstance(settings, Settings)  # noqa: S101
    return settings
