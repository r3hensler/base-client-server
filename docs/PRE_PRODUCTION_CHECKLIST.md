# Pre-Production Checklist

**Before deploying to production, complete all items in this checklist.**

Last Updated: 2026-02-11

---

## 🔴 CRITICAL - Must Complete Before Launch

### Security Configuration

- [ ] **Generate Strong JWT Secret**
  ```bash
  python -c "import secrets; print(secrets.token_urlsafe(64))"
  ```
  - Set `JWT_SECRET_KEY` in production `.env`
  - ✅ Must be at least 32 characters (validation enforced)
  - ⚠️ Never commit this value to version control
  - 📝 Store securely (e.g., AWS Secrets Manager, 1Password)

- [ ] **Generate Strong Database Password**
  ```bash
  openssl rand -base64 32
  ```
  - Set `POSTGRES_PASSWORD` in production `.env`
  - Update `DATABASE_URL` connection string with new password
  - ⚠️ Never use default `postgres/postgres` in production

- [ ] **Configure Cookie Security**
  - Set `COOKIE_SECURE=true` in production `.env`
  - Set `ENV=production` in production `.env`
  - Verify HTTPS is configured (Caddy proxy handles this)
  - ⚠️ Application will refuse to start if `COOKIE_SECURE=false` in production

### Database Setup

- [ ] **Create Production Database**
  ```bash
  # On database server:
  createdb app
  createuser app_user
  psql -c "GRANT ALL PRIVILEGES ON DATABASE app TO app_user;"
  ```

- [ ] **Run Database Migrations**
  ```bash
  cd backend
  alembic upgrade head
  ```
  - ✅ Verify migration completes successfully
  - 📝 Check `alembic_version` table shows correct revision

- [ ] **Verify Database Connection Pool**
  - Confirm `DB_POOL_SIZE=20` (default is good for most cases)
  - Confirm `DB_POOL_MAX_OVERFLOW=10` (allows bursts up to 30 connections)
  - Adjust based on expected concurrent users:
    - Small (< 100 users): pool_size=10, max_overflow=5
    - Medium (100-1000 users): pool_size=20, max_overflow=10 (default)
    - Large (1000+ users): pool_size=50, max_overflow=20

### Environment Validation

- [ ] **Review All Environment Variables**
  ```bash
  # Copy and customize for production:
  cp .env.example .env.production
  ```

  Required settings:
  - `ENV=production`
  - `JWT_SECRET_KEY=<64-char-random-string>`
  - `DATABASE_URL=<production-db-url>`
  - `POSTGRES_PASSWORD=<strong-password>`
  - `COOKIE_SECURE=true`
  - `COOKIE_SAMESITE=lax`
  - `SITE_ADDRESS=<your-domain.com>`

- [ ] **Test Configuration Startup**
  ```bash
  cd backend
  python -c "from app.config import settings; print('✅ Config valid')"
  ```
  - ✅ Should print "Config valid" without errors
  - ⚠️ Will fail if JWT_SECRET_KEY is weak or missing

---

## 🟠 HIGH PRIORITY - Complete Within First Week

### Monitoring & Observability

- [ ] **Set Up Application Monitoring**
  - [ ] Error tracking (e.g., Sentry, Rollbar)
  - [ ] Performance monitoring (response times, throughput)
  - [ ] Database connection pool metrics
    - Monitor `pool_size` usage
    - Alert if overflow is consistently hit
    - Alert on connection timeout errors

- [ ] **Set Up Health Checks**
  - [ ] Verify `/health` endpoint returns 200
  - [ ] Set up uptime monitoring (e.g., UptimeRobot, Pingdom)
  - [ ] Configure alerts for downtime

- [ ] **Set Up Logging**
  - [ ] Centralized log aggregation (e.g., CloudWatch, Datadog)
  - [ ] Log authentication events:
    - Failed login attempts
    - Successful logins
    - Token refresh failures
    - Account registrations
  - [ ] Set up alerts for suspicious patterns:
    - High rate of failed logins from single IP
    - Unusual geographic login patterns
    - Multiple refresh token failures

### Security Hardening

- [ ] **Implement Rate Limiting** ⚠️ HIGH PRIORITY
  ```python
  # Add to requirements.txt:
  # slowapi>=0.1.9

  # In app/main.py:
  from slowapi import Limiter
  from slowapi.util import get_remote_address

  limiter = Limiter(key_func=get_remote_address)
  app.state.limiter = limiter

  # In app/api/auth.py:
  @router.post("/login")
  @limiter.limit("5/minute")  # 5 attempts per minute
  async def login(...):
      ...
  ```
  - [ ] Login endpoint: 5 attempts/minute per IP
  - [ ] Registration endpoint: 3 registrations/hour per IP
  - [ ] Refresh endpoint: 10 refreshes/minute per IP

- [ ] **Implement Account Lockout**
  - [ ] Add columns to `users` table:
    ```sql
    ALTER TABLE users ADD COLUMN failed_login_attempts INTEGER DEFAULT 0;
    ALTER TABLE users ADD COLUMN locked_until TIMESTAMP WITH TIME ZONE;
    ```
  - [ ] Lock account after 5 failed login attempts
  - [ ] Auto-unlock after 15 minutes
  - [ ] Email notification on account lockout

- [ ] **Review Security Headers**
  - [ ] Verify `SecurityHeadersMiddleware` is active
  - [ ] Test with https://securityheaders.com
  - [ ] Expected headers:
    - `X-Content-Type-Options: nosniff`
    - `X-Frame-Options: DENY`
    - `X-XSS-Protection: 1; mode=block`
    - `Referrer-Policy: strict-origin-when-cross-origin`
    - `Strict-Transport-Security: max-age=31536000` (HTTPS only)

### Performance Validation

- [ ] **Load Testing**
  ```bash
  # Example with wrk or locust:
  wrk -t4 -c100 -d30s https://your-domain.com/health
  ```
  - [ ] Test login endpoint under load (simulate 50-100 concurrent logins)
  - [ ] Test refresh token endpoint under load
  - [ ] Verify database connection pool handles expected traffic
  - [ ] Monitor response times (target: < 200ms for auth endpoints)

- [ ] **Database Query Analysis**
  ```sql
  -- Enable query logging temporarily
  SET log_statement = 'all';
  ```
  - [ ] Verify all queries use indexes (no sequential scans on large tables)
  - [ ] Check slow query log for queries > 100ms
  - [ ] Verify partial index on `refresh_tokens` is being used

---

## 🟡 MEDIUM PRIORITY - Complete Within First Month

### Operational Excellence

- [ ] **Backup Strategy**
  - [ ] Set up automated database backups (daily at minimum)
  - [ ] Test restore procedure
  - [ ] Document recovery time objective (RTO) and recovery point objective (RPO)
  - [ ] Store backups in separate region/availability zone

- [ ] **Database Maintenance**
  - [ ] Set up automated cleanup job for expired refresh tokens
    ```python
    # backend/app/tasks/cleanup.py
    async def cleanup_expired_tokens():
        cutoff = datetime.now(UTC) - timedelta(days=30)
        await db.execute(
            delete(RefreshToken).where(
                RefreshToken.expires_at < cutoff
            )
        )
    ```
  - [ ] Schedule to run daily (e.g., via cron or Celery)
  - [ ] Monitor database size growth

- [ ] **Incident Response Plan**
  - [ ] Document who to contact for security incidents
  - [ ] Create runbook for common issues:
    - Database connection pool exhausted
    - High rate of authentication failures
    - Suspected account compromise
  - [ ] Test rollback procedure

### Feature Enhancements

- [ ] **Email Verification** (Optional but recommended)
  - [ ] Add `email_verified` boolean to users table
  - [ ] Generate verification token on registration
  - [ ] Send verification email
  - [ ] Require verification before login

- [ ] **Password Reset Flow** (Optional but recommended)
  - [ ] Add password reset token table
  - [ ] Implement "Forgot Password" endpoint
  - [ ] Send password reset email
  - [ ] Implement reset confirmation endpoint

- [ ] **Security Event Logging**
  ```python
  import logging

  security_logger = logging.getLogger('security')

  # Log important events:
  security_logger.info(f"Login success: {user.email} from {request.client.host}")
  security_logger.warning(f"Failed login: {email} from {request.client.host}")
  security_logger.error(f"Token theft suspected: {user.email}")
  ```

### Documentation

- [ ] **API Documentation**
  - [ ] Review auto-generated Swagger docs at `/docs`
  - [ ] Add descriptions to all endpoints
  - [ ] Document authentication flow
  - [ ] Add example requests/responses

- [ ] **Operational Runbooks**
  - [ ] How to add a new environment variable
  - [ ] How to create a database migration
  - [ ] How to manually revoke a user's refresh tokens
  - [ ] How to scale the application

---

## 🟢 NICE TO HAVE - Future Enhancements

### Advanced Security

- [ ] **CSRF Protection Enhancement**
  - Current: `SameSite=lax` provides basic protection
  - Enhancement: Add double-submit cookie pattern for additional security

- [ ] **Emergency Token Revocation**
  - Add `jti` (JWT ID) to access tokens
  - Create `revoked_tokens` table for emergency revocation
  - Check on every token validation (adds ~10ms latency)

- [ ] **Two-Factor Authentication (2FA)**
  - TOTP-based (Google Authenticator, Authy)
  - Or SMS-based
  - Requires additional tables and endpoints

- [ ] **Session Management Dashboard**
  - Show users their active sessions (devices, locations)
  - Allow users to revoke individual sessions
  - Show last login time/location

### Performance Optimization

- [ ] **Caching Layer**
  - Add Redis for user session cache
  - Cache user lookups to reduce database queries
  - Set TTL to access token expiry time

- [ ] **Read Replicas**
  - If read-heavy, set up PostgreSQL read replicas
  - Route read queries to replicas
  - Route writes to primary

### Compliance

- [ ] **GDPR Compliance** (if operating in EU)
  - [ ] Add user data export endpoint
  - [ ] Add user account deletion endpoint
  - [ ] Update privacy policy
  - [ ] Implement data retention policies

- [ ] **SOC 2 / HIPAA** (if required)
  - [ ] Implement comprehensive audit logging
  - [ ] Set up log retention (7+ years)
  - [ ] Implement data encryption at rest
  - [ ] Document security controls

---

## ✅ Validation Checklist

Run these tests before declaring production-ready:

### Functional Tests

- [ ] **Registration Flow**
  - [ ] Can create new account with valid password
  - [ ] Cannot create account with weak password
  - [ ] Cannot create duplicate account (same email)
  - [ ] Password is properly hashed in database

- [ ] **Login Flow**
  - [ ] Can login with correct credentials
  - [ ] Cannot login with incorrect password
  - [ ] Cannot login with non-existent email
  - [ ] Cookies are set with proper flags (HttpOnly, Secure)

- [ ] **Token Refresh Flow**
  - [ ] Can refresh access token with valid refresh token
  - [ ] Old refresh token is revoked after rotation
  - [ ] Cannot use revoked refresh token
  - [ ] Cannot use expired refresh token

- [ ] **Logout Flow**
  - [ ] Logout clears cookies
  - [ ] Cannot access protected endpoints after logout
  - [ ] Refresh token is revoked in database

- [ ] **Protected Endpoints**
  - [ ] `/api/v1/auth/me` requires authentication
  - [ ] Returns 401 without valid access token
  - [ ] Returns user data with valid token

### Security Tests

- [ ] **Password Validation**
  - [ ] Requires minimum 8 characters
  - [ ] Requires uppercase letter
  - [ ] Requires lowercase letter
  - [ ] Requires digit
  - [ ] Requires special character

- [ ] **JWT Token Validation**
  - [ ] Tokens include `iss`, `aud`, `iat` claims
  - [ ] Tokens are validated on decode
  - [ ] Invalid tokens return 401
  - [ ] Expired tokens return 401

- [ ] **Timing Attack Protection**
  - [ ] Login takes same time for valid/invalid users
  - [ ] Test with timing analysis tool

- [ ] **Cookie Security**
  - [ ] `HttpOnly` flag is set (prevents XSS)
  - [ ] `Secure` flag is set in production (HTTPS only)
  - [ ] `SameSite=lax` is set (prevents CSRF)
  - [ ] Refresh token scoped to `/api/v1/auth` path

### Performance Tests

- [ ] **Database Connection Pool**
  - [ ] Pool size is appropriate for expected load
  - [ ] No connection timeout errors under normal load
  - [ ] Connections are properly released

- [ ] **Response Times**
  - [ ] Login: < 500ms (bcrypt is intentionally slow)
  - [ ] Refresh: < 100ms
  - [ ] Protected endpoints: < 50ms
  - [ ] Health check: < 10ms

- [ ] **Database Indexes**
  - [ ] `EXPLAIN ANALYZE` shows index usage on auth queries
  - [ ] No sequential scans on large tables
  - [ ] Partial index on `refresh_tokens` is used

---

## 📊 Production Readiness Score

Calculate your readiness score:

- **Critical Items (Must Complete)**: _____ / 10 (0 acceptable failures)
- **High Priority Items**: _____ / 15 (aim for 80%+ completion)
- **Medium Priority Items**: _____ / 10 (aim for 60%+ completion)
- **Nice to Have Items**: _____ / 10 (optional, enhance over time)

**Target Score for Launch:**
- ✅ Critical: 10/10 (100%)
- ✅ High Priority: 12/15 (80%)
- 🎯 Medium Priority: 6/10 (60%)

---

## 🚨 Roll Back Plan

If critical issues are discovered after deployment:

1. **Immediate Actions**
   - [ ] Stop accepting new user registrations (feature flag)
   - [ ] Revert to previous deployment
   - [ ] Announce incident to users (if customer-facing)

2. **Investigation**
   - [ ] Check logs for error patterns
   - [ ] Review monitoring dashboards
   - [ ] Query database for data integrity

3. **Communication**
   - [ ] Notify stakeholders of issue and ETA for fix
   - [ ] Post status updates every 30 minutes
   - [ ] Conduct post-mortem after resolution

---

## 📝 Sign-Off

**Deployment Approval:** This application has been reviewed and approved for production deployment.

- [ ] **Technical Lead:** _________________ Date: _______
- [ ] **Security Review:** _________________ Date: _______
- [ ] **DevOps Review:** _________________ Date: _______

**Notes:**
```
(Add any deployment-specific notes, exceptions, or conditions)
```

---

## 📚 Reference Links

- **Implementation Plan:** [docs/IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md)
- **FastAPI Deployment Guide:** https://fastapi.tiangolo.com/deployment/
- **PostgreSQL Performance Tuning:** https://wiki.postgresql.org/wiki/Performance_Optimization
- **OWASP Authentication Cheat Sheet:** https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html
- **Security Headers Guide:** https://securityheaders.com/

---

**Last Review Date:** _____________
**Next Review Date:** _____________ (recommended: monthly for first 6 months)
