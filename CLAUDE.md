# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

FastAPI + React + PostgreSQL full-stack template with JWT-based authentication using HttpOnly cookies. A Caddy reverse proxy fronts both services on the same origin for Safari/iOS cookie compatibility.

## Architecture

- **Backend:** FastAPI (Python 3.12) with async SQLAlchemy, asyncpg, Alembic migrations
- **Frontend:** React 19 + TypeScript + Vite + React Router v7
- **Database:** PostgreSQL 17
- **Proxy:** Caddy (auto-TLS, routes `/api/*` to backend, everything else to frontend)
- **Auth flow:** Login sets HttpOnly `access_token` (15min) and `refresh_token` (7d) cookies. Frontend API client auto-refreshes on 401. Refresh tokens are rotated on each use (old revoked, new issued).

## Build and Run Commands

### Local development (Docker)
```bash
docker compose -f docker-compose.yml -f docker-compose.local.yml up --build
```

### Production
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

### Backend
```bash
# Install dependencies
pip install -r backend/requirements.txt

# Run server (with hot reload)
cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Run all tests (requires PostgreSQL with app_test database)
cd backend && pytest tests/ -v --tb=short

# Run a single test file
cd backend && pytest tests/test_auth_api.py -v

# Run a single test class or method
cd backend && pytest tests/test_auth_api.py::TestLogin::test_login_success -v

# Lint and format (CI uses ruff)
ruff check backend/
ruff format --check backend/

# Database migrations
cd backend && alembic upgrade head
cd backend && alembic revision --autogenerate -m "description"
```

### Frontend
```bash
cd frontend && npm ci --legacy-peer-deps

# Dev server
cd frontend && npm run dev

# Build (typecheck + vite build)
cd frontend && npm run build

# Lint (ESLint 10, flat config)
cd frontend && npm run lint

# Typecheck only
cd frontend && npm run typecheck

# Run all tests
cd frontend && npm test

# Run tests in watch mode
cd frontend && npm run test:watch
```

## Key Environment Variables

`JWT_SECRET_KEY` is **required** (no default). Copy `.env.example` to `.env` and generate with:
```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

Backend tests need `DATABASE_URL` pointing to a test database and `JWT_SECRET_KEY` set. The test conftest derives the test DB URL by replacing `/app` with `/app_test` in `DATABASE_URL`.

## Code Layout Conventions

### Backend (`backend/app/`)
- `config.py` — Pydantic `Settings` (env-driven), singleton `settings` instance
- `database.py` — Async SQLAlchemy engine, session factory, `Base` declarative base, `get_db` dependency
- `models/` — SQLAlchemy models (`User`, `RefreshToken`); all models re-exported from `__init__.py`
- `schemas/` — Pydantic request/response models
- `services/` — Business logic (password hashing, JWT creation/verification, token rotation)
- `api/` — FastAPI routers; `router.py` mounts sub-routers under `/api/v1`
- `dependencies.py` — FastAPI dependencies (`get_current_user` reads `access_token` cookie)

### Frontend (`frontend/src/`)
- `api/client.ts` — `ApiClient` class with auto-refresh on 401; exports `api` singleton
- `contexts/AuthContext.tsx` — `AuthProvider` + `useAuth` hook; checks `/api/v1/auth/me` on mount
- `components/` — `LoginForm`, `RegisterForm`, `ProtectedRoute`
- `pages/` — Route-level page components
- Tests in `frontend/tests/`, use Vitest + React Testing Library, mock `api/client.ts`

### Auth Endpoints
All under `/api/v1/auth`: `POST /register`, `POST /login`, `POST /refresh`, `POST /logout`, `GET /me`

## Testing Patterns

**Backend:** pytest + pytest-asyncio. Tests use a separate `app_test` database with tables created/dropped per test via the `setup_db` autouse fixture. The `client` fixture overrides `get_db` to use the test session. `registered_user` and `authenticated_client` fixtures handle common setup.

**Frontend:** Vitest with jsdom environment. Tests mock `../src/api/client` to avoid network calls. Components are wrapped with `BrowserRouter` + `AuthProvider` via a `renderWithProviders` helper. Use `vi.hoisted()` when declaring mock variables referenced inside `vi.mock()` factory functions (see `AuthContext.test.tsx` for the pattern).

## CI Workflows (GitHub Actions)

- `backend.yml` — ruff lint/format check, pytest with Postgres service container, Docker build
- `frontend.yml` — ESLint, TypeScript typecheck, Vitest, Docker build (prod target)
- `proxy.yml` — Caddyfile validation, Docker build

Each workflow triggers only on changes to its respective directory.
