# Spec §11.1. Fallback: python:3.14-slim-trixie, jeśli brakuje kół musllinux (ryzyko R2).
FROM python:3.14-alpine3.22 AS builder
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

FROM python:3.14-alpine3.22 AS runtime
# Ta warstwa zależy tylko od obrazu bazowego, więc zostaje w cache. Nie zmieniaj tekstu polecenia
# bez potrzeby: każda zmiana instaluje od nowa ~270 pakietów (LibreOffice).
RUN apk add --no-cache tesseract-ocr tesseract-ocr-data-pol libmagic \
        libreoffice-writer libreoffice-calc \
 && adduser -D -H -u 10001 -s /sbin/nologin app
WORKDIR /srv
COPY --from=builder /srv/.venv /srv/.venv
COPY app ./app
ENV PATH="/srv/.venv/bin:$PATH" PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
USER app
EXPOSE 8000
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
