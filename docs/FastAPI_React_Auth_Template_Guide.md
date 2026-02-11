# FastAPI + React Auth Template Guide

A practical guide for setting up JWT-based authentication with HttpOnly cookies in a FastAPI + React + PostgreSQL stack, fronted by a Caddy reverse proxy for Safari/iOS compatibility.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Project Structure](#project-structure)
3. [Backend](#backend)
4. [Frontend](#frontend)
5. [Caddy Reverse Proxy](#caddy-reverse-proxy)
6. [Docker & Docker Compose](#docker--docker-compose)
7. [GitHub Actions CI](#github-actions-ci)
8. [Environment Variables Reference](#environment-variables-reference)
9. [Security Notes](#security-notes)

---

## Architecture Overview

```
                        ┌─────────────┐
                        │   Client    │
                        │  (Browser)  │
                        └──────┬──────┘
                               │ HTTPS
                        ┌──────▼──────┐
                        │    Caddy    │
                        │   :443/:80  │
                        └──┬───────┬──┘
                  /api/* │         │ /*
               ┌─────────▼──┐  ┌──▼─────────┐
               │   FastAPI   │  │   React    │
               │   :8000     │  │   :5173    │
               └──────┬──────┘  └────────────┘
                      │
               ┌──────▼──────┐
               │ PostgreSQL  │
               │   :5432     │
               └─────────────┘
```

**Auth flow (HttpOnly cookies):**

1. Client POSTs credentials to `/api/v1/auth/login`
2. Backend validates, returns `Set-Cookie` headers with `access_token` (15 min) and `refresh_token` (7 days)
3. Browser automatically attaches cookies on subsequent requests (same origin via Caddy)
4. On 401, frontend calls `/api/v1/auth/refresh` — backend rotates the refresh token and sets new cookies
5. On logout, backend revokes refresh token and clears cookies

**Why Caddy matters for Safari/iOS:**
Safari aggressively blocks third-party cookies and enforces strict `SameSite` rules. By routing both frontend and API through Caddy on the same origin, all cookies are first-party. Caddy also handles automatic HTTPS (including local dev with self-signed certs), which is required for `Secure` cookies.

---

## Project Structure

```
project-root/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   └── user.py
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   └── auth.py
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── router.py
│   │   │   └── auth.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   └── auth.py
│   │   └── dependencies.py
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/
│   ├── alembic.ini
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── conftest.py
│   │   ├── test_auth_api.py
│   │   └── test_auth_service.py
│   ├── Dockerfile
│   ├── requirements.txt
│   └── entrypoint.sh
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   │   └── client.ts
│   │   ├── contexts/
│   │   │   └── AuthContext.tsx
│   │   ├── components/
│   │   │   ├── LoginForm.tsx
│   │   │   ├── RegisterForm.tsx
│   │   │   └── ProtectedRoute.tsx
│   │   ├── pages/
│   │   │   ├── LoginPage.tsx
│   │   │   ├── RegisterPage.tsx
│   │   │   └── DashboardPage.tsx
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   └── vite-env.d.ts
│   ├── tests/
│   │   ├── setup.ts
│   │   ├── LoginForm.test.tsx
│   │   ├── RegisterForm.test.tsx
│   │   └── AuthContext.test.tsx
│   ├── index.html
│   ├── Dockerfile
│   ├── eslint.config.mjs
│   ├── vite.config.ts
│   ├── tsconfig.json
│   └── package.json
├── proxy/
│   ├── Caddyfile
│   └── Dockerfile
├── docker-compose.yml
├── docker-compose.local.yml
├── docker-compose.staging.yml
├── docker-compose.prod.yml
├── .env.example
└── .github/
    └── workflows/
        ├── backend.yml
        ├── frontend.yml
        └── proxy.yml
```

---

## Backend

### Dependencies

**`backend/requirements.txt`**

```
# Framework
fastapi>=0.115.0
uvicorn[standard]>=0.34.0

# Database
sqlalchemy[asyncio]>=2.0.36
asyncpg>=0.30.0
alembic>=1.14.0

# Auth
PyJWT>=2.10.0
passlib[bcrypt]>=1.7.4
bcrypt>=4.2.0

# Config
pydantic-settings>=2.7.0

# Testing
pytest>=8.3.0
pytest-asyncio>=0.25.0
httpx>=0.28.0
```

### Configuration

**`backend/app/config.py`**

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@db:5432/app"

    # JWT
    jwt_secret_key: str  # No default — must be set
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # Cookies
    cookie_secure: bool = True  # Requires HTTPS (Caddy provides this)
    cookie_samesite: str = "lax"
    cookie_domain: str | None = None  # None = current domain only

    model_config = {"env_file": ".env"}


settings = Settings()
```

### Database Setup

**`backend/app/database.py`**

```python
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with async_session() as session:
        yield session
```

### Models

**`backend/app/models/user.py`**

```python
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="refresh_tokens")
```

**`backend/app/models/__init__.py`**

```python
from app.models.user import RefreshToken, User

__all__ = ["User", "RefreshToken"]
```

### Schemas

**`backend/app/schemas/auth.py`**

```python
import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str  # Minimum length validated in service


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    message: str
```

### Auth Service

**`backend/app/services/auth.py`**

```python
import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.user import RefreshToken, User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(user_id: uuid.UUID) -> str:
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes),
        "type": "access",
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    """Decode and validate an access token. Raises jwt.PyJWTError on failure."""
    payload = jwt.decode(
        token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
    )
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("Not an access token")
    return payload


def generate_refresh_token() -> tuple[str, str]:
    """Returns (raw_token, sha256_hash)."""
    raw = secrets.token_urlsafe(48)
    hashed = hashlib.sha256(raw.encode()).hexdigest()
    return raw, hashed


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def create_user(db: AsyncSession, email: str, password: str) -> User:
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters")
    user = User(email=email, hashed_password=hash_password(password))
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def create_refresh_token_record(db: AsyncSession, user_id: uuid.UUID) -> str:
    """Create a refresh token in the DB. Returns the raw token (for the cookie)."""
    raw_token, token_hash = generate_refresh_token()
    record = RefreshToken(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days),
    )
    db.add(record)
    await db.commit()
    return raw_token


async def rotate_refresh_token(db: AsyncSession, raw_token: str) -> tuple[User, str]:
    """Validate, revoke, and reissue a refresh token. Returns (user, new_raw_token).

    Raises ValueError if the token is invalid, expired, or already revoked.
    """
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked_at.is_(None),
        )
    )
    record = result.scalar_one_or_none()

    if record is None:
        raise ValueError("Invalid refresh token")
    if record.expires_at < datetime.now(UTC):
        raise ValueError("Refresh token expired")

    # Revoke the old token
    record.revoked_at = datetime.now(UTC)

    # Load user
    user_result = await db.execute(select(User).where(User.id == record.user_id))
    user = user_result.scalar_one()

    # Issue new token
    new_raw_token = await create_refresh_token_record(db, user.id)
    await db.commit()
    return user, new_raw_token


async def revoke_refresh_token(db: AsyncSession, raw_token: str) -> None:
    """Revoke a refresh token (logout)."""
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked_at.is_(None),
        )
    )
    record = result.scalar_one_or_none()
    if record:
        record.revoked_at = datetime.now(UTC)
        await db.commit()
```

### Auth Dependencies

**`backend/app/dependencies.py`**

```python
import uuid

import jwt
from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.services.auth import decode_access_token

from sqlalchemy import select


async def get_current_user(
    access_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
) -> User:
    if access_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )
    try:
        payload = decode_access_token(access_token)
        user_id = uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
        )
    return user
```

### API Endpoints

**`backend/app/api/auth.py`**

```python
from fastapi import APIRouter, Depends, HTTPException, Response, Cookie, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    UserResponse,
)
from app.services.auth import (
    create_refresh_token_record,
    create_access_token,
    create_user,
    get_user_by_email,
    revoke_refresh_token,
    rotate_refresh_token,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    """Set HttpOnly cookies for both tokens."""
    common = {
        "httponly": True,
        "secure": settings.cookie_secure,
        "samesite": settings.cookie_samesite,
        "domain": settings.cookie_domain,
    }
    response.set_cookie(
        key="access_token",
        value=access_token,
        max_age=settings.access_token_expire_minutes * 60,
        path="/",
        **common,
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        max_age=settings.refresh_token_expire_days * 86400,
        path="/api/v1/auth",  # Only sent to auth endpoints
        **common,
    )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/api/v1/auth")


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    existing = await get_user_by_email(db, body.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email already registered"
        )
    try:
        user = await create_user(db, body.email, body.password)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    return user


@router.post("/login", response_model=UserResponse)
async def login(
    body: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    user = await get_user_by_email(db, body.email)
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Account is deactivated"
        )

    access_token = create_access_token(user.id)
    refresh_token = await create_refresh_token_record(db, user.id)
    _set_auth_cookies(response, access_token, refresh_token)
    return user


@router.post("/refresh", response_model=UserResponse)
async def refresh(
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    if refresh_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="No refresh token"
        )
    try:
        user, new_refresh_token = await rotate_refresh_token(db, refresh_token)
    except ValueError:
        _clear_auth_cookies(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        )

    new_access_token = create_access_token(user.id)
    _set_auth_cookies(response, new_access_token, new_refresh_token)
    return user


@router.post("/logout", response_model=MessageResponse)
async def logout(
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    if refresh_token:
        await revoke_refresh_token(db, refresh_token)
    _clear_auth_cookies(response)
    return {"message": "Logged out"}


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)):
    return current_user
```

**`backend/app/api/router.py`**

```python
from fastapi import APIRouter

from app.api.auth import router as auth_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router)
```

### Application Entry Point

**`backend/app/main.py`**

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.router import api_router
from app.database import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(title="App", lifespan=lifespan)
app.include_router(api_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
```

### Alembic Setup

**`backend/alembic.ini`** (key lines — adjust generated file):

```ini
[alembic]
script_location = alembic

# Leave sqlalchemy.url empty — env.py reads from config
sqlalchemy.url =
```

**`backend/alembic/env.py`**

```python
import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import settings
from app.database import Base
from app.models import User, RefreshToken  # noqa: F401 — ensure models are registered

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline():
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online():
    connectable = create_async_engine(settings.database_url)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
```

**`backend/entrypoint.sh`**

```bash
#!/bin/bash
set -e

echo "Running database migrations..."
alembic upgrade head

echo "Starting server..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 "$@"
```

Generate the initial migration after setting up:

```bash
alembic revision --autogenerate -m "create users and refresh_tokens"
```

### Backend Tests

**`backend/tests/conftest.py`**

```python
import asyncio
import uuid
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.database import Base, get_db
from app.main import app

# Use a separate test database
TEST_DB_URL = settings.database_url.replace("/app", "/app_test")

engine = create_async_engine(TEST_DB_URL, echo=False)
TestSession = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with TestSession() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# ── Helpers ──────────────────────────────────────────────────

TEST_EMAIL = "test@example.com"
TEST_PASSWORD = "securepassword123"


@pytest_asyncio.fixture
async def registered_user(client: AsyncClient) -> dict:
    """Register a user and return the response data."""
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
    )
    assert resp.status_code == 201
    return resp.json()


@pytest_asyncio.fixture
async def authenticated_client(client: AsyncClient, registered_user: dict) -> AsyncClient:
    """Login and return a client with auth cookies set."""
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
    )
    assert resp.status_code == 200
    # Cookies are set on the client automatically by httpx
    return client
```

**`backend/tests/test_auth_api.py`**

```python
import pytest
from httpx import AsyncClient

from tests.conftest import TEST_EMAIL, TEST_PASSWORD


@pytest.mark.asyncio
class TestRegister:
    async def test_register_success(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/register",
            json={"email": "new@example.com", "password": "password123"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == "new@example.com"
        assert "id" in data
        assert "hashed_password" not in data

    async def test_register_duplicate_email(self, client: AsyncClient, registered_user):
        resp = await client.post(
            "/api/v1/auth/register",
            json={"email": TEST_EMAIL, "password": "anotherpass123"},
        )
        assert resp.status_code == 409

    async def test_register_short_password(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/register",
            json={"email": "short@example.com", "password": "abc"},
        )
        assert resp.status_code == 422

    async def test_register_invalid_email(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/register",
            json={"email": "not-an-email", "password": "password123"},
        )
        assert resp.status_code == 422


@pytest.mark.asyncio
class TestLogin:
    async def test_login_success(self, client: AsyncClient, registered_user):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
        )
        assert resp.status_code == 200
        assert resp.json()["email"] == TEST_EMAIL
        assert "access_token" in resp.cookies
        assert "refresh_token" in resp.cookies

    async def test_login_wrong_password(self, client: AsyncClient, registered_user):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": TEST_EMAIL, "password": "wrongpassword"},
        )
        assert resp.status_code == 401

    async def test_login_nonexistent_user(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@example.com", "password": "password123"},
        )
        assert resp.status_code == 401


@pytest.mark.asyncio
class TestMe:
    async def test_me_authenticated(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.get("/api/v1/auth/me")
        assert resp.status_code == 200
        assert resp.json()["email"] == TEST_EMAIL

    async def test_me_unauthenticated(self, client: AsyncClient):
        resp = await client.get("/api/v1/auth/me")
        assert resp.status_code == 401


@pytest.mark.asyncio
class TestRefresh:
    async def test_refresh_rotates_tokens(self, authenticated_client: AsyncClient):
        old_access = authenticated_client.cookies.get("access_token")
        resp = await authenticated_client.post("/api/v1/auth/refresh")
        assert resp.status_code == 200
        new_access = authenticated_client.cookies.get("access_token")
        assert new_access != old_access

    async def test_refresh_without_token(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/refresh")
        assert resp.status_code == 401


@pytest.mark.asyncio
class TestLogout:
    async def test_logout_clears_cookies(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.post("/api/v1/auth/logout")
        assert resp.status_code == 200
        # After logout, /me should fail
        resp = await authenticated_client.get("/api/v1/auth/me")
        assert resp.status_code == 401
```

**`backend/tests/test_auth_service.py`**

```python
import pytest
from app.services.auth import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
    generate_refresh_token,
)
import uuid
import jwt as pyjwt


class TestPasswordHashing:
    def test_hash_and_verify(self):
        hashed = hash_password("mysecretpass")
        assert hashed != "mysecretpass"
        assert verify_password("mysecretpass", hashed)

    def test_wrong_password_fails(self):
        hashed = hash_password("correct")
        assert not verify_password("wrong", hashed)


class TestAccessToken:
    def test_create_and_decode(self):
        user_id = uuid.uuid4()
        token = create_access_token(user_id)
        payload = decode_access_token(token)
        assert payload["sub"] == str(user_id)
        assert payload["type"] == "access"

    def test_invalid_token_raises(self):
        with pytest.raises(pyjwt.PyJWTError):
            decode_access_token("garbage.token.here")


class TestRefreshToken:
    def test_generates_unique_tokens(self):
        raw1, hash1 = generate_refresh_token()
        raw2, hash2 = generate_refresh_token()
        assert raw1 != raw2
        assert hash1 != hash2

    def test_hash_is_deterministic(self):
        import hashlib
        raw, expected_hash = generate_refresh_token()
        actual_hash = hashlib.sha256(raw.encode()).hexdigest()
        assert actual_hash == expected_hash
```

---

## Frontend

### Dependencies

**`frontend/package.json`** (key `dependencies` and `devDependencies`):

```json
{
  "name": "app-frontend",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview",
    "lint": "eslint .",
    "test": "vitest run",
    "test:watch": "vitest"
  },
  "dependencies": {
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "react-router-dom": "^7.0.0"
  },
  "devDependencies": {
    "@testing-library/react": "^16.0.0",
    "@testing-library/jest-dom": "^6.6.0",
    "@testing-library/user-event": "^14.5.0",
    "@types/react": "^19.0.0",
    "@types/react-dom": "^19.0.0",
    "@eslint/js": "^10.0.0",
    "@vitejs/plugin-react": "^4.3.0",
    "eslint": "^10.0.0",
    "eslint-plugin-react-hooks": "^7.0.0",
    "jsdom": "^25.0.0",
    "typescript": "^5.7.0",
    "typescript-eslint": "^8.55.0",
    "vite": "^6.0.0",
    "vitest": "^2.1.0"
  }
}
```

### Vite Config

**`frontend/vite.config.ts`**

```typescript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    // In local dev (without Caddy), proxy API calls to backend
    proxy: {
      "/api": {
        target: "http://backend:8000",
        changeOrigin: true,
      },
    },
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: "./tests/setup.ts",
  },
});
```

### ESLint Config

**`frontend/eslint.config.mjs`**

```javascript
import eslint from "@eslint/js";
import { defineConfig } from "eslint/config";
import reactHooks from "eslint-plugin-react-hooks";
import tseslint from "typescript-eslint";

export default defineConfig(
  eslint.configs.recommended,
  tseslint.configs.recommended,
  reactHooks.configs.flat.recommended,
  {
    ignores: ["dist/"],
  },
);
```

**Notes:**
- ESLint 10 requires the flat config format (`eslint.config.mjs`); the legacy `.eslintrc` format is no longer supported.
- `tseslint.configs.recommended` automatically scopes TypeScript-specific rules to `.ts`/`.tsx` files.
- `reactHooks.configs.flat.recommended` enables `rules-of-hooks` (error) and `exhaustive-deps` (warn).

### API Client

**`frontend/src/api/client.ts`**

```typescript
export interface ApiError {
  detail: string;
}

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl = "") {
    this.baseUrl = baseUrl;
  }

  private async request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        ...options.headers,
      },
      ...options,
    });

    if (response.status === 401 && !path.includes("/auth/refresh")) {
      // Try refreshing the token once
      const refreshResp = await fetch(`${this.baseUrl}/api/v1/auth/refresh`, {
        method: "POST",
        credentials: "same-origin",
      });
      if (refreshResp.ok) {
        // Retry original request
        const retryResp = await fetch(`${this.baseUrl}${path}`, {
          credentials: "same-origin",
          headers: {
            "Content-Type": "application/json",
            ...options.headers,
          },
          ...options,
        });
        if (retryResp.ok) {
          return retryResp.json() as Promise<T>;
        }
      }
      // Refresh failed — throw so AuthContext can handle logout
      throw new AuthError("Session expired");
    }

    if (!response.ok) {
      const body = await response.json().catch(() => ({ detail: "Request failed" }));
      throw new ApiRequestError(response.status, body.detail ?? "Request failed");
    }

    return response.json() as Promise<T>;
  }

  get<T>(path: string): Promise<T> {
    return this.request<T>(path);
  }

  post<T>(path: string, body?: unknown): Promise<T> {
    return this.request<T>(path, {
      method: "POST",
      body: body ? JSON.stringify(body) : undefined,
    });
  }
}

export class AuthError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "AuthError";
  }
}

export class ApiRequestError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiRequestError";
  }
}

export const api = new ApiClient();
```

### Auth Context

**`frontend/src/contexts/AuthContext.tsx`**

```tsx
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { api, AuthError, ApiRequestError } from "../api/client";

interface User {
  id: string;
  email: string;
  is_active: boolean;
  created_at: string;
}

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchUser = useCallback(async () => {
    try {
      const data = await api.get<User>("/api/v1/auth/me");
      setUser(data);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchUser();
  }, [fetchUser]);

  const login = useCallback(async (email: string, password: string) => {
    const data = await api.post<User>("/api/v1/auth/login", { email, password });
    setUser(data);
  }, []);

  const register = useCallback(async (email: string, password: string) => {
    await api.post<User>("/api/v1/auth/register", { email, password });
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.post("/api/v1/auth/logout");
    } finally {
      setUser(null);
    }
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
```

### Components

**`frontend/src/components/LoginForm.tsx`**

```tsx
import { FormEvent, useState } from "react";
import { useAuth } from "../contexts/AuthContext";

export function LoginForm({ onSuccess }: { onSuccess?: () => void }) {
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      await login(email, password);
      onSuccess?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <h2>Login</h2>
      {error && <p role="alert">{error}</p>}
      <label>
        Email
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
      </label>
      <label>
        Password
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
      </label>
      <button type="submit" disabled={submitting}>
        {submitting ? "Logging in…" : "Login"}
      </button>
    </form>
  );
}
```

**`frontend/src/components/RegisterForm.tsx`**

```tsx
import { FormEvent, useState } from "react";
import { useAuth } from "../contexts/AuthContext";

export function RegisterForm({ onSuccess }: { onSuccess?: () => void }) {
  const { register } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    if (password !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }
    setSubmitting(true);
    try {
      await register(email, password);
      onSuccess?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <h2>Register</h2>
      {error && <p role="alert">{error}</p>}
      <label>
        Email
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
      </label>
      <label>
        Password
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          minLength={8}
        />
      </label>
      <label>
        Confirm Password
        <input
          type="password"
          value={confirmPassword}
          onChange={(e) => setConfirmPassword(e.target.value)}
          required
        />
      </label>
      <button type="submit" disabled={submitting}>
        {submitting ? "Registering…" : "Register"}
      </button>
    </form>
  );
}
```

**`frontend/src/components/ProtectedRoute.tsx`**

```tsx
import { Navigate } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import type { ReactNode } from "react";

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();

  if (loading) {
    return <div>Loading…</div>;
  }
  if (!user) {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
}
```

### Pages & App

**`frontend/src/App.tsx`**

```tsx
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider } from "./contexts/AuthContext";
import { LoginPage } from "./pages/LoginPage";
import { RegisterPage } from "./pages/RegisterPage";
import { DashboardPage } from "./pages/DashboardPage";
import { ProtectedRoute } from "./components/ProtectedRoute";

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <DashboardPage />
              </ProtectedRoute>
            }
          />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
```

**`frontend/src/pages/LoginPage.tsx`**

```tsx
import { useNavigate, Link } from "react-router-dom";
import { LoginForm } from "../components/LoginForm";

export function LoginPage() {
  const navigate = useNavigate();
  return (
    <div>
      <LoginForm onSuccess={() => navigate("/dashboard")} />
      <p>
        Don't have an account? <Link to="/register">Register</Link>
      </p>
    </div>
  );
}
```

**`frontend/src/pages/RegisterPage.tsx`**

```tsx
import { useNavigate, Link } from "react-router-dom";
import { RegisterForm } from "../components/RegisterForm";

export function RegisterPage() {
  const navigate = useNavigate();
  return (
    <div>
      <RegisterForm onSuccess={() => navigate("/login")} />
      <p>
        Already have an account? <Link to="/login">Login</Link>
      </p>
    </div>
  );
}
```

**`frontend/src/pages/DashboardPage.tsx`**

```tsx
import { useAuth } from "../contexts/AuthContext";

export function DashboardPage() {
  const { user, logout } = useAuth();

  return (
    <div>
      <h1>Dashboard</h1>
      <p>Welcome, {user?.email}</p>
      <button onClick={logout}>Logout</button>
    </div>
  );
}
```

### Frontend Tests

**`frontend/tests/setup.ts`**

```typescript
import "@testing-library/jest-dom/vitest";
```

**`frontend/tests/LoginForm.test.tsx`**

```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import { LoginForm } from "../src/components/LoginForm";
import { AuthProvider } from "../src/contexts/AuthContext";
import { BrowserRouter } from "react-router-dom";

// Mock the api client
vi.mock("../src/api/client", () => ({
  api: {
    get: vi.fn().mockRejectedValue(new Error("Not authenticated")),
    post: vi.fn(),
  },
  AuthError: class extends Error {},
  ApiRequestError: class extends Error {
    constructor(public status: number, message: string) {
      super(message);
    }
  },
}));

function renderWithProviders(ui: React.ReactElement) {
  return render(
    <BrowserRouter>
      <AuthProvider>{ui}</AuthProvider>
    </BrowserRouter>,
  );
}

describe("LoginForm", () => {
  it("renders email and password inputs", () => {
    renderWithProviders(<LoginForm />);
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
  });

  it("renders a submit button", () => {
    renderWithProviders(<LoginForm />);
    expect(screen.getByRole("button", { name: /login/i })).toBeInTheDocument();
  });

  it("requires email and password fields", () => {
    renderWithProviders(<LoginForm />);
    const emailInput = screen.getByLabelText(/email/i);
    const passwordInput = screen.getByLabelText(/password/i);
    expect(emailInput).toBeRequired();
    expect(passwordInput).toBeRequired();
  });

  it("shows error on failed login", async () => {
    const { api } = await import("../src/api/client");
    (api.post as ReturnType<typeof vi.fn>).mockRejectedValueOnce(
      new Error("Invalid credentials"),
    );

    renderWithProviders(<LoginForm />);
    const user = userEvent.setup();
    await user.type(screen.getByLabelText(/email/i), "test@example.com");
    await user.type(screen.getByLabelText(/password/i), "wrongpassword");
    await user.click(screen.getByRole("button", { name: /login/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Invalid credentials");
  });

  it("calls onSuccess after successful login", async () => {
    const { api } = await import("../src/api/client");
    (api.post as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      id: "123",
      email: "test@example.com",
      is_active: true,
      created_at: new Date().toISOString(),
    });

    const onSuccess = vi.fn();
    renderWithProviders(<LoginForm onSuccess={onSuccess} />);
    const user = userEvent.setup();
    await user.type(screen.getByLabelText(/email/i), "test@example.com");
    await user.type(screen.getByLabelText(/password/i), "password123");
    await user.click(screen.getByRole("button", { name: /login/i }));

    expect(onSuccess).toHaveBeenCalled();
  });
});
```

**`frontend/tests/RegisterForm.test.tsx`**

```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import { RegisterForm } from "../src/components/RegisterForm";
import { AuthProvider } from "../src/contexts/AuthContext";
import { BrowserRouter } from "react-router-dom";

vi.mock("../src/api/client", () => ({
  api: {
    get: vi.fn().mockRejectedValue(new Error("Not authenticated")),
    post: vi.fn(),
  },
  AuthError: class extends Error {},
  ApiRequestError: class extends Error {
    constructor(public status: number, message: string) {
      super(message);
    }
  },
}));

function renderWithProviders(ui: React.ReactElement) {
  return render(
    <BrowserRouter>
      <AuthProvider>{ui}</AuthProvider>
    </BrowserRouter>,
  );
}

describe("RegisterForm", () => {
  it("renders all form fields", () => {
    renderWithProviders(<RegisterForm />);
    expect(screen.getByLabelText(/^email$/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^password$/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/confirm password/i)).toBeInTheDocument();
  });

  it("shows error when passwords do not match", async () => {
    renderWithProviders(<RegisterForm />);
    const user = userEvent.setup();
    await user.type(screen.getByLabelText(/^email$/i), "new@example.com");
    await user.type(screen.getByLabelText(/^password$/i), "password123");
    await user.type(screen.getByLabelText(/confirm password/i), "different");
    await user.click(screen.getByRole("button", { name: /register/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Passwords do not match",
    );
  });

  it("calls onSuccess after successful registration", async () => {
    const { api } = await import("../src/api/client");
    (api.post as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      id: "123",
      email: "new@example.com",
      is_active: true,
      created_at: new Date().toISOString(),
    });

    const onSuccess = vi.fn();
    renderWithProviders(<RegisterForm onSuccess={onSuccess} />);
    const user = userEvent.setup();
    await user.type(screen.getByLabelText(/^email$/i), "new@example.com");
    await user.type(screen.getByLabelText(/^password$/i), "password123");
    await user.type(screen.getByLabelText(/confirm password/i), "password123");
    await user.click(screen.getByRole("button", { name: /register/i }));

    expect(onSuccess).toHaveBeenCalled();
  });
});
```

**`frontend/tests/AuthContext.test.tsx`**

```tsx
import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { AuthProvider, useAuth } from "../src/contexts/AuthContext";

const mockApi = {
  get: vi.fn(),
  post: vi.fn(),
};

vi.mock("../src/api/client", () => ({
  api: mockApi,
  AuthError: class extends Error {},
  ApiRequestError: class extends Error {
    constructor(public status: number, message: string) {
      super(message);
    }
  },
}));

function TestConsumer() {
  const { user, loading } = useAuth();
  if (loading) return <div>Loading</div>;
  return <div>{user ? `Logged in as ${user.email}` : "Not logged in"}</div>;
}

describe("AuthContext", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows loading state initially then resolves", async () => {
    mockApi.get.mockRejectedValueOnce(new Error("Not authenticated"));
    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>,
    );

    expect(screen.getByText("Loading")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText("Not logged in")).toBeInTheDocument();
    });
  });

  it("fetches current user on mount", async () => {
    mockApi.get.mockResolvedValueOnce({
      id: "1",
      email: "user@example.com",
      is_active: true,
      created_at: new Date().toISOString(),
    });

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByText("Logged in as user@example.com")).toBeInTheDocument();
    });
    expect(mockApi.get).toHaveBeenCalledWith("/api/v1/auth/me");
  });

  it("throws when useAuth is used outside AuthProvider", () => {
    // Suppress console.error for this test
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    expect(() => render(<TestConsumer />)).toThrow(
      "useAuth must be used within an AuthProvider",
    );
    spy.mockRestore();
  });
});
```

---

## Caddy Reverse Proxy

**`proxy/Caddyfile`**

```caddyfile
{$SITE_ADDRESS:localhost} {
    # API routes → FastAPI backend
    handle /api/* {
        reverse_proxy backend:8000
    }

    # Health check passthrough
    handle /health {
        reverse_proxy backend:8000
    }

    # Everything else → React frontend
    handle {
        reverse_proxy frontend:5173
    }
}
```

**Notes:**
- `{$SITE_ADDRESS:localhost}` uses an env var with a fallback, so the same Caddyfile works across environments.
- In production, set `SITE_ADDRESS=yourdomain.com` and Caddy auto-provisions a TLS certificate via Let's Encrypt.
- For local dev, Caddy auto-generates a self-signed cert for `localhost`. Accept the browser warning once, or install the Caddy root CA (`caddy trust`).

**`proxy/Dockerfile`**

```dockerfile
FROM caddy:2-alpine
COPY Caddyfile /etc/caddy/Caddyfile
```

---

## Docker & Docker Compose

### Backend Dockerfile

**`backend/Dockerfile`**

```dockerfile
FROM python:3.12-slim AS base
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["./entrypoint.sh"]
```

### Frontend Dockerfile

**`frontend/Dockerfile`**

A multi-stage build: dev stage serves via Vite, prod stage builds static files.

```dockerfile
# ── Dev stage ────────────────────────────────────────────────
FROM node:22-slim AS dev
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci
COPY . .
EXPOSE 5173
CMD ["npm", "run", "dev"]

# ── Build stage ──────────────────────────────────────────────
FROM node:22-slim AS build
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci
COPY . .
RUN npm run build

# ── Prod stage — serve static files via Caddy ───────────────
FROM caddy:2-alpine AS prod
COPY --from=build /app/dist /srv
COPY <<EOF /etc/caddy/Caddyfile
:5173 {
    root * /srv
    file_server
    try_files {path} /index.html
}
EOF
EXPOSE 5173
```

### Docker Compose — Base

**`docker-compose.yml`**

Defines all services with sensible defaults. Override files layer on environment-specific config.

```yaml
services:
  db:
    image: postgres:17-alpine
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-postgres}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-postgres}
      POSTGRES_DB: ${POSTGRES_DB:-app}
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-postgres}"]
      interval: 5s
      timeout: 3s
      retries: 5

  backend:
    build:
      context: ./backend
    depends_on:
      db:
        condition: service_healthy
    environment:
      DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER:-postgres}:${POSTGRES_PASSWORD:-postgres}@db:5432/${POSTGRES_DB:-app}
      JWT_SECRET_KEY: ${JWT_SECRET_KEY:?JWT_SECRET_KEY must be set}
      COOKIE_SECURE: ${COOKIE_SECURE:-true}
      COOKIE_SAMESITE: ${COOKIE_SAMESITE:-lax}

  frontend:
    build:
      context: ./frontend

  proxy:
    build:
      context: ./proxy
    ports:
      - "${PROXY_HTTP_PORT:-80}:80"
      - "${PROXY_HTTPS_PORT:-443}:443"
    depends_on:
      - backend
      - frontend
    environment:
      SITE_ADDRESS: ${SITE_ADDRESS:-localhost}

volumes:
  pgdata:
```

### Docker Compose — Local Override

**`docker-compose.local.yml`**

Hot-reload for both backend and frontend, exposed database port for direct access.

```yaml
services:
  db:
    ports:
      - "5432:5432"

  backend:
    build:
      context: ./backend
    volumes:
      - ./backend:/app
    command: ["--reload"]  # Appended to entrypoint uvicorn args
    environment:
      COOKIE_SECURE: "false"  # Allows HTTP in local dev if needed

  frontend:
    build:
      context: ./frontend
      target: dev
    volumes:
      - ./frontend:/app
      - /app/node_modules  # Preserve container's node_modules
```

Start local dev:

```bash
docker compose -f docker-compose.yml -f docker-compose.local.yml up --build
```

### Docker Compose — Staging Override

**`docker-compose.staging.yml`**

```yaml
services:
  backend:
    restart: unless-stopped

  frontend:
    build:
      context: ./frontend
      target: prod
    restart: unless-stopped

  proxy:
    restart: unless-stopped
    environment:
      SITE_ADDRESS: ${STAGING_DOMAIN}
```

### Docker Compose — Production Override

**`docker-compose.prod.yml`**

```yaml
services:
  db:
    restart: always

  backend:
    restart: always
    environment:
      COOKIE_SECURE: "true"
      COOKIE_SAMESITE: "lax"

  frontend:
    build:
      context: ./frontend
      target: prod
    restart: always

  proxy:
    restart: always
    volumes:
      - caddy_data:/data
      - caddy_config:/config
    environment:
      SITE_ADDRESS: ${PRODUCTION_DOMAIN}

volumes:
  caddy_data:
  caddy_config:
```

Start production:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

---

## GitHub Actions CI

### Backend Workflow

**`.github/workflows/backend.yml`**

```yaml
name: Backend CI

on:
  push:
    paths:
      - "backend/**"
      - ".github/workflows/backend.yml"
  pull_request:
    paths:
      - "backend/**"
      - ".github/workflows/backend.yml"

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install ruff
      - run: ruff check backend/
      - run: ruff format --check backend/

  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:17-alpine
        env:
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: app_test
        ports:
          - 5432:5432
        options: >-
          --health-cmd "pg_isready -U postgres"
          --health-interval 5s
          --health-timeout 3s
          --health-retries 5

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip
          cache-dependency-path: backend/requirements.txt
      - run: pip install -r backend/requirements.txt
        working-directory: backend
      - run: pytest tests/ -v --tb=short
        working-directory: backend
        env:
          DATABASE_URL: postgresql+asyncpg://postgres:postgres@localhost:5432/app_test
          JWT_SECRET_KEY: test-secret-key-for-ci-only

  docker-build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: docker build -t app-backend ./backend
```

### Frontend Workflow

**`.github/workflows/frontend.yml`**

```yaml
name: Frontend CI

on:
  push:
    paths:
      - "frontend/**"
      - ".github/workflows/frontend.yml"
  pull_request:
    paths:
      - "frontend/**"
      - ".github/workflows/frontend.yml"

jobs:
  lint-and-typecheck:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 22
          cache: npm
          cache-dependency-path: frontend/package-lock.json
      - run: npm ci
        working-directory: frontend
      - run: npx eslint .
        working-directory: frontend
      - run: npx tsc --noEmit
        working-directory: frontend

  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 22
          cache: npm
          cache-dependency-path: frontend/package-lock.json
      - run: npm ci
        working-directory: frontend
      - run: npm test
        working-directory: frontend

  docker-build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: docker build --target prod -t app-frontend ./frontend
```

### Proxy Workflow

**`.github/workflows/proxy.yml`**

```yaml
name: Proxy CI

on:
  push:
    paths:
      - "proxy/**"
      - ".github/workflows/proxy.yml"
  pull_request:
    paths:
      - "proxy/**"
      - ".github/workflows/proxy.yml"

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Validate Caddyfile
        run: |
          docker run --rm \
            -v ${{ github.workspace }}/proxy/Caddyfile:/etc/caddy/Caddyfile \
            caddy:2-alpine caddy validate --config /etc/caddy/Caddyfile

  docker-build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: docker build -t app-proxy ./proxy
```

---

## Environment Variables Reference

**`.env.example`**

```bash
# ── Database ─────────────────────────────────────────────────
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=app

# ── Auth ─────────────────────────────────────────────────────
JWT_SECRET_KEY=          # REQUIRED — generate with: python -c "import secrets; print(secrets.token_urlsafe(64))"

# ── Cookies ──────────────────────────────────────────────────
COOKIE_SECURE=true       # Set to false for local HTTP dev without Caddy
COOKIE_SAMESITE=lax
COOKIE_DOMAIN=           # Leave empty for current domain only

# ── Proxy ────────────────────────────────────────────────────
SITE_ADDRESS=localhost   # Set to your domain in staging/production
PROXY_HTTP_PORT=80
PROXY_HTTPS_PORT=443

# ── Deployment domains ───────────────────────────────────────
STAGING_DOMAIN=staging.example.com
PRODUCTION_DOMAIN=example.com
```

---

## Security Notes

1. **Refresh token path scoping:** The refresh token cookie has `path="/api/v1/auth"` so it is only sent with auth-related requests, not every API call. This reduces exposure.

2. **Token rotation:** Every use of a refresh token invalidates it and issues a new one. If an attacker replays a stolen refresh token after the legitimate user has already used it, the token will be revoked and the rotation fails. Consider also revoking all of a user's refresh tokens if a reuse is detected (indicates theft).

3. **Password requirements:** The service enforces a minimum 8-character password. Add further complexity rules as needed, but favour length over complexity per NIST SP 800-63B.

4. **HTTPS is mandatory:** HttpOnly + Secure cookies require TLS. Caddy handles this automatically. Never set `COOKIE_SECURE=false` in production.

5. **CSRF:** Because the API uses `SameSite=Lax` cookies and only mutates state on POST requests (not GET), CSRF protection is implicit. If you add PUT/DELETE endpoints, they are also safe under `Lax` as browsers only auto-attach cookies for top-level navigations (which are always GET). For extra safety, add a `X-Requested-With` header check or CSRF tokens.

6. **Rate limiting:** Not included in this template. Add rate limiting middleware (e.g., `slowapi` for FastAPI) on `/auth/login` and `/auth/register` to prevent brute-force attacks.

7. **Refresh token cleanup:** Expired and revoked tokens accumulate in the database. Add a periodic task (cron job or Celery beat) to delete tokens where `expires_at < now()` or `revoked_at IS NOT NULL`.

---

## Known Limitations & Future Improvements

1. **Fragile test database URL derivation:** The test conftest derives the test database URL via `settings.database_url.replace("/app", "/app_test")`, which breaks if the database name changes. Replace this with a dedicated `TEST_DATABASE_URL` environment variable for robustness.

2. **`AuthError` not explicitly handled in the frontend:** The `AuthError` class thrown by the API client on session expiry is caught generically by `AuthContext` (the `catch` in `fetchUser`) and by the forms (the `catch (err)` block). This works, but there is no dedicated session-expired UX (e.g., a toast notification or redirect with a message). When building out the template, add an `AuthError`-specific catch in `AuthContext` that triggers a user-visible "Session expired, please log in again" flow.

3. **No rate limiting on auth endpoints:** The `/auth/login` and `/auth/register` endpoints have no brute-force protection. Add `slowapi` (or equivalent) middleware before deploying to any environment. Example configuration:

   ```python
   from slowapi import Limiter
   from slowapi.util import get_remote_address

   limiter = Limiter(key_func=get_remote_address)

   @router.post("/login")
   @limiter.limit("5/minute")
   async def login(...):
       ...
   ```
