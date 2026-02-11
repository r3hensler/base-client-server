# Implementation Plan: FastAPI + React Auth Template

This document provides a phased implementation plan for building the full-stack authentication template described in `/docs/FastAPI_React_Auth_Template_Guide.md`.

---

## Current State Assessment

**Repository Status:** Backend and frontend complete, infrastructure pending

**Overall Progress:** Phases 0-6 complete (38/54 files created) — **70% of files, 7/10 phases**

| Component | Status | Notes |
|-----------|--------|-------|
| Environment Config | **Complete** | `.env.example` and `.gitignore` created |
| Backend (FastAPI) | **Complete** | All models, services, API endpoints, tests, Dockerfile |
| Frontend (React) | **Complete** | All components, pages, API client, auth context, tests, Dockerfile |
| Proxy (Caddy) | Not started | No `proxy/` directory exists |
| Docker Compose | Partial | `docker-compose.test.yml` exists; main compose files pending |
| CI Workflows | Not started | No `.github/workflows/` directory exists |

**Additional files created (not in original plan):**
- `docker-compose.test.yml` — Test environment compose file
- `test-backend.sh` — Backend test runner script
- `docs/PRE_PRODUCTION_CHECKLIST.md` — Production readiness checklist
- `backend/alembic/script.py.mako` — Alembic migration template
- `backend/alembic/versions/.gitkeep` — Placeholder for migrations directory
- `backend/alembic/versions/6260199ba8ed_create_users_and_refresh_tokens.py` — Initial migration

---

## Dependency Analysis

The implementation order matters because components have dependencies on each other:

```
                    Environment Setup (.env.example)
                              |
                              v
    +-------------------------+-------------------------+
    |                         |                         |
    v                         v                         v
Backend Core           Frontend Core              Proxy Config
(models, config)       (package.json,            (Caddyfile)
    |                  tsconfig)                      |
    v                         |                       |
Backend Auth                  v                       |
(services, API)        Frontend Auth                  |
    |                  (API client,                   |
    v                  AuthContext)                   |
Backend Tests                 |                       |
    |                         v                       |
    |                  Frontend Tests                 |
    |                         |                       |
    +------------+------------+                       |
                 |                                    |
                 v                                    |
          Docker Compose <----------------------------+
                 |
                 v
           CI Workflows
```

**Key Dependencies:**
1. Backend auth service depends on database models and configuration
2. Frontend auth context depends on API client
3. Docker Compose requires all Dockerfiles to exist
4. CI workflows require tests to be in place
5. Proxy configuration is independent but validates the full system

---

## Implementation Phases

### Phase 0: Environment Foundation — COMPLETE
**Complexity:** Low | **Estimated Time:** 30 minutes

**Objective:** Establish the environment configuration that all other components depend on.

**Deliverables:**
- [x] `.env.example` with all required environment variables
- [x] `.gitignore` for Python, Node, and Docker artifacts

**Files to Create:**
```
.env.example
.gitignore
```

**Prerequisites:** None

**Blockers/Risks:** None

---

### Phase 1: Backend Foundation — COMPLETE
**Complexity:** Medium | **Estimated Time:** 2-3 hours

**Objective:** Establish the core backend structure with database connectivity and configuration.

**Deliverables:**
- [x] Project structure with `backend/app/` directory
- [x] Configuration module (`config.py`)
- [x] Database setup with async SQLAlchemy (`database.py`)
- [x] User and RefreshToken models
- [x] Alembic migration setup
- [x] Requirements file
- [x] Basic health check endpoint

**Files to Create:**
```
backend/
  app/
    __init__.py
    config.py
    database.py
    main.py
    models/
      __init__.py
      user.py
  alembic/
    env.py
    versions/
      (initial migration)
  alembic.ini
  requirements.txt
```

**Prerequisites:**
- Phase 0 complete (environment variables defined)

**Architectural Decisions:**

| Decision | Choice | Rationale |
|----------|--------|-----------|
| ORM | SQLAlchemy 2.0 async | Native async support, type hints, mature ecosystem |
| Connection pool | Default asyncpg pool | Sufficient for most workloads; tune if needed |
| Migration tool | Alembic | Standard for SQLAlchemy, supports async |
| UUID primary keys | Yes | Prevents ID enumeration, works well in distributed systems |

**Blockers/Risks:**
- Alembic async configuration can be tricky; follow the guide's `env.py` exactly
- Ensure `app_test` database is created for test runs

---

### Phase 2: Backend Authentication Service — COMPLETE
**Complexity:** High | **Estimated Time:** 3-4 hours

**Objective:** Implement the complete authentication service layer and API endpoints.

**Deliverables:**
- [x] Pydantic schemas for auth requests/responses
- [x] Auth service (password hashing, JWT creation/verification, token rotation)
- [x] Auth dependencies (`get_current_user`)
- [x] Auth API endpoints (register, login, refresh, logout, me)
- [x] Router configuration

**Files to Create:**
```
backend/app/
  schemas/
    __init__.py
    auth.py
  services/
    __init__.py
    auth.py
  api/
    __init__.py
    router.py
    auth.py
  dependencies.py
```

**Prerequisites:**
- Phase 1 complete (models and database exist)

**Architectural Decisions:**

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Password hashing | bcrypt via passlib | Industry standard, adaptive cost factor |
| JWT library | PyJWT | Lightweight, well-maintained |
| Token storage | HttpOnly cookies | XSS protection, automatic browser attachment |
| Refresh token storage | SHA256 hash in DB | Never store raw tokens; enables server-side revocation |
| Token rotation | Rotate on every refresh | Limits window for token theft |

**Security Considerations:**
- Refresh token path scoped to `/api/v1/auth` to minimize exposure
- Access token short-lived (15 min) to limit damage from theft
- Revoked tokens tracked for replay detection

**Blockers/Risks:**
- Cookie settings must match environment (Secure=true requires HTTPS)
- SameSite=Lax must be understood for CSRF implications

---

### Phase 3: Backend Testing & Docker — COMPLETE
**Complexity:** Medium | **Estimated Time:** 2-3 hours

**Objective:** Comprehensive test coverage for auth functionality and Docker containerization.

**Deliverables:**
- [x] Test configuration (`conftest.py`)
- [x] API tests for all auth endpoints
- [x] Service unit tests
- [x] Backend Dockerfile
- [x] Entrypoint script with migration

**Files to Create:**
```
backend/
  tests/
    __init__.py
    conftest.py
    test_auth_api.py
    test_auth_service.py
  Dockerfile
  entrypoint.sh
```

**Prerequisites:**
- Phase 2 complete (auth service and API exist)
- `app_test` database available

**Test Coverage Goals:**
- Registration: success, duplicate email, invalid email, short password
- Login: success, wrong password, nonexistent user
- Me: authenticated, unauthenticated
- Refresh: token rotation, missing token
- Logout: cookie clearing, token revocation

**Blockers/Risks:**
- Test database isolation is critical; each test should start fresh
- pytest-asyncio configuration must match SQLAlchemy async patterns

---

### Phase 4: Frontend Foundation — COMPLETE
**Complexity:** Medium | **Estimated Time:** 2-3 hours

**Objective:** Establish React application structure with TypeScript, Vite, and testing setup.

**Deliverables:**
- [x] Package configuration with all dependencies
- [x] TypeScript configuration
- [x] Vite configuration (dev server proxy, test setup)
- [x] ESLint flat config for ESLint 10
- [x] Entry point and HTML shell
- [x] Test setup file

**Files to Create:**
```
frontend/
  src/
    main.tsx
    App.tsx
    vite-env.d.ts
  tests/
    setup.ts
  index.html
  package.json
  package-lock.json (generated)
  tsconfig.json
  vite.config.ts
  eslint.config.mjs
```

**Prerequisites:**
- Phase 0 complete (environment variables for any build-time config)

**Architectural Decisions:**

| Decision | Choice | Rationale |
|----------|--------|-----------|
| React version | 19 | Latest stable, concurrent features |
| Build tool | Vite 6 | Fast HMR, native ESM, excellent DX |
| Router | React Router v7 | Latest patterns, data APIs |
| Testing | Vitest + React Testing Library | Fast, Vite-native, component testing best practices |
| Linting | ESLint 10 flat config | Required format for ESLint 10+ |

**Blockers/Risks:**
- ESLint 10 requires flat config format; `.eslintrc` will not work
- Node 22 required for latest npm features

---

### Phase 5: Frontend Authentication — COMPLETE
**Complexity:** High | **Estimated Time:** 3-4 hours

**Objective:** Implement API client with auto-refresh and auth context for state management.

**Deliverables:**
- [x] API client with 401 handling and token refresh
- [x] Auth context provider and hook
- [x] Login form component
- [x] Register form component
- [x] Protected route wrapper
- [x] Page components (Login, Register, Dashboard)
- [x] Router setup with protected routes

**Files to Create:**
```
frontend/src/
  api/
    client.ts
  contexts/
    AuthContext.tsx
  components/
    LoginForm.tsx
    RegisterForm.tsx
    ProtectedRoute.tsx
  pages/
    LoginPage.tsx
    RegisterPage.tsx
    DashboardPage.tsx
```

**Prerequisites:**
- Phase 4 complete (React app skeleton exists)
- Phase 2 complete (backend API to integrate against)

**Architectural Decisions:**

| Decision | Choice | Rationale |
|----------|--------|-----------|
| State management | React Context | Sufficient for auth state; avoids Redux complexity |
| API client | Custom fetch wrapper | Full control over cookie handling and retry logic |
| Auto-refresh | Intercept 401, retry once | Transparent token refresh without user interruption |
| Cookie handling | `credentials: "same-origin"` | Required for browser to send/receive cookies |

**Critical Implementation Details:**
- API client must not retry on `/auth/refresh` endpoint (infinite loop)
- `AuthError` thrown on refresh failure for logout handling
- Initial auth check on app mount via `/api/v1/auth/me`

**Blockers/Risks:**
- Frontend must be served through same origin as API (Caddy) for cookies to work
- Safari/iOS cookie behavior requires same-origin setup

---

### Phase 6: Frontend Testing & Docker — COMPLETE
**Complexity:** Medium | **Estimated Time:** 2-3 hours

**Objective:** Component tests and Docker build configuration.

**Deliverables:**
- [x] LoginForm tests
- [x] RegisterForm tests
- [x] AuthContext tests
- [x] Multi-stage Dockerfile (dev and prod targets)

**Files to Create:**
```
frontend/
  tests/
    LoginForm.test.tsx
    RegisterForm.test.tsx
    AuthContext.test.tsx
  Dockerfile
```

**Prerequisites:**
- Phase 5 complete (components to test exist)

**Test Strategy:**
- Mock `api/client.ts` module to avoid network calls
- Use `renderWithProviders` helper for consistent context setup
- Test error states, loading states, and success callbacks

**Docker Build Targets:**
- `dev`: Uses Vite dev server with hot reload
- `prod`: Builds static assets, serves via Caddy

**Blockers/Risks:**
- Module mocking in Vitest requires correct import paths
- Multi-stage Docker build needs careful layer caching

---

### Phase 7: Caddy Proxy
**Complexity:** Low | **Estimated Time:** 1 hour

**Objective:** Configure reverse proxy for same-origin cookie handling.

**Deliverables:**
- [ ] Caddyfile with routing rules
- [ ] Proxy Dockerfile

**Files to Create:**
```
proxy/
  Caddyfile
  Dockerfile
```

**Prerequisites:**
- Backend Dockerfile exists (Phase 3)
- Frontend Dockerfile exists (Phase 6)

**Routing Rules:**
- `/api/*` -> `backend:8000`
- `/health` -> `backend:8000`
- `/*` -> `frontend:5173`

**Architectural Decisions:**

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Proxy server | Caddy 2 | Automatic HTTPS, simple config, good performance |
| TLS handling | Caddy auto-provision | Zero-config Let's Encrypt in production |
| Local dev TLS | Self-signed via Caddy | Enables testing Secure cookies locally |

**Blockers/Risks:**
- Domain configuration varies by environment; use `{$SITE_ADDRESS}` env var
- Local dev requires accepting self-signed certificate once

---

### Phase 8: Docker Compose Integration
**Complexity:** Medium | **Estimated Time:** 2 hours

**Objective:** Complete Docker Compose setup for all environments.

**Deliverables:**
- [ ] Base `docker-compose.yml`
- [ ] Local override (`docker-compose.local.yml`)
- [ ] Staging override (`docker-compose.staging.yml`)
- [ ] Production override (`docker-compose.prod.yml`)

**Files to Create:**
```
docker-compose.yml
docker-compose.local.yml
docker-compose.staging.yml
docker-compose.prod.yml
```

**Prerequisites:**
- All Dockerfiles exist (Phases 3, 6, 7)
- Environment variables defined (Phase 0)

**Environment Differences:**

| Setting | Local | Staging | Prod |
|---------|-------|---------|------|
| Backend hot reload | Yes | No | No |
| Frontend target | dev | prod | prod |
| DB port exposed | Yes | No | No |
| Restart policy | No | unless-stopped | always |
| TLS certificates | Self-signed | Let's Encrypt | Let's Encrypt |

**Blockers/Risks:**
- Volume mounts for hot reload can have performance issues on macOS
- Database healthcheck must complete before backend starts

---

### Phase 9: CI/CD Workflows
**Complexity:** Medium | **Estimated Time:** 2 hours

**Objective:** GitHub Actions workflows for automated testing and builds.

**Deliverables:**
- [ ] Backend workflow (lint, format check, test, docker build)
- [ ] Frontend workflow (lint, typecheck, test, docker build)
- [ ] Proxy workflow (validate Caddyfile, docker build)

**Files to Create:**
```
.github/
  workflows/
    backend.yml
    frontend.yml
    proxy.yml
```

**Prerequisites:**
- All tests exist (Phases 3, 6)
- All Dockerfiles exist (Phases 3, 6, 7)

**Workflow Triggers:**
- Each workflow triggers only on changes to its respective directory
- Runs on both push and pull_request events

**CI Services:**
- Backend tests require PostgreSQL service container

**Blockers/Risks:**
- GitHub Actions PostgreSQL service requires explicit health check
- Test database (`app_test`) must be created by Postgres container

---

## Implementation Order Summary

| Phase | Component | Depends On | Complexity | Est. Time | Status |
|-------|-----------|------------|------------|-----------|--------|
| 0 | Environment Setup | None | Low | 30 min | **COMPLETE** |
| 1 | Backend Foundation | Phase 0 | Medium | 2-3 hrs | **COMPLETE** |
| 2 | Backend Auth Service | Phase 1 | High | 3-4 hrs | **COMPLETE** |
| 3 | Backend Tests + Docker | Phase 2 | Medium | 2-3 hrs | **COMPLETE** |
| 4 | Frontend Foundation | Phase 0 | Medium | 2-3 hrs | **COMPLETE** |
| 5 | Frontend Auth | Phase 4, 2 | High | 3-4 hrs | **COMPLETE** |
| 6 | Frontend Tests + Docker | Phase 5 | Medium | 2-3 hrs | **COMPLETE** |
| 7 | Caddy Proxy | Phase 3, 6 | Low | 1 hr | Not started |
| 8 | Docker Compose | Phase 3, 6, 7 | Medium | 2 hrs | Not started |
| 9 | CI Workflows | Phase 3, 6, 7 | Medium | 2 hrs | Not started |

**Total Estimated Time:** 20-28 hours

**Parallel Opportunities:**
- Phases 1-3 (backend) and Phases 4-6 (frontend) can proceed in parallel after Phase 0
- Phase 7 can start as soon as backend and frontend Dockerfiles exist

---

## Critical Path

The minimum viable working system requires:

```
Phase 0 -> Phase 1 -> Phase 2 -> Phase 3 (Backend complete)
                |
                +-> Phase 4 -> Phase 5 -> Phase 6 (Frontend complete)    <<<< YOU ARE HERE
                                   |
                                   +-> Phase 7 -> Phase 8 (Full stack running)
```

**MVP Milestone:** After Phase 8, the full authentication flow works locally.

**Next Step:** Phase 7 (Caddy Proxy) — all backend and frontend prerequisites are met.

---

## Verification Checkpoints

### After Phase 3 (Backend Complete)
- [ ] `cd backend && pytest tests/ -v` passes all tests
- [ ] `ruff check backend/` passes
- [ ] `docker build -t app-backend ./backend` succeeds

### After Phase 6 (Frontend Complete)
- [x] `cd frontend && npm test` passes all tests (14 tests, 4 suites)
- [x] `cd frontend && npx eslint .` passes
- [x] `cd frontend && npx tsc --noEmit` passes
- [ ] `docker build --target prod -t app-frontend ./frontend` succeeds

### After Phase 8 (Full Stack)
- [ ] `docker compose -f docker-compose.yml -f docker-compose.local.yml up --build` starts all services
- [ ] Navigate to `https://localhost` (accept self-signed cert)
- [ ] Register a new user
- [ ] Login with the user
- [ ] Dashboard shows user email
- [ ] Logout works
- [ ] Refresh a protected page while logged in (verifies cookie persistence)
- [ ] Wait 15+ minutes and verify auto-refresh works on API call

### After Phase 9 (CI Complete)
- [ ] Push to a branch triggers all relevant workflows
- [ ] All workflow checks pass

---

## Risk Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| Cookie not sent in Safari | Auth broken on iOS | Ensure same-origin via Caddy; verify SameSite=Lax |
| Test database not created | Backend CI fails | Create `app_test` DB in Postgres container init |
| Alembic async config wrong | Migrations fail | Follow guide's `env.py` exactly |
| ESLint 10 config format | Lint fails | Use flat config (`eslint.config.mjs`), not `.eslintrc` |
| Hot reload slow on macOS | Poor dev experience | Use named volumes for node_modules |
| JWT secret not set | App crashes on start | Fail fast with `{?JWT_SECRET_KEY must be set}` |

---

## Post-Implementation Improvements

After the core template is working, consider these enhancements (not in scope for initial implementation):

1. **Rate Limiting**: Add `slowapi` middleware to `/auth/login` and `/auth/register`
2. **Refresh Token Cleanup**: Scheduled task to purge expired/revoked tokens
3. **Session Expired UX**: Explicit handling of `AuthError` with user notification
4. **Test Database URL**: Replace string replacement with dedicated `TEST_DATABASE_URL` env var
5. **Password Strength**: Add configurable password complexity rules
6. **Account Recovery**: Password reset flow with email verification
7. **Multi-factor Auth**: TOTP or WebAuthn support
8. **Audit Logging**: Track login attempts, token rotations, and security events

---

## File Creation Checklist

Complete list of files to create, organized by phase:

### Phase 0 — COMPLETE
- [x] `.env.example`
- [x] `.gitignore`

### Phase 1 — COMPLETE
- [x] `backend/app/__init__.py`
- [x] `backend/app/config.py`
- [x] `backend/app/database.py`
- [x] `backend/app/main.py`
- [x] `backend/app/models/__init__.py`
- [x] `backend/app/models/user.py`
- [x] `backend/alembic.ini`
- [x] `backend/alembic/env.py`
- [x] `backend/requirements.txt`

### Phase 2 — COMPLETE
- [x] `backend/app/schemas/__init__.py`
- [x] `backend/app/schemas/auth.py`
- [x] `backend/app/services/__init__.py`
- [x] `backend/app/services/auth.py`
- [x] `backend/app/api/__init__.py`
- [x] `backend/app/api/router.py`
- [x] `backend/app/api/auth.py`
- [x] `backend/app/dependencies.py`

### Phase 3 — COMPLETE
- [x] `backend/tests/__init__.py`
- [x] `backend/tests/conftest.py`
- [x] `backend/tests/test_auth_api.py`
- [x] `backend/tests/test_auth_service.py`
- [x] `backend/Dockerfile`
- [x] `backend/entrypoint.sh`

### Phase 4 — COMPLETE
- [x] `frontend/package.json`
- [x] `frontend/tsconfig.json`
- [x] `frontend/vite.config.ts`
- [x] `frontend/eslint.config.mjs`
- [x] `frontend/index.html`
- [x] `frontend/src/main.tsx`
- [x] `frontend/src/App.tsx`
- [x] `frontend/src/vite-env.d.ts`
- [x] `frontend/tests/setup.ts`

### Phase 5 — COMPLETE
- [x] `frontend/src/api/client.ts`
- [x] `frontend/src/contexts/AuthContext.tsx`
- [x] `frontend/src/components/LoginForm.tsx`
- [x] `frontend/src/components/RegisterForm.tsx`
- [x] `frontend/src/components/ProtectedRoute.tsx`
- [x] `frontend/src/pages/LoginPage.tsx`
- [x] `frontend/src/pages/RegisterPage.tsx`
- [x] `frontend/src/pages/DashboardPage.tsx`

### Phase 6 — COMPLETE
- [x] `frontend/tests/LoginForm.test.tsx`
- [x] `frontend/tests/RegisterForm.test.tsx`
- [x] `frontend/tests/AuthContext.test.tsx`
- [x] `frontend/Dockerfile`

### Phase 7
- [ ] `proxy/Caddyfile`
- [ ] `proxy/Dockerfile`

### Phase 8
- [ ] `docker-compose.yml`
- [ ] `docker-compose.local.yml`
- [ ] `docker-compose.staging.yml`
- [ ] `docker-compose.prod.yml`

### Phase 9
- [ ] `.github/workflows/backend.yml`
- [ ] `.github/workflows/frontend.yml`
- [ ] `.github/workflows/proxy.yml`

**Total Files:** 54 (38 created, 16 remaining)
