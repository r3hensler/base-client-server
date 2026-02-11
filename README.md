# FastAPI + React Auth Template

Full-stack authentication template using JWT with HttpOnly cookies, fronted by a Caddy reverse proxy for Safari/iOS cookie compatibility.

## Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI, SQLAlchemy 2 (async), PostgreSQL 17 |
| Frontend | React 19, TypeScript, Vite 6, React Router v7 |
| Proxy | Caddy 2 (auto-TLS) |
| Testing | pytest + pytest-asyncio (backend), Vitest + React Testing Library (frontend) |
| CI | GitHub Actions (lint, test, Docker build per component) |

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
- Node.js 22+ (for local frontend development without Docker)
- Python 3.12+ (for local backend development without Docker)

### Setup

1. Copy environment config:
   ```bash
   cp .env.example .env
   ```

2. Generate a JWT secret and paste it as the `JWT_SECRET_KEY` value in `.env`:
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(64))"
   ```

3. Start all services:
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.local.yml up --build
   ```

4. Open https://localhost and accept the self-signed certificate.

5. Register a new user, log in, and verify the dashboard loads.

## Docker Compose Environments

| Command | Use Case |
|---------|----------|
| `docker compose -f docker-compose.yml -f docker-compose.local.yml up --build` | Local development (hot reload, exposed DB) |
| `docker compose -f docker-compose.yml -f docker-compose.staging.yml up -d --build` | Staging (prod build, Let's Encrypt TLS) |
| `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build` | Production (restart policies, cert persistence) |

### Environment Differences

| Setting | Local | Staging | Prod |
|---------|-------|---------|------|
| Backend hot reload | Yes | No | No |
| Frontend target | dev (Vite HMR) | prod (static) | prod (static) |
| DB port exposed | Yes (5432) | No | No |
| Restart policy | No | unless-stopped | always |
| TLS | Self-signed (Caddy) | Let's Encrypt | Let's Encrypt |
| COOKIE_SECURE | false | true | true |

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

# Database migrations
cd backend && alembic upgrade head
cd backend && alembic revision --autogenerate -m "description"
```

### Frontend

```bash
cd frontend && npm ci --legacy-peer-deps

# Dev server
npm run dev

# Build (typecheck + vite build)
npm run build

# Lint (ESLint 10, flat config)
npm run lint

# Typecheck only
npm run typecheck

# Tests
npm test
```

### Proxy

```bash
# Validate Caddyfile (requires Docker)
docker run --rm -v $(pwd)/proxy/Caddyfile:/etc/caddy/Caddyfile caddy:2-alpine caddy validate --config /etc/caddy/Caddyfile
```

## Auth Flow

1. `POST /api/v1/auth/register` — create account
2. `POST /api/v1/auth/login` — sets `access_token` (15min) and `refresh_token` (7d) HttpOnly cookies
3. `GET /api/v1/auth/me` — returns current user (requires valid access token)
4. `POST /api/v1/auth/refresh` — rotates refresh token, issues new access token
5. `POST /api/v1/auth/logout` — revokes refresh token, clears cookies

The frontend API client automatically attempts a token refresh on 401 responses.

## CI/CD

Three GitHub Actions workflows run on push and pull request, scoped to their respective directories:

| Workflow | Triggers On | Jobs |
|----------|-------------|------|
| `backend.yml` | `backend/**` | ruff lint/format, pytest with Postgres, Docker build |
| `frontend.yml` | `frontend/**` | ESLint, TypeScript typecheck, Vitest, Docker build (prod) |
| `proxy.yml` | `proxy/**` | Caddyfile validation, Docker build |

## Project Structure

```
├── backend/
│   ├── app/
│   │   ├── api/          # FastAPI route handlers
│   │   ├── models/       # SQLAlchemy models (User, RefreshToken)
│   │   ├── schemas/      # Pydantic request/response models
│   │   ├── services/     # Business logic (auth, JWT, passwords)
│   │   ├── config.py     # Environment-driven settings
│   │   ├── database.py   # Async SQLAlchemy setup
│   │   └── dependencies.py
│   ├── alembic/          # Database migrations
│   ├── tests/            # pytest async tests
│   ├── Dockerfile
│   └── entrypoint.sh     # Runs migrations then starts uvicorn
├── frontend/
│   ├── src/
│   │   ├── api/          # Fetch wrapper with auto-refresh
│   │   ├── components/   # LoginForm, RegisterForm, ProtectedRoute
│   │   ├── contexts/     # AuthContext + useAuth hook
│   │   └── pages/        # Route-level page components
│   ├── tests/            # Vitest + React Testing Library
│   └── Dockerfile        # Multi-stage (dev/prod)
├── proxy/
│   ├── Caddyfile         # /api/* → backend, /* → frontend
│   └── Dockerfile
├── .github/workflows/    # CI pipelines (backend, frontend, proxy)
├── docker-compose.yml          # Base service definitions
├── docker-compose.local.yml    # Local dev overrides
├── docker-compose.staging.yml  # Staging overrides
├── docker-compose.prod.yml     # Production overrides
├── docker-compose.test.yml     # Standalone test database
├── .env.example
└── docs/
    ├── FastAPI_React_Auth_Template_Guide.md
    ├── IMPLEMENTATION_PLAN.md
    └── PRE_PRODUCTION_CHECKLIST.md
```

## Security Notes

- **HttpOnly cookies** prevent XSS access to tokens
- **SameSite=Lax** provides implicit CSRF protection for POST-only mutations
- **Token rotation** on every refresh limits the window for stolen refresh tokens
- **Refresh token path scoping** (`/api/v1/auth`) minimizes cookie exposure
- **Caddy auto-TLS** ensures `Secure` cookies work in all environments
- **No rate limiting included** — add `slowapi` middleware before deploying

See [docs/PRE_PRODUCTION_CHECKLIST.md](docs/PRE_PRODUCTION_CHECKLIST.md) for a full production readiness checklist.

## License

MIT
