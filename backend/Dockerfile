# Spec §11.1. Obrazy bazowe: oficjalne, wersja + digest (bez `latest`).
# Fallback: python:3.14-slim-trixie, jeśli brakuje kół musllinux (ryzyko R2).
FROM python:3.14-alpine3.22@sha256:6b91e66ab2a880ce9ca5a1b91c70f45963ff71ff68268df056336e1a657d5efd AS builder
# Wersja przypięta (tag + digest): nowe wydanie uv nie unieważnia cache'u buildera.
COPY --from=ghcr.io/astral-sh/uv:0.13.9@sha256:d3b601f0c7b118bc1753febf7c41cc80981df678445e0254284eecf84db79a7d /uv /usr/local/bin/uv
# Ta sama ścieżka co w obrazie runtime: skrypty w .venv/bin mają shebang z bezwzględną ścieżką.
WORKDIR /srv
# Cache uv poza warstwą: zmiana pyproject.toml uruchamia sync ponownie, ale bez ponownego pobierania pakietów.
ENV UV_LINK_MODE=copy UV_COMPILE_BYTECODE=0
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project
COPY app ./app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev

FROM python:3.14-alpine3.22@sha256:6b91e66ab2a880ce9ca5a1b91c70f45963ff71ff68268df056336e1a657d5efd AS runtime
# Pakiety apk bez wersji celowo: repozytorium Alpine trzyma tylko bieżącą wersję w gałęzi
# 3.22, więc przypięta wersja przestaje się budować po pierwszej łatce bezpieczeństwa.
# Powtarzalność daje obraz bazowy przypięty digestem; łatki wchodzą przy przebudowie.
# Ta warstwa zależy tylko od obrazu bazowego, więc zostaje w cache. Nie zmieniaj tekstu polecenia
# bez potrzeby: każda zmiana instaluje od nowa ~270 pakietów (LibreOffice).
RUN apk add --no-cache tesseract-ocr tesseract-ocr-data-pol libmagic \
        libreoffice-writer libreoffice-calc \
 && adduser -D -H -u 10001 -s /sbin/nologin app
# Osobna warstwa, żeby nie unieważniać cache'u z LibreOffice powyżej: dane OSD do korekty
# orientacji skanów (Tesseract).
RUN apk add --no-cache tesseract-ocr-data-osd
WORKDIR /srv
COPY --from=builder /srv/.venv /srv/.venv
COPY app ./app
ENV PATH="/srv/.venv/bin:$PATH" PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
USER app
EXPOSE 8000
LABEL org.opencontainers.image.title="coi-cf-api" \
      org.opencontainers.image.version="0.1.0"
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD wget -qO- http://127.0.0.1:8000/api/v1/health/live || exit 1
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-server-header"]
