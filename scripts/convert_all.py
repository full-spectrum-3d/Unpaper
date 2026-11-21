"""Przepuszcza wszystkie formularze z katalogu wejściowego przez API (spec §13.3).

Zapisuje out/<nazwa pliku>.json (formularz) oraz out/<nazwa pliku>.report.json (raport).
Nazwa zawiera rozszerzenie: ten sam formularz bywa w kilku formatach (.pdf, .docx, .jpg).

    make convert-all                      # materials/ -> out/, API na http://localhost:8000
    uv run --project backend python scripts/convert_all.py --input DIR --output DIR \\
        [--url http://localhost:8000] [--user admin]

Login: --user albo API_USER (środowisko, potem .env), hasło: API_PASSWORD albo pytanie w terminalu.
Błąd jednego pliku nie przerywa przebiegu; kod wyjścia 1, gdy którykolwiek się nie powiódł.

    python3 scripts/convert_all.py --self-test
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import httpx

# Lista z backend/app/pipeline/upload_validation (MIME po rozszerzeniu).
SUPPORTED = {".pdf", ".doc", ".docx", ".ods", ".xlsx", ".jpg", ".jpeg", ".png"}
# > REQUEST_TIMEOUT_S (540): odpowiedź 504 przy przekroczeniu wysyła API.
TIMEOUT_S = 600


def inputs(directory: Path) -> list[Path]:
    """Obsługiwane pliki z katalogu (bez podkatalogów), posortowane.

    >>> import tempfile
    >>> d = Path(tempfile.mkdtemp())
    >>> for n in ("b.PDF", "a.docx", "notatka.txt", ".ukryty.pdf"): _ = (d / n).write_bytes(b"")
    >>> [p.name for p in inputs(d)]
    ['a.docx', 'b.PDF']
    """
    return sorted(
        p
        for p in directory.iterdir()
        if p.is_file() and not p.name.startswith(".") and p.suffix.lower() in SUPPORTED
    )


def output_paths(source: Path, out_dir: Path) -> tuple[Path, Path]:
    """Ścieżki formularza i raportu dla pliku źródłowego.

    >>> [p.as_posix() for p in output_paths(Path("m/Wniosek.pdf"), Path("out"))]
    ['out/Wniosek.pdf.json', 'out/Wniosek.pdf.report.json']
    """
    return out_dir / f"{source.name}.json", out_dir / f"{source.name}.report.json"


def env_file_user(path: Path = Path(".env")) -> str | None:
    """API_USER z pliku .env (make convert-all nie eksportuje .env do środowiska).

    >>> import tempfile
    >>> f = Path(tempfile.mkdtemp()) / ".env"
    >>> _ = f.write_text("JWT_SECRET=x\\nAPI_USER=admin\\n")
    >>> env_file_user(f), env_file_user(f.with_name("brak"))
    ('admin', None)
    """
    if not path.is_file():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("API_USER="):
            return line.removeprefix("API_USER=").strip().strip("'\"") or None
    return None


def _error_detail(response: httpx.Response) -> str:
    try:
        body = response.json()
        return f"{response.status_code} {body.get('code', '')}: {body.get('detail', '')}"
    except ValueError:
        return f"{response.status_code} {response.text[:200]}"


def login(client: httpx.Client, user: str, password: str) -> str:
    response = client.post("/api/v1/auth/token", data={"username": user, "password": password})
    if response.status_code != 200:
        sys.exit(f"Logowanie nieudane: {_error_detail(response)}")
    token: str = response.json()["access_token"]
    return token


def convert(client: httpx.Client, source: Path, out_dir: Path) -> str | None:
    """Konwertuje jeden plik; zwraca opis błędu albo None."""
    with source.open("rb") as fh:
        response = client.post(
            "/api/v1/forms/convert",
            params={"report": "true"},
            files={"file": (source.name, fh)},
            timeout=TIMEOUT_S,
        )
    if response.status_code != 200:
        return _error_detail(response)
    body = response.json()
    form_path, report_path = output_paths(source, out_dir)
    for path, data in ((form_path, body["form"]), (report_path, body["report"])):
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--input", type=Path, default=Path("materials"))
    parser.add_argument("--output", type=Path, default=Path("out"))
    parser.add_argument("--url", default=os.environ.get("API_URL", "http://localhost:8000"))
    parser.add_argument("--user", default=os.environ.get("API_USER") or env_file_user())
    parser.add_argument("--self-test", action="store_true", help="uruchom doctesty i wyjdź")
    args = parser.parse_args()
    if args.self_test:
        import doctest

        sys.exit(1 if doctest.testmod().failed else 0)

    import httpx  # zależność backendu; dopiero tutaj, żeby --self-test działał bez niej

    files = inputs(args.input)
    if not files:
        sys.exit(f"Brak obsługiwanych plików w {args.input}")
    if not args.user:
        sys.exit("Podaj --user albo ustaw API_USER")
    password = os.environ.get("API_PASSWORD") or getpass.getpass(f"Hasło {args.user}: ")
    args.output.mkdir(parents=True, exist_ok=True)

    failed: list[tuple[str, str]] = []
    with httpx.Client(base_url=args.url, timeout=30) as client:
        # shortcut: jeden token na cały przebieg; przy bardzo długich przebiegach (> JWT exp)
        # dodać ponowne logowanie po 401.
        client.headers["Authorization"] = f"Bearer {login(client, args.user, password)}"
        for i, source in enumerate(files, 1):
            print(f"[{i}/{len(files)}] {source.name} ... ", end="", flush=True)
            try:
                error = convert(client, source, args.output)
            except httpx.HTTPError as exc:
                error = f"{type(exc).__name__}: {exc}"
            print(error or "OK")
            if error:
                failed.append((source.name, error))

    print(f"\nGotowe: {len(files) - len(failed)}/{len(files)} w {args.output}/")
    for name, error in failed:
        print(f"  BŁĄD {name}: {error}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
