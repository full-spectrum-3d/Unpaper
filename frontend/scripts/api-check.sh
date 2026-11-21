#!/bin/sh
# Fails when the committed OpenAPI schema or generated client differ from what the backend produces.
set -eu

paths="../docs/openapi.json src/app/shared/api"

npm run api:generate
# porcelain covers modified, deleted and untracked files, unlike git diff.
# shellcheck disable=SC2086
changes=$(git status --porcelain -- $paths)
if [ -n "$changes" ]; then
  echo "$changes" >&2
  echo 'Kontrakt API nieaktualny: uruchom npm run api:generate i zacommituj zmiany' >&2
  exit 1
fi
