import pytest
from httpx import AsyncClient

from tests.conftest import TEST_EMAIL, TEST_PASSWORD


@pytest.mark.asyncio
class TestRegister:
    async def test_register_success(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/register",
            json={"email": "new@example.com", "password": "ValidPass123!"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == "new@example.com"
        assert "id" in data
        assert "hashed_password" not in data

    async def test_register_duplicate_email(self, client: AsyncClient, registered_user):
        resp = await client.post(
            "/api/v1/auth/register",
            json={"email": TEST_EMAIL, "password": "AnotherPass123!"},
        )
        assert resp.status_code == 409

    async def test_register_short_password(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/register",
            json={"email": "short@example.com", "password": "abc"},
        )
        assert resp.status_code == 422

    async def test_register_weak_password_no_uppercase(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/register",
            json={"email": "weak@example.com", "password": "password123!"},
        )
        assert resp.status_code == 422
        assert "uppercase" in resp.json()["detail"].lower()

    async def test_register_weak_password_no_special(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/register",
            json={"email": "weak@example.com", "password": "Password123"},
        )
        assert resp.status_code == 422
        assert "special" in resp.json()["detail"].lower()

    async def test_register_invalid_email(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/register",
            json={"email": "not-an-email", "password": "ValidPass123!"},
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
            json={"email": TEST_EMAIL, "password": "WrongPass123!"},
        )
        assert resp.status_code == 401

    async def test_login_nonexistent_user(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@example.com", "password": "ValidPass123!"},
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
        old_refresh = authenticated_client.cookies.get("refresh_token")
        resp = await authenticated_client.post("/api/v1/auth/refresh")
        assert resp.status_code == 200
        new_refresh = authenticated_client.cookies.get("refresh_token")
        # Refresh token should be rotated (different)
        assert new_refresh != old_refresh
        # Response should include user data
        assert resp.json()["email"] == "test@example.com"

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
