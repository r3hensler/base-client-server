# Railway Deployment Plan

**Last Updated:** February 11, 2026

---

## Architecture on Railway

```
Internet → Caddy Proxy (public, Railway domain)
              ├─ /api/*       → Backend (private, http://backend.railway.internal)
              ├─ /health      → Backend (private)
              ├─ /proxy/health → responds "OK" directly
              └─ /*           → Frontend (private, http://frontend.railway.internal)
                                  ↓
                           PostgreSQL (Railway managed, private)
```

Only the proxy service has a public domain. Backend and frontend communicate via Railway private networking (`http://`, not `https://`).

---

## Code Changes Made

### 1. `proxy/Caddyfile.railway` (new file)

Railway-specific Caddyfile that:
- Uses `:{$PORT:80}` for Railway's dynamic PORT injection
- Uses `{$BACKEND_URL}` and `{$FRONTEND_URL}` env vars for private networking
- Adds `/proxy/health` endpoint for Railway deployment validation
- Always applies HSTS (Railway uses real domains with TLS)

The original `proxy/Caddyfile` is unchanged for local/staging/prod Docker Compose.

### 2. `proxy/Dockerfile.railway` (new file)

Copies `Caddyfile.railway` instead of `Caddyfile`. Point Railway's proxy service to this Dockerfile.

### 3. `backend/entrypoint.sh`

Changed uvicorn port from hardcoded `8000` to `${PORT:-8000}`. Railway injects PORT at runtime.

### 4. `backend/Dockerfile`

Added HEALTHCHECK using PORT variable with 40s start period (allows time for Alembic migrations + connection pool init).

### 5. `frontend/Dockerfile`

- Changed inline Caddyfile in prod stage from `:5173` to `:{$PORT:5173}` for Railway compatibility
- Added HEALTHCHECK using wget

### 6. `backend/app/config.py`

Added `ensure_asyncpg_url` validator that auto-converts `postgresql://` to `postgresql+asyncpg://`. Railway provides the standard format; our app needs the asyncpg dialect prefix.

---

## Railway Dashboard Configuration

### Step 1: Add PostgreSQL

- Click "New" → "Database" → "PostgreSQL"
- Railway auto-provisions and provides `DATABASE_URL`, `PGHOST`, `PGPORT`, etc.

### Step 2: Add Backend Service

| Setting | Value |
|---------|-------|
| **Source** | GitHub repo |
| **Root directory** | `backend` |
| **Builder** | Dockerfile |
| **Dockerfile path** | `Dockerfile` |

**Environment variables:**

| Variable | Value |
|----------|-------|
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` |
| `JWT_SECRET_KEY` | Generate with: `python -c "import secrets; print(secrets.token_urlsafe(64))"` |
| `ENV` | `production` |
| `COOKIE_SECURE` | `true` |
| `COOKIE_SAMESITE` | `lax` |
| `FORWARDED_ALLOW_IPS` | `*` (backend is private — only proxy can reach it) |

**Settings:**
- Health check path: `/health`
- **No public domain** — private networking only

### Step 3: Add Frontend Service

| Setting | Value |
|---------|-------|
| **Source** | GitHub repo |
| **Root directory** | `frontend` |
| **Builder** | Dockerfile |
| **Dockerfile path** | `Dockerfile` |

**Settings:**
- **No public domain** — private networking only
- Railway will build the default (last) stage which is `prod`

### Step 4: Add Proxy Service

| Setting | Value |
|---------|-------|
| **Source** | GitHub repo |
| **Root directory** | `proxy` |
| **Builder** | Dockerfile |
| **Dockerfile path** | `Dockerfile.railway` |

**Environment variables:**

| Variable | Value |
|----------|-------|
| `BACKEND_URL` | `http://${{backend.RAILWAY_PRIVATE_DOMAIN}}:${{backend.PORT}}` |
| `FRONTEND_URL` | `http://${{frontend.RAILWAY_PRIVATE_DOMAIN}}:${{frontend.PORT}}` |

**Settings:**
- Health check path: `/proxy/health`
- **Public domain:** Generate Railway domain (or attach custom domain)

### Important Notes

1. **Private networking uses `http://`** — never `https://` for internal Railway communication
2. **Backend and frontend must NOT have public domains** — only proxy is public
3. **Migrations run automatically** on backend startup via `entrypoint.sh` (`alembic upgrade head`)
4. **PORT is injected by Railway** — services automatically get a PORT env var at runtime

---

## Verification

After deploying all services:

```bash
# Proxy health
curl https://<railway-domain>/proxy/health
# Expected: OK

# Backend health (via proxy)
curl https://<railway-domain>/health
# Expected: {"status":"ok"}

# Frontend (via proxy)
curl https://<railway-domain>/
# Expected: HTML page

# Auth flow
# 1. POST /api/v1/auth/register — create account
# 2. POST /api/v1/auth/login — get cookies
# 3. GET /api/v1/auth/me — verify authentication
# 4. POST /api/v1/auth/logout — clear cookies
```

---

## Estimated Monthly Cost

| Service | Memory | Cost |
|---------|--------|------|
| Caddy Proxy | ~50-100 MB | $3-5 |
| Frontend (Caddy) | ~20-50 MB | $3-5 |
| Backend (FastAPI) | ~150-250 MB | $5-10 |
| PostgreSQL | ~100-500 MB | $5-10 |
| **Total** | | **$16-30** |

---

## Files Changed

| File | Change |
|------|--------|
| `proxy/Caddyfile.railway` | **New** — Railway-specific Caddyfile with PORT + env var URLs |
| `proxy/Dockerfile.railway` | **New** — Dockerfile using Caddyfile.railway |
| `backend/entrypoint.sh` | Use `${PORT:-8000}` instead of hardcoded 8000 |
| `backend/Dockerfile` | Added HEALTHCHECK |
| `frontend/Dockerfile` | `:{$PORT:5173}` in prod Caddyfile + HEALTHCHECK |
| `backend/app/config.py` | Added `ensure_asyncpg_url` validator |

## Files NOT Changed (preserved for local/staging/prod Docker Compose)

| File | Reason |
|------|--------|
| `proxy/Caddyfile` | Local dev uses `{$SITE_ADDRESS:localhost}` for auto-TLS |
| `proxy/Dockerfile` | References original Caddyfile |
| `docker-compose*.yml` | All Docker Compose files work as before |
