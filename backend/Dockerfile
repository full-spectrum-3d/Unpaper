# Spec §11.1. Fallback: python:3.14-slim-trixie, jeśli brakuje kół musllinux (ryzyko R2).
FROM python:3.14-alpine3.22 AS builder
# TODO: przypiąć wersję uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /build
COPY pyproject.toml uv.lock* ./
RUN uv sync --no-dev --no-install-project
COPY app ./app
RUN uv sync --no-dev

FROM python:3.14-alpine3.22 AS runtime
RUN apk add --no-cache tesseract-ocr tesseract-ocr-data-pol libmagic \
        libreoffice-writer libreoffice-calc \
 && adduser -D -H -u 10001 -s /sbin/nologin app
WORKDIR /srv
COPY --from=builder /build/.venv /srv/.venv
COPY app ./app
ENV PATH="/srv/.venv/bin:$PATH" PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
USER app
EXPOSE 8000
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
