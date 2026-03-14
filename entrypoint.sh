#!/bin/sh
# Writes the GOOGLE_CREDENTIALS secret (injected by Cloud Run) to a file,
# then runs main.py with whatever arguments were passed to the container.

set -e

echo "$GOOGLE_CREDENTIALS" > /app/credentials.json

exec python main.py "$@"
