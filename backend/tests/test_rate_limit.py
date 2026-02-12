import pytest
from httpx import AsyncClient

from app.rate_limit import limiter
from tests.conftest import TEST_PASSWORD


@pytest.fixture(autouse=True)
def _enable_rate_limiter():
    """Enable the rate limiter for this module and reset storage after each test."""
    limiter.enabled = True
    yield
    limiter.enabled = False
    limiter.reset()


@pytest.mark.asyncio
class TestLoginRateLimit:
    async def test_login_returns_429_after_limit_exceeded(self, client: AsyncClient):
        """Login endpoint should return 429 after 5 requests in a minute."""
        for i in range(5):
            resp = await client.post(
                "/api/v1/auth/login",
                json={"email": "no@example.com", "password": "Wrong123!"},
            )
            assert resp.status_code == 401, f"Request {i + 1} should return 401"

        # 6th request should be rate limited
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "no@example.com", "password": "Wrong123!"},
        )
        assert resp.status_code == 429

    async def test_login_rate_limit_is_per_ip(self, client: AsyncClient, db_session):
        """Different IPs should have independent rate limit buckets."""
        # Exhaust limit for IP "10.0.0.1"
        for _ in range(5):
            resp = await client.post(
                "/api/v1/auth/login",
                json={"email": "no@example.com", "password": "Wrong123!"},
                headers={"X-Real-IP": "10.0.0.1"},
            )
            assert resp.status_code == 401

        # 10.0.0.1 should be rate limited
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "no@example.com", "password": "Wrong123!"},
            headers={"X-Real-IP": "10.0.0.1"},
        )
        assert resp.status_code == 429

        # 10.0.0.2 should still be allowed
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "no@example.com", "password": "Wrong123!"},
            headers={"X-Real-IP": "10.0.0.2"},
        )
        assert resp.status_code == 401


@pytest.mark.asyncio
class TestRegisterRateLimit:
    async def test_register_returns_429_after_limit_exceeded(self, client: AsyncClient):
        """Register endpoint should return 429 after 3 requests in an hour."""
        for i in range(3):
            resp = await client.post(
                "/api/v1/auth/register",
                json={"email": f"user{i}@example.com", "password": TEST_PASSWORD},
            )
            # 201 for new users
            assert resp.status_code == 201, f"Request {i + 1} should return 201"

        # 4th request should be rate limited
        resp = await client.post(
            "/api/v1/auth/register",
            json={"email": "user99@example.com", "password": TEST_PASSWORD},
        )
        assert resp.status_code == 429
