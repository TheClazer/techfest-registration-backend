"""FastAPI application factory: wiring middleware, error handlers, and routers."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from slowapi.errors import RateLimitExceeded

from .config import settings
from .database import init_db
from .errors import register_exception_handlers
from .logging_mw import RequestContextMiddleware
from .ratelimit import limiter, rate_limit_exceeded_handler
from .routers import auth, checkin, health, payments, registrations, tickets

DESCRIPTION = (
    "Backend API for the IEEE RVCE Tech Fest registration system — authentication, "
    "registration, payment, QR tickets, and gate check-in. See `/docs` for the live API."
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


def create_app() -> FastAPI:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    app = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        description=DESCRIPTION,
        lifespan=lifespan,
    )

    # Rate limiting
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

    # Middleware + error envelope
    app.add_middleware(RequestContextMiddleware)
    register_exception_handlers(app)

    # Routers
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(tickets.router)
    app.include_router(payments.router)
    app.include_router(checkin.router)
    app.include_router(registrations.router)

    return app


app = create_app()
