.PHONY: build up down model test convert-all

build:
	docker compose build

up:
	docker compose up -d

down:
	docker compose down

model:
	docker compose run --rm llm ollama pull $${LLM_MODEL:-qwen3:8b}

test:
	cd backend && uv run pytest

convert-all:
	uv run --project backend python scripts/convert_all.py --input materials --output out
