"""Uniform error envelope and global exception handlers.

Every error response has the shape:

    {"error": {"code": "<machine_code>", "message": "<human readable>", "details": <optional>}}
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("techfest.error")

_STATUS_CODE_NAMES = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    422: "invalid_input",
    429: "rate_limited",
}


def error_body(code: str, message: str, details: Any | None = None, request_id: str | None = None) -> dict:
    err: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        err["details"] = details
    if request_id is not None:
        err["request_id"] = request_id  # echoes the X-Request-ID header for traceability
    return {"error": err}


def _rid(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


class AppError(Exception):
    """Domain error that maps cleanly to an HTTP response."""

    def __init__(self, status_code: int, code: str, message: str, details: Any | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _handle_app_error(request: Request, exc: AppError):
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(exc.code, exc.message, exc.details, _rid(request)),
        )

    @app.exception_handler(RequestValidationError)
    async def _handle_validation(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content=error_body(
                "invalid_input", "Request validation failed.", jsonable_encoder(exc.errors()), _rid(request)
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _handle_http(request: Request, exc: StarletteHTTPException):
        code = _STATUS_CODE_NAMES.get(exc.status_code, "error")
        message = exc.detail if isinstance(exc.detail, str) else "Request failed."
        return JSONResponse(status_code=exc.status_code, content=error_body(code, message, request_id=_rid(request)))

    @app.exception_handler(Exception)
    async def _handle_unhandled(request: Request, exc: Exception):  # noqa: ARG001
        request_id = _rid(request)
        logger.exception("unhandled exception rid=%s", request_id)
        return JSONResponse(
            status_code=500,
            content=error_body("internal_error", "An unexpected error occurred.", request_id=request_id),
        )
