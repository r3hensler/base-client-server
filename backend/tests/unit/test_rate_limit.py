from unittest.mock import MagicMock

from app.rate_limit import _get_client_ip


def _make_request(headers: dict | None = None, client_host: str = "127.0.0.1"):
    """Build a minimal mock Request with the given headers and client host."""
    request = MagicMock()
    request.headers = headers or {}
    request.client.host = client_host
    return request


class TestGetClientIp:
    def test_returns_x_real_ip_when_present(self):
        request = _make_request(headers={"X-Real-IP": "203.0.113.1"})
        assert _get_client_ip(request) == "203.0.113.1"

    def test_strips_whitespace_from_x_real_ip(self):
        request = _make_request(headers={"X-Real-IP": "  203.0.113.1  "})
        assert _get_client_ip(request) == "203.0.113.1"

    def test_falls_back_to_client_host_without_x_real_ip(self):
        request = _make_request(client_host="10.0.0.5")
        assert _get_client_ip(request) == "10.0.0.5"

    def test_ignores_x_forwarded_for(self):
        """X-Forwarded-For is client-spoofable and should not be used."""
        request = _make_request(
            headers={"X-Forwarded-For": "spoofed-ip"},
            client_host="10.0.0.5",
        )
        assert _get_client_ip(request) == "10.0.0.5"

    def test_x_real_ip_takes_precedence_over_client_host(self):
        request = _make_request(
            headers={"X-Real-IP": "203.0.113.1"},
            client_host="10.0.0.5",
        )
        assert _get_client_ip(request) == "203.0.113.1"

    def test_returns_unknown_when_no_client(self):
        request = MagicMock()
        request.headers = {}
        request.client = None
        assert _get_client_ip(request) == "unknown"
