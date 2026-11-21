"""POST /auth/token - logowanie kontem technicznym, wydanie JWT (spec §6.1, §10.1).

Router jest rejestrowany tylko wtedy, gdy API wydaje tokeny
(`Settings.token_issuing_enabled`). Przy RS256 z samym kluczem publicznym
tokeny wydaje inny system, a ten endpoint nie istnieje.
"""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Response
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

from app.core.config import Settings, get_settings
from app.core.errors import AppError, ErrorCode, ProblemDetail
from app.core.security import authenticate_user, create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105 - typ tokenu, nie sekret
    expires_in: int


@router.post(
    "/token",
    response_model=TokenResponse,
    responses={401: {"model": ProblemDetail, "description": "Nieprawidłowy login lub hasło"}},
)
def issue_token(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    settings: Annotated[Settings, Depends(get_settings)],
    response: Response,
) -> TokenResponse:
    # Funkcja synchroniczna: weryfikacja argon2 obciąża CPU, FastAPI uruchomi ją w puli wątków.
    if not authenticate_user(settings, form.username, form.password):
        raise AppError(ErrorCode.INVALID_CREDENTIALS)
    assert settings.api_user is not None  # noqa: S101 - zapewnia walidacja konfiguracji
    token, expires_in = create_access_token(settings, settings.api_user)
    response.headers["Cache-Control"] = "no-store"
    return TokenResponse(access_token=token, expires_in=expires_in)
