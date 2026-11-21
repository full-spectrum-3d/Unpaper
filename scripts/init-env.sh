#!/bin/sh
# Tworzy .env z .env.example: losowy JWT_SECRET, konto techniczne API_USER i hash hasła
# (argon2id liczony w obrazie API, więc na hoście wystarczy Docker).
#
#   scripts/init-env.sh [użytkownik]          # hasło wygenerowane losowo i wypisane raz
#   API_PASSWORD=... scripts/init-env.sh      # własne hasło
#
# Wymaga zbudowanego obrazu API (docker compose build). Nie nadpisuje istniejącego .env.
set -eu

cd "$(dirname "$0")/.."
image="${API_IMAGE:-coi-cf-api:0.1.0}"
user="${1:-admin}"

if [ -e .env ]; then
  echo ".env już istnieje - usuń go, jeśli chcesz wygenerować nowy." >&2
  exit 1
fi
if ! docker image inspect "$image" >/dev/null 2>&1; then
  echo "Brak obrazu $image - najpierw: docker compose build" >&2
  exit 1
fi

random() { head -c "$1" /dev/urandom | base64 | tr -d '\n=+/'; }

secret="$(random 48)"
generated=0
if [ -z "${API_PASSWORD:-}" ]; then
  API_PASSWORD="$(random 18)"
  generated=1
fi
hash="$(printf '%s\n' "$API_PASSWORD" |
  docker run --rm -i --network none "$image" python -m app.core.security hash-password --stdin)"

umask 077
awk -v secret="$secret" -v user="$user" -v hash="$hash" '
  /^JWT_SECRET=/        { print "JWT_SECRET=" secret; next }
  /^API_USER=/          { print "API_USER=" user; next }
  /^API_PASSWORD_HASH=/ { print "API_PASSWORD_HASH=\047" hash "\047"; next }
  { print }
' .env.example > .env

echo "Utworzono .env (użytkownik: $user)."
if [ "$generated" -eq 1 ]; then
  echo "Hasło (zapisz je, nie jest nigdzie przechowywane): $API_PASSWORD"
fi
