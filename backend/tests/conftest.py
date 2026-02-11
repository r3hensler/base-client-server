import asyncio
import uuid
from collections.abc import AsyncGenerator
import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.database import Base, get_db
from app.main import app

# Use a separate test database
# Prefer TEST_DATABASE_URL env var, otherwise derive from main database URL
TEST_DB_URL = os.getenv(
    "TEST_DATABASE_URL",
    settings.database_url.rsplit("/", 1)[0] + "/app_test"
)


@pytest_asyncio.fixture(scope="function")
async def engine():
    """Create a fresh engine for each test with production-like pool settings."""
    test_engine = create_async_engine(
        TEST_DB_URL,
        echo=False,
        pool_size=5,
        max_overflow=5,
        pool_timeout=10,
        pool_recycle=3600,
        pool_pre_ping=True,
    )
    yield test_engine
    await test_engine.dispose()


@pytest_asyncio.fixture(scope="function", autouse=True)
async def setup_db(engine):
    """Create and clean up database schema for each test."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Clean up after test
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session(engine) -> AsyncGenerator[AsyncSession, None]:
    TestSession = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
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
TEST_PASSWORD = "SecurePass123!"  # Meets all password requirements


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
