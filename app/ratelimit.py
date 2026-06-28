"""Rate limiting via slowapi (in-memory, per client IP)."""
from __future__ import annotations

from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.requests import Request
from starlette.responses import JSONResponse

from .config import settings
from .errors import error_body

limiter = Limiter(key_func=get_remote_address)


def rate_limit_exceeded_handler(_request: Request, _exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content=error_body("rate_limited", "Too many requests. Please slow down and try again shortly."),
    )


# Convenience accessors for decorators on routes.
REGISTER_LIMIT = settings.rate_limit_register
LOGIN_LIMIT = settings.rate_limit_login
