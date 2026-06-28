"""Pytest fixtures. Environment is configured *before* the app is imported."""
import os
import pathlib
import tempfile

# Configure a fast, isolated test environment before any app import reads settings.
os.environ.setdefault("JWT_SECRET", "test-jwt-secret")
os.environ.setdefault("TICKET_SECRET", "test-ticket-secret")
os.environ.setdefault("PAYMENT_WEBHOOK_SECRET", "test-webhook-secret")
os.environ.setdefault("ARGON2_MEMORY_COST", "8192")  # 8 MiB — keep hashing fast in tests
os.environ.setdefault("ARGON2_TIME_COST", "1")
_DB_PATH = pathlib.Path(tempfile.gettempdir()) / "techfest_pytest.db"
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_DB_PATH.as_posix()}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import models  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.ratelimit import limiter  # noqa: E402

# Rate limiting uses a process-global in-memory store keyed by client IP; under the
# test client every request shares one IP, so the cap would bleed across tests.
# Disable it for the suite (the 429 path is verified separately).
limiter.enabled = False


@pytest.fixture(autouse=True)
def fresh_db():
    """Reset schema + seed the seat counter before every test for full isolation."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        db.add(models.EventSeats(id=1, sold=0))
        db.commit()
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(fresh_db):
    with TestClient(app) as test_client:
        yield test_client
