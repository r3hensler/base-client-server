# Railway Deployment - Lessons Learned

**Platform:** Railway
**Last Updated:** February 11, 2026

---

## Executive Summary

This document captures lessons learned from deploying FastAPI + React + Caddy applications to Railway. It includes issues encountered, solutions implemented, and comparisons with Railway's official documentation and community best practices.

**Key Takeaways:**
1. Safari/WebKit CORS issues require a reverse proxy for cross-origin applications
2. Vite environment variables must be handled at Docker build-time, not runtime
3. Database migrations (Alembic) should auto-run on startup for simple deployments
4. Railway private networking uses specific patterns with reference variables
5. Structured logging to stdout is essential for Railway observability

---

## Table of Contents

1. [Safari CORS and Reverse Proxy](#1-safari-cors-and-reverse-proxy)
2. [Docker Multi-Stage Builds](#2-docker-multi-stage-builds)
3. [Vite Build-Time Environment Variables](#3-vite-build-time-environment-variables)
4. [Database Migrations with Alembic](#4-database-migrations-with-alembic)
5. [Railway Private Networking](#5-railway-private-networking)
6. [Logging and Observability](#6-logging-and-observability)
7. [Health Checks and Restart Policies](#7-health-checks-and-restart-policies)
8. [Port Configuration](#8-port-configuration)
9. [Cost and Resource Optimization](#9-cost-and-resource-optimization)
10. [CI/CD Integration](#10-cicd-integration)

---

## 1. Safari CORS and Reverse Proxy

### The Problem

When deploying frontend and backend as separate Railway services with different domains, Safari and iOS WebKit browsers blocked cross-origin API requests despite proper CORS headers.

**Root Cause:** Safari's Intelligent Tracking Prevention (ITP) applies stricter rules than Chrome/Firefox for cross-domain requests. Third-party cookies and certain cross-origin requests are blocked even with valid CORS configuration.

### Our Solution

Implemented a Caddy reverse proxy as the single public entry point, routing:
- `/api/*` → Backend (FastAPI)
- `/*` → Frontend (React SPA via Caddy)

This makes all requests same-origin, completely bypassing CORS issues.

### Railway Documentation Alignment

**Confirmed by Railway community:** Railway's [Help Station](https://help.railway.com/questions/simple-way-to-add-a-reverse-proxy-to-byp-7375f286) explicitly recommends Caddy reverse proxy for CORS issues:

> "Hosting a Caddy reverse proxy involves deploying a web server that routes incoming requests to different backend services based on URL patterns. This allows you to access your frontend from /* and your backend from /api/* on the same domain, eliminating CORS issues."

**Additional Safari-specific insight from [Railway community](https://station.railway.com/questions/private-networking-cors-a1e9bd97):**
> "The issue is that on browsers that block third party cookies, the authentication system breaks (ex: Safari mobile)."

### Key Caddyfile Configuration

```caddyfile
:{$PORT:80} {
    handle /api/* {
        reverse_proxy {$BACKEND_URL}
    }

    handle /proxy/health {
        respond "OK" 200
    }

    handle {
        reverse_proxy {$FRONTEND_URL}
    }
}
```

**Lesson:** Use `handle` (not `handle_path`) to preserve URL paths when proxying to backend services.

### Cost Impact

- Additional service cost: ~$3-5/month
- **Worth it:** Ensures Safari/iOS compatibility without complex CORS debugging

---

## 2. Docker Multi-Stage Builds

### The Pattern We Used

Frontend uses multi-stage Docker builds:
1. **Dev stage:** Node.js 22-slim with Vite HMR for local development
2. **Build stage:** Node.js 22-slim with full dependencies, Vite production build
3. **Prod stage:** Caddy 2-alpine serving static files

Backend uses a single stage with Python 3.12-slim.

### Railway Documentation Alignment

Per [Railway's deployment guide](https://docs.railway.com/guides/dockerfiles):
> "Choosing a minimal base image, such as alpine or slim, can significantly reduce the overall size of your Docker image."

### Key Lessons

1. **Use specific version tags** — Pin `python:3.12-slim`, `node:22-slim`, `caddy:2-alpine` for reproducible builds

2. **Run as non-root user** — Backend creates a dedicated `app` user:
   ```dockerfile
   RUN addgroup --system app && adduser --system --ingroup app app
   USER app
   ```

3. **Use `exec` in entrypoint scripts** — Ensures proper signal handling (SIGTERM):
   ```bash
   exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" "$@"
   ```

4. **Leverage .dockerignore** — Exclude `node_modules`, `__pycache__`, tests, and docs to reduce build context

---

## 3. Vite Build-Time Environment Variables

### The Problem

Environment variables defined in Railway's dashboard aren't available during Vite builds. The frontend bundle has undefined values.

**Root Cause:** Vite embeds environment variables at **build time**, not runtime. Railway's environment variables are available at runtime but not during Docker build unless explicitly passed.

### Solution

Use Docker `ARG` to pass variables at build time:

```dockerfile
ARG VITE_API_URL
ENV VITE_API_URL=${VITE_API_URL}
RUN npm run build
```

### Railway Documentation Alignment

Railway's [Help Station](https://station.railway.com/questions/environment-variables-in-vite-js-not-avai-a4085c8d) confirms:
> "Railway doesn't have the ability to offer variables at build time, unless you are sourcing them via ARG in a Dockerfile."

### Key Lessons

1. **ARG vs ENV:** ARGs are only available during build; ENVs persist at runtime. For Vite, you need ARG.

2. **With reverse proxy, VITE_API_URL can be empty** — Since all requests are same-origin via proxy, the frontend can use relative URLs (`/api` instead of `https://api.example.com/api`).

3. **Railway provides useful build-time variables:**
   - `RAILWAY_GIT_COMMIT_SHA` — Full commit hash
   - `RAILWAY_GIT_BRANCH` — Current branch name

---

## 4. Database Migrations with Alembic

### Our Solution

Automatic migrations via a startup script (`entrypoint.sh`):

```bash
#!/bin/bash
set -e

echo "Running database migrations..."
alembic upgrade head

echo "Starting server..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" "$@"
```

### Key Lessons

1. **Auto-run migrations on startup:**
   - Simplifies deployment workflow (no manual migration step)
   - Ensures database schema is always up-to-date
   - Use `set -e` to fail fast if migrations fail
   - Use `exec` to replace shell process with application (proper signal handling)

2. **Alembic works well with Railway:**
   - No special configuration needed beyond standard Alembic setup
   - Database URL via environment variable (`DATABASE_URL`)
   - Migrations run successfully as non-root user

3. **Migration safety:**
   - Always test migrations locally before deploying
   - Use `alembic upgrade head --sql` to review SQL before running
   - Railway's automatic backups provide safety net

4. **Railway's `DATABASE_URL` uses `postgresql://`** — Our app needs `postgresql+asyncpg://`. The `ensure_asyncpg_url` validator in `config.py` auto-converts this.

### Alternative Approaches Considered

**Option 1: Run migrations in Railway build phase**
- Doesn't work because DATABASE_URL not available during build
- Private networking only available at runtime

**Option 2: Separate migration service**
- Adds complexity and cost
- Harder to coordinate with main service deployment
- Not needed for single-instance deployments

**Option 3: Manual migrations via Railway CLI**
- Error-prone (easy to forget)
- Breaks automated deployment workflow

### Railway Documentation Alignment

From [Railway's deployment best practices](https://docs.railway.com/guides/dockerfiles):
> "You can run database migrations as part of your application startup process."

---

## 5. Railway Private Networking

### How We Use It

Our proxy communicates with frontend and backend over Railway's private network:

```bash
BACKEND_URL=http://${{backend.RAILWAY_PRIVATE_DOMAIN}}:${{backend.PORT}}
FRONTEND_URL=http://${{frontend.RAILWAY_PRIVATE_DOMAIN}}:${{frontend.PORT}}
```

### Railway Documentation Alignment

From [Railway Private Networking docs](https://docs.railway.com/guides/private-networking):
> "By default, all projects have private networking enabled and services will get a new DNS name under the railway.internal domain."

Critical requirement:
> "Super important: use http:// and NOT https:// or the internal network will not work."

### Key Lessons

1. **Always use `http://` for private networking** — HTTPS doesn't work on internal network

2. **PORT configuration matters:**
   - Railway injects a PORT at runtime
   - For reference variables to work, you need to pin the PORT as a service variable

3. **Private network scope:**
   - Scoped to single environment within a project
   - Services in different projects/environments cannot communicate privately
   - **Not available during build phase** — Only at runtime

4. **Client-side code cannot use private networking:**
   > "A web application that makes client-side requests cannot communicate to another service over the private network."

   This is why we use a proxy (server-side) instead of having the browser call the backend directly.

5. **Benefits of keeping services in same project:**
   - Private networking is free (no egress fees)
   - Faster than public networking
   - More secure (not exposed to internet)

---

## 6. Logging and Observability

### Railway Documentation Alignment

From [Railway Logging docs](https://docs.railway.com/reference/logging):
> "The entire JSON log must be emitted on a single line to be parsed correctly by Railway."

> "Railway recommends using structured logging with minimal formatting (e.g., minified JSON instead of pretty-printed objects)."

### Key Lessons

1. **Log to stdout** — Railway captures stdout automatically. Don't write to files.

2. **Use structured JSON logging** — For Python, use `python-json-logger` or similar. Caddy already outputs JSON when configured with `format json`.

3. **Essential fields for structured logs:**
   - `timestamp` (ISO 8601 in UTC)
   - `level` (ERROR, WARN, INFO, DEBUG)
   - `requestId` or `correlationId`
   - `userId` (when authenticated)

4. **Log levels strategy:**
   - `error`: Unexpected errors, database errors
   - `warn`: Expected errors (NOT_FOUND, validation), rate limits
   - `info`: Significant events (logins, registrations)
   - `debug`: Detailed debugging (development only)

---

## 7. Health Checks and Restart Policies

### Our Configuration

Each service has a Dockerfile HEALTHCHECK:

**Backend (FastAPI):**
```dockerfile
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD python -c "import urllib.request,os; urllib.request.urlopen('http://localhost:'+os.environ.get('PORT','8000')+'/health')"
```

**Frontend (Caddy):**
```dockerfile
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD wget --quiet --tries=1 --spider http://localhost:5173/ || exit 1
```

### Railway Documentation Alignment

From [Railway Healthchecks docs](https://docs.railway.com/guides/healthchecks-and-restarts):
> "The default timeout on healthchecks is 300 seconds (5 minutes). If your application fails to serve a 200 status code during this allotted time, the deploy will be marked as failed."

Important distinction:
> "The healthcheck endpoint is currently not used for continuous monitoring as it is only called at the start of the deployment."

### Key Lessons

1. **Dockerfile HEALTHCHECK vs Railway healthcheck:**
   - Dockerfile HEALTHCHECK: Container-level, Docker runtime uses it
   - Railway healthcheck path: Deployment validation only (not continuous monitoring)

2. **Health check must use PORT variable:**
   > "If your application doesn't listen on the PORT variable... your health check [may return] a service unavailable error."

3. **Memory limits cause silent kills:**
   > "If memory spikes to your plan limit, Railway kills the container silently (no error logs)."

4. **Start period is important:**
   Use `--start-period` to give your app time to initialize (especially with Alembic migrations on startup). Our backend uses 40s to allow for migration + connection pool init.

---

## 8. Port Configuration

### Our Solution

```bash
# Backend entrypoint.sh
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
```

```caddyfile
# Proxy Caddyfile
:{$PORT:80} {
    ...
}
```

```caddyfile
# Frontend inline Caddyfile (in Dockerfile)
:{$PORT:5173} {
    ...
}
```

### Key Lessons

1. **Railway injects PORT at runtime** — Always use `${PORT:-default}` syntax

2. **Always bind to 0.0.0.0** — Binding to `localhost` or `127.0.0.1` won't work

3. **EXPOSE in Dockerfile is informational** — It documents the port but doesn't publish it. Railway uses the PORT env var.

4. **Caddyfile PORT variable** — Use `:{$PORT:80}` syntax (Caddy's env var syntax) for Railway compatibility

5. **Private vs Public domain ports:**
   - Private domain: Uses the PORT env var Railway sets
   - Public domain: Always 443 (HTTPS) externally, routed to your PORT internally

---

## 9. Cost and Resource Optimization

### Estimated Costs

| Service | Memory | Estimated Monthly |
|---------|--------|-------------------|
| Caddy Proxy | ~50-100 MB | $3-5 |
| Frontend (Caddy) | ~20-50 MB | $3-5 |
| Backend (FastAPI) | ~150-250 MB | $5-10 |
| PostgreSQL | ~100-500 MB | $5-10 |
| **Total** | | **$16-30** |

### Railway Documentation Alignment

From [Railway Best Practices](https://docs.railway.com/overview/best-practices):
> "The private network is scoped to a single environment within a project, having all related services within a single project will allow you to use private networking for faster networking along with no egress fees for service-to-service communication."

### Optimization Lessons

1. **Slim/Alpine images reduce costs** — Smaller images = faster deploys = less compute during builds

2. **Private networking saves money** — No egress fees for proxy-to-service communication

3. **Connection pooling for database:**
   From [Railway's database guide](https://blog.railway.com/p/database-connection-pooling):
   > "Connection pooling is an effective strategy for optimizing server-to-database communication."

   Our SQLAlchemy pool defaults: `pool_size=20`, `max_overflow=10` (30 max per instance). If scaling to multiple instances, reduce per-instance pool size to stay within Railway PostgreSQL connection limits (typically 20-50).

4. **Consider Railway's free tier** — $5/month credit can run small apps for free during development.

---

## 10. CI/CD Integration

### Railway Auto-Deploy Flow

1. Push to `main` branch
2. GitHub Actions validates Docker builds, linting, and tests
3. Railway detects push and starts build
4. Railway builds Docker images
5. Railway runs health checks
6. Railway routes traffic (zero-downtime)

### Key Lessons

1. **Validate before Railway builds** — Catch Dockerfile errors before Railway deployment (saves time and deploy slots)

2. **Railway doesn't need you to push images** — Railway builds from your Dockerfile directly. No need for Docker registry.

3. **Branch-based environments** — Railway can create preview environments for PRs automatically

4. **Watch paths for selective rebuilds** — Configure which file changes trigger rebuilds for each service

---

## Summary: Top 10 Lessons

1. **Use a reverse proxy for Safari/iOS compatibility** — Caddy is simple and effective
2. **Vite env vars need Docker ARG** — Runtime ENV doesn't work for build-time embedding
3. **Auto-run Alembic migrations on startup** — Simplifies deployment workflow
4. **Use `exec` in startup scripts** — Proper signal handling for graceful shutdown
5. **Use `http://` for private networking** — HTTPS breaks internal communication
6. **Bind to 0.0.0.0** — Required for Railway to reach your container
7. **Log to stdout as JSON** — Railway parses structured logs automatically
8. **Use `:{$PORT:default}` in Caddyfiles** — Railway compatibility with local fallback
9. **Private networking is free** — Keep related services in same project
10. **Non-root users for security** — Run as non-root in all containers

---

## References

### Railway Documentation
- [Private Networking](https://docs.railway.com/guides/private-networking)
- [Dockerfiles Guide](https://docs.railway.com/guides/dockerfiles)
- [Healthchecks and Restarts](https://docs.railway.com/guides/healthchecks-and-restarts)
- [Logging](https://docs.railway.com/reference/logging)
- [Best Practices](https://docs.railway.com/overview/best-practices)

### Railway Community (Help Station)
- [Reverse Proxy for CORS](https://help.railway.com/questions/simple-way-to-add-a-reverse-proxy-to-byp-7375f286)
- [Vite Environment Variables](https://station.railway.com/questions/environment-variables-in-vite-js-not-avai-a4085c8d)

### External Resources
- [Docker Multi-Stage Builds](https://docs.docker.com/build/building/multi-stage/)
- [Railway Database Connection Pooling](https://blog.railway.com/p/database-connection-pooling)
