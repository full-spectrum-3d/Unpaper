.PHONY: setup build env model up down logs test convert-all password-hash

# Pierwsze uruchomienie: obrazy, .env z sekretami, model w wolumenie.
setup: build env model

build:
	docker compose build

env:
	scripts/init-env.sh

# Model z LLM_MODEL (domyślnie qwen3:8b) pobiera jednorazowy kontener z dostępem do sieci.
# Tylko z profilem `ollama` (COMPOSE_PROFILES w .env); z zewnętrznym serwerem modelu nic nie robi.
model:
	@if docker compose config --services | grep -qx llm; then \
		docker compose --profile setup run --rm llm-pull; \
	else \
		echo "Profil ollama wyłączony (COMPOSE_PROFILES) - pomijam pobieranie modelu, API użyje LLM_BASE_URL."; \
	fi

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

test:
	cd backend && uv run pytest

convert-all:
	uv run --project backend python scripts/convert_all.py --input materials --output out

# Hash argon2id hasła do API_PASSWORD_HASH (liczony w obrazie API, bez lokalnego Pythona).
password-hash:
	docker run --rm -it --network none coi-cf-api:0.1.0 python -m app.core.security hash-password
