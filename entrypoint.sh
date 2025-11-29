#!/usr/bin/env bash
set -e

# Apply database migrations before starting the app
alembic upgrade head

# Execute the container's main process (what's set as CMD)
exec "$@"
