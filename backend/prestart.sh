#!/usr/bin/env bash
set -e

echo "Running database migrations..."
alembic upgrade head
echo "Database migrations completed successfully!"
