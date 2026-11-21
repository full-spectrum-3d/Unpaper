.PHONY: setup build env model up down logs test test-frontend convert-all password-hash

# Pierwsze uruchomienie: .env z sekretami, obrazy, model w wolumenie. `.env` przed `build`:
# COMPOSE_PROFILES z .env decyduje, czy compose buduje obraz llm.
setup: env build model

build:
	docker compose build

# Hash hasła liczy obraz API, więc bez .env budujemy go samym `docker build` (compose bez
# .env nie przechodzi walidacji env_file). Istniejący .env zostaje - `make setup` można powtórzyć.
env:
	@if [ -e .env ]; then echo ".env istnieje - pomijam."; else \
		docker build -t coi-cf-api:0.1.0 ./backend && scripts/init-env.sh; \
	fi

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

test-frontend:
	cd frontend && npm test -- --watch=false

# Wymaga działającego API (make up). Login: API_USER (środowisko albo .env), hasło: API_PASSWORD
# albo pytanie w terminalu.
convert-all:
	uv run --project backend python scripts/convert_all.py --input materials --output out

# Hash argon2id hasła do API_PASSWORD_HASH (liczony w obrazie API, bez lokalnego Pythona).
password-hash:
	docker run --rm -it --network none coi-cf-api:0.1.0 python -m app.core.security hash-password
