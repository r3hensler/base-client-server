#!/bin/bash
set -e

# Environment variables for the test Postgres instance
export DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/app
export TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/app_test
export JWT_SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(64))")

echo "🐘 Starting PostgreSQL..."
docker compose -f docker-compose.test.yml up -d
echo "Waiting for database to be ready..."
until docker compose -f docker-compose.test.yml exec -T db pg_isready -U postgres > /dev/null 2>&1; do
  sleep 1
done
echo "Database is ready!"

echo ""
echo "📦 Installing backend dependencies..."
cd backend
pip install -r requirements.txt

echo ""
echo "🗄️  Creating test database..."
docker compose -f docker-compose.test.yml exec -T db psql -U postgres -c "CREATE DATABASE app_test;" 2>/dev/null || echo "Test database already exists"

echo ""
# Fail fast if committed migration is missing
if [ ! -f "alembic/versions/6260199ba8ed_create_users_and_refresh_tokens.py" ]; then
    echo "❌ Expected migration file not found. Ensure migrations are committed."
    exit 1
fi

echo ""
echo "🔄 Running migrations on main database..."
alembic upgrade head

echo ""
echo "✅ Running tests..."
pytest tests/ -v --tb=short

echo ""
echo "🚀 Starting development server..."
echo "   Visit: http://localhost:8000/health"
echo "   API docs: http://localhost:8000/docs"
echo "   Press Ctrl+C to stop"
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
