# FastAPI + React Auth Template

Full-stack authentication template using JWT with HttpOnly cookies, fronted by a Caddy reverse proxy for Safari/iOS cookie compatibility.

## Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI, SQLAlchemy 2 (async), PostgreSQL 17 |
| Frontend | React 19, TypeScript, Vite 6, React Router v7 |
| Proxy | Caddy 2 (auto-TLS) |
| Testing | pytest + pytest-asyncio (backend), Vitest + React Testing Library (frontend) |

## Architecture

```
              Browser
                │ HTTPS
              Caddy (:443/:80)
              ┌─┴──┐
         /api/*    /*
              │     │
          FastAPI  React
          (:8000)  (:5173)
              │
          PostgreSQL
          (:5432)
```

Authentication uses HttpOnly cookies set by the backend. The Caddy proxy ensures both frontend and API share the same origin, making cookies first-party for Safari/iOS compatibility.

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Node.js 22+ (for local frontend development)
- Python 3.12+ (for local backend development)

### Setup

1. Copy environment config:
   ```bash
   cp .env.example .env
   ```

2. Generate a JWT secret:
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(64))"
   ```
   Paste the output as the `JWT_SECRET_KEY` value in `.env`.

3. Start all services:
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.local.yml up --build
   ```

4. Open https://localhost (accept the self-signed certificate).

## Development

### Backend

```bash
pip install -r backend/requirements.txt

# Run server with hot reload
cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Run tests (requires PostgreSQL with app_test database)
cd backend && pytest tests/ -v --tb=short

# Lint
ruff check backend/
ruff format --check backend/
```

### Frontend

```bash
cd frontend && npm ci --legacy-peer-deps

# Dev server
npm run dev

# Build
npm run build

# Lint
npm run lint

# Typecheck
npm run typecheck

# Tests
npm test
```

## Auth Flow

1. `POST /api/v1/auth/register` — create account
2. `POST /api/v1/auth/login` — sets `access_token` (15min) and `refresh_token` (7d) HttpOnly cookies
3. `GET /api/v1/auth/me` — returns current user (requires valid access token)
4. `POST /api/v1/auth/refresh` — rotates refresh token, issues new access token
5. `POST /api/v1/auth/logout` — revokes refresh token, clears cookies

The frontend API client automatically attempts a token refresh on 401 responses.

## Project Structure

```
├── backend/
│   ├── app/
│   │   ├── api/          # FastAPI route handlers
│   │   ├── models/       # SQLAlchemy models
│   │   ├── schemas/      # Pydantic request/response models
│   │   ├── services/     # Business logic (auth, JWT, passwords)
│   │   ├── config.py     # Environment-driven settings
│   │   ├── database.py   # Async SQLAlchemy setup
│   │   └── dependencies.py
│   ├── alembic/          # Database migrations
│   ├── tests/            # pytest async tests
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── api/          # Fetch wrapper with auto-refresh
│   │   ├── components/   # LoginForm, RegisterForm, ProtectedRoute
│   │   ├── contexts/     # AuthContext + useAuth hook
│   │   └── pages/        # Route-level page components
│   ├── tests/            # Vitest + React Testing Library
│   └── Dockerfile        # Multi-stage (dev/prod)
├── proxy/                # Caddy config (not yet created)
├── docs/
│   ├── FastAPI_React_Auth_Template_Guide.md
│   └── IMPLEMENTATION_PLAN.md
└── docker-compose*.yml
```

## Implementation Status

Phases 0-6 of 10 complete. See [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) for details.

| Phase | Component | Status |
|-------|-----------|--------|
| 0 | Environment Setup | Complete |
| 1 | Backend Foundation | Complete |
| 2 | Backend Auth Service | Complete |
| 3 | Backend Tests + Docker | Complete |
| 4 | Frontend Foundation | Complete |
| 5 | Frontend Auth | Complete |
| 6 | Frontend Tests + Docker | Complete |
| 7 | Caddy Proxy | Pending |
| 8 | Docker Compose | Pending |
| 9 | CI Workflows | Pending |

## License

MIT
