"""Uwierzytelnianie: hasło konta technicznego, wydawanie i weryfikacja JWT (spec §10.1).

Algorytm i klucze pochodzą wyłącznie z konfiguracji - nigdy z nagłówka tokenu.
Ścieżka uwierzytelniania nie wykonuje żadnych wywołań sieciowych.

Narzędzie: `python -m app.core.security hash-password` wypisuje hash argon2id
do zmiennej API_PASSWORD_HASH. Z `--stdin` czyta hasło z pierwszej linii wejścia
(skrypty, np. `scripts/init-env.sh`), bez pytania o powtórzenie.
"""

import argparse
import getpass
import hmac
import logging
import sys
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Annotated, Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer

from app.core.config import Settings, get_settings
from app.core.errors import AppError, ErrorCode

logger = logging.getLogger(__name__)

TOKEN_URL = "/api/v1/auth/token"  # noqa: S105 - ścieżka endpointu, nie sekret
# Identyfikator użytkownika sprawdzamy osobno - jego claim jest konfigurowalny (JWT_SUBJECT_CLAIM).
_REQUIRED_CLAIMS = ["exp", "iat", "iss", "aud"]
_DEV_SUBJECT = "dev"

_password_hasher = PasswordHasher()
_oauth2_scheme = OAuth2PasswordBearer(tokenUrl=TOKEN_URL, auto_error=False)


@dataclass(frozen=True, slots=True)
class Principal:
    """Uwierzytelniony podmiot żądania."""

    subject: str
    roles: frozenset[str] = frozenset()


# --- Hasło konta technicznego ---


@lru_cache(maxsize=1)
def _dummy_hash() -> str:
    """Hash porównawczy dla złego loginu - wyrównuje czas odpowiedzi."""
    return _password_hasher.hash(uuid.uuid4().hex)


def authenticate_user(settings: Settings, username: str, password: str) -> bool:
    """Sprawdza login i hasło konta technicznego w czasie niezależnym od poprawności loginu."""
    expected_user = settings.api_user or ""
    user_ok = hmac.compare_digest(username.encode(), expected_user.encode())
    if user_ok and settings.api_password_hash is not None:
        stored_hash = settings.api_password_hash.get_secret_value()
    else:
        stored_hash = _dummy_hash()
    password_ok: bool
    try:
        password_ok = _password_hasher.verify(stored_hash, password)
    except VerificationError, InvalidHashError:
        password_ok = False
    return user_ok and password_ok


# --- Tokeny ---


def create_access_token(settings: Settings, subject: str) -> tuple[str, int]:
    """Wydaje token dostępowy. Zwraca (token, czas ważności w sekundach)."""
    if not settings.token_issuing_enabled:
        raise RuntimeError("Wydawanie tokenów jest wyłączone w tej konfiguracji")
    now = datetime.now(UTC)
    expires_in = settings.jwt_expires_min * 60
    payload: dict[str, Any] = {
        "sub": subject,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": now,
        "nbf": now,
        "exp": now + timedelta(seconds=expires_in),
        "jti": str(uuid.uuid4()),
    }
    # Własne tokeny mają ten sam kształt co tokeny brokera, więc przechodzą tę samą weryfikację.
    _set_claim(payload, settings.jwt_subject_claim, subject)
    if settings.jwt_required_role:
        _set_claim(payload, settings.jwt_roles_claim, [settings.jwt_required_role])
    token = jwt.encode(payload, settings.jwt_signing_key, algorithm=settings.jwt_algorithm)
    return token, expires_in


def decode_access_token(settings: Settings, token: str) -> Principal:
    """Weryfikuje podpis, claimy i wymaganą rolę tokenu.

    Zły token → `AppError(INVALID_TOKEN)` (401), brak wymaganej roli → `AppError(FORBIDDEN)` (403).
    """
    try:
        claims = jwt.decode(
            token,
            settings.jwt_verification_key,
            algorithms=[settings.jwt_algorithm],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
            leeway=settings.jwt_leeway_s,
            options={"require": _REQUIRED_CLAIMS},
        )
    except jwt.PyJWTError as exc:
        # Przyczyna tylko w logu; klient dostaje jednolity komunikat.
        logger.info("Odrzucono token: %s", type(exc).__name__)
        raise _invalid_token() from exc

    subject = _get_claim(claims, settings.jwt_subject_claim)
    if not isinstance(subject, str) or not subject:
        logger.info("Odrzucono token: brak claimu %s", settings.jwt_subject_claim)
        raise _invalid_token()

    roles = _parse_roles(_get_claim(claims, settings.jwt_roles_claim))
    required_role = settings.jwt_required_role
    if required_role and required_role not in roles:
        logger.info("Odmowa dostępu: brak roli %s", required_role)
        raise AppError(
            ErrorCode.FORBIDDEN,
            headers={"WWW-Authenticate": 'Bearer error="insufficient_scope"'},
        )
    return Principal(subject=subject, roles=roles)


def _get_claim(claims: Mapping[str, Any], path: str) -> object:
    """Wartość claimu wskazanego ścieżką z kropkami (`realm_access.roles`) albo None."""
    value: object = claims
    for segment in path.split("."):
        if not isinstance(value, Mapping):
            return None
        value = value.get(segment)
    return value


def _set_claim(payload: dict[str, Any], path: str, value: object) -> None:
    *parents, leaf = path.split(".")
    target = payload
    for segment in parents:
        target = target.setdefault(segment, {})
    target[leaf] = value


def _parse_roles(value: object) -> frozenset[str]:
    """Role jako lista napisów albo napis rozdzielony spacjami (styl `scope`)."""
    if isinstance(value, str):
        return frozenset(value.split())
    if isinstance(value, list):
        return frozenset(item for item in value if isinstance(item, str))
    return frozenset()


def _invalid_token() -> AppError:
    return AppError(
        ErrorCode.INVALID_TOKEN,
        headers={"WWW-Authenticate": 'Bearer error="invalid_token"'},
    )


# --- Zależność FastAPI ---


def require_auth(
    token: Annotated[str | None, Depends(_oauth2_scheme)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Principal:
    """Wymaga poprawnego tokenu Bearer. Przy AUTH_ENABLED=false (tylko dev) przepuszcza."""
    if not settings.auth_enabled:
        return Principal(subject=_DEV_SUBJECT)
    if not token:
        raise AppError(ErrorCode.NOT_AUTHENTICATED, headers={"WWW-Authenticate": "Bearer"})
    return decode_access_token(settings, token)


# --- CLI ---


def _hash_password_command(*, from_stdin: bool = False) -> int:
    password = sys.stdin.readline().rstrip("\r\n") if from_stdin else getpass.getpass("Hasło: ")
    if not password:
        print("Hasło nie może być puste.", file=sys.stderr)
        return 1
    if not from_stdin and password != getpass.getpass("Powtórz hasło: "):
        print("Hasła nie są zgodne.", file=sys.stderr)
        return 1
    print(_password_hasher.hash(password))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.core.security")
    subcommands = parser.add_subparsers(dest="command", required=True)
    hash_parser = subcommands.add_parser(
        "hash-password", help="wygeneruj hash argon2id dla API_PASSWORD_HASH"
    )
    hash_parser.add_argument(
        "--stdin", action="store_true", help="hasło z pierwszej linii stdin (dla skryptów)"
    )
    args = parser.parse_args(argv)
    if args.command == "hash-password":
        return _hash_password_command(from_stdin=args.stdin)
    return 2


if __name__ == "__main__":
    sys.exit(main())
