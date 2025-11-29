#!/usr/bin/env bash
set -e

# Apply database migrations
alembic upgrade head

# Start the application
exec "$@"
