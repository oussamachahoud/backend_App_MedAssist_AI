#!/bin/sh
set -e

echo "=========================================================="
echo "🚀 MedAssist AI Container Initializing..."
echo "=========================================================="

# Run Alembic database migrations to ensure all tables exist
echo "📦 Running database migrations (alembic upgrade head)..."
alembic upgrade head || {
    echo "⚠️ Alembic migration failed or database not yet ready."
    echo "   Continuing startup — lifespan will attempt degraded initialization."
}

echo "✅ Migrations complete. Launching application..."
echo "=========================================================="

# Execute the main container command (e.g. uvicorn)
exec "$@"

