from starlette.requests import Request

from slowapi import Limiter


def _get_client_ip(request: Request) -> str:
    """Derive client IP from the connection information for rate limiting."""
    return request.client.host if request.client else "unknown"


# Uses in-memory storage by default. Rate limits reset on deploy/restart
# and are per-instance. If scaling to multiple backend instances, switch
# to Redis: Limiter(key_func=..., storage_uri="redis://...")
limiter = Limiter(key_func=_get_client_ip)
