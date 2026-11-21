#!/bin/sh
# Jednorazowe pobranie modelu do wolumenu (make model). Usługa `llm` działa w sieci bez
# dostępu do internetu, więc pobieramy osobnym kontenerem z tym samym wolumenem.
set -eu
model="${LLM_MODEL:-qwen3:8b}"
ollama serve >/dev/null 2>&1 &
server=$!
trap 'kill "$server" 2>/dev/null || true' EXIT
i=0
until ollama list >/dev/null 2>&1; do
  i=$((i + 1))
  [ "$i" -gt 60 ] && { echo "Serwer Ollama nie wystartował" >&2; exit 1; }
  sleep 1
done
echo "Pobieranie modelu $model ..."
ollama pull "$model"
ollama list
