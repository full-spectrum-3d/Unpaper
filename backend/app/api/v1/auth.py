"""Logowanie, rejestracja i wydawanie JWT (spec §6.1, §10.1).

Router jest rejestrowany tylko wtedy, gdy API wydaje tokeny
(`Settings.token_issuing_enabled`). Przy RS256 z samym kluczem publicznym
tokeny wydaje inny system, a ten endpoint nie istnieje.

Konto techniczne (`API_USER` z `.env`) działa zawsze. Zarejestrowane konta leżą
w `UserStore` (SQLite), jeśli rejestracja jest dostępna.
"""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field

from app.core.config import Settings, get_settings
from app.core.errors import AppError, ErrorCode
from app.core.openapi import problem_responses
from app.core.security import authenticate_user, create_access_token
from app.core.users import UsernameTakenError, UserStore

router = APIRouter(prefix="/auth", tags=["auth"])


class TokenResponse(BaseModel):
    """Token dostępu do nagłówka `Authorization: Bearer <access_token>`."""

    access_token: str = Field(description="Token JWT")
    token_type: Literal["bearer"] = "bearer"  # noqa: S105 - typ tokenu, nie sekret
    expires_in: int = Field(description="Ważność tokenu w sekundach", examples=[3600])


class RegisterRequest(BaseModel):
    username: Annotated[
        str,
        Field(
            min_length=3,
            max_length=50,
            pattern=r"^[A-Za-z0-9._-]+$",
            description="Login: 3-50 znaków, litery łacińskie, cyfry, `.`, `_`, `-`; "
            "wielkość liter nie ma znaczenia",
            examples=["jan.kowalski"],
        ),
    ]
    password: Annotated[str, Field(min_length=8, max_length=128, description="Hasło: 8-128 znaków")]


class AuthOptions(BaseModel):
    registration_enabled: bool = Field(
        description="Czy działa `POST /auth/register` (inaczej 403 `REGISTRATION_DISABLED`)"
    )


def _user_store(request: Request) -> UserStore | None:
    store = getattr(request.app.state, "user_store", None)
    return store if isinstance(store, UserStore) else None


def _issue(settings: Settings, response: Response, subject: str) -> TokenResponse:
    token, expires_in = create_access_token(settings, subject)
    response.headers["Cache-Control"] = "no-store"
    return TokenResponse(access_token=token, expires_in=expires_in)


@router.get("/options", response_model=AuthOptions, summary="Opcje logowania")
def auth_options(request: Request) -> AuthOptions:
    """Mówi ekranowi logowania, czy pokazać rejestrację."""
    return AuthOptions(registration_enabled=_user_store(request) is not None)


@router.post(
    "/token",
    response_model=TokenResponse,
    summary="Logowanie (wydanie tokenu)",
    responses=problem_responses(
        ErrorCode.INVALID_CREDENTIALS, ErrorCode.VALIDATION_ERROR, instance="/api/v1/auth/token"
    ),
)
def issue_token(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    settings: Annotated[Settings, Depends(get_settings)],
    request: Request,
    response: Response,
) -> TokenResponse:
    """OAuth2 password flow: `application/x-www-form-urlencoded` z polami `username`
    i `password`. Działa dla konta technicznego (`API_USER`) i kont zarejestrowanych.
    Odpowiedź ma `Cache-Control: no-store`.
    """
    # Funkcja synchroniczna: weryfikacja argon2 obciąża CPU, FastAPI uruchomi ją w puli wątków.
    if authenticate_user(settings, form.username, form.password):
        assert settings.api_user is not None  # noqa: S101 - zapewnia walidacja konfiguracji
        return _issue(settings, response, settings.api_user)
    store = _user_store(request)
    if store is not None and store.verify(form.username, form.password):
        return _issue(settings, response, form.username.lower())
    raise AppError(ErrorCode.INVALID_CREDENTIALS)


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=201,
    summary="Rejestracja konta",
    responses=problem_responses(
        ErrorCode.REGISTRATION_DISABLED,
        ErrorCode.USERNAME_TAKEN,
        ErrorCode.VALIDATION_ERROR,
        instance="/api/v1/auth/register",
    ),
)
def register(
    body: RegisterRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    request: Request,
    response: Response,
) -> TokenResponse:
    """Zakłada konto i od razu zwraca token, jak po zalogowaniu."""
    store = _user_store(request)
    if store is None:
        raise AppError(ErrorCode.REGISTRATION_DISABLED)
    # Login konta technicznego jest zarezerwowany, inaczej dwa konta miałyby ten sam `sub`.
    if settings.api_user and body.username.lower() == settings.api_user.lower():
        raise AppError(ErrorCode.USERNAME_TAKEN)
    try:
        store.create(body.username, body.password)
    except UsernameTakenError as exc:
        raise AppError(ErrorCode.USERNAME_TAKEN) from exc
    return _issue(settings, response, body.username.lower())
