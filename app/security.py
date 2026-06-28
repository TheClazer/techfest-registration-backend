"""Security primitives: bounded Argon2id hashing, JWT access tokens, signed ticket tokens."""
from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from itsdangerous import BadSignature, URLSafeSerializer

from .config import settings

# --------------------------------------------------------------------------- #
# Password hashing (Argon2id) — bounded concurrency
# --------------------------------------------------------------------------- #

_password_hasher = PasswordHasher(
    time_cost=settings.argon2_time_cost,
    memory_cost=settings.argon2_memory_cost,
    parallelism=settings.argon2_parallelism,
)

# Cap simultaneous Argon2id operations so peak memory is a fixed ceiling regardless
# of incoming load. This is the implemented core of the SCALE.md strategy: FastAPI
# runs sync routes in a threadpool, and this semaphore bounds how many of those
# threads may be inside an (expensive, memory-hard) hash/verify at once.
#
# NOTE: While this protects memory, it causes requests to block in the sync threadpool,
# leading to high latencies (up to 80s) during a registration spike since there is no
# actual background job queue implemented.
_HASH_SEMAPHORE = threading.BoundedSemaphore(settings.hash_concurrency)


def hash_password(password: str) -> str:
    with _HASH_SEMAPHORE:
        return _password_hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    with _HASH_SEMAPHORE:
        try:
            return _password_hasher.verify(password_hash, password)
        except (VerificationError, InvalidHashError):
            return False


# A real Argon2id hash used to equalize verification time when the email is
# unknown, so login response time cannot be used to enumerate accounts.
DUMMY_PASSWORD_HASH = _password_hasher.hash("not-a-real-password")


# --------------------------------------------------------------------------- #
# JWT access tokens
# --------------------------------------------------------------------------- #


def create_access_token(*, user_id: int, role: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.jwt_expire_minutes)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    """Decode and validate a JWT. Raises jwt.PyJWTError on any problem."""
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


# --------------------------------------------------------------------------- #
# Signed ticket tokens (what the QR encodes)
# --------------------------------------------------------------------------- #

_ticket_serializer = URLSafeSerializer(settings.ticket_secret, salt="techfest-ticket")


def sign_ticket(ticket_uuid: str) -> str:
    """Return a tamper-proof token for a ticket. Encoded into the QR code."""
    return _ticket_serializer.dumps({"tid": ticket_uuid})


def verify_ticket(token: str) -> str | None:
    """Return the ticket_uuid if the token is authentic, else None."""
    try:
        data = _ticket_serializer.loads(token)
    except BadSignature:
        return None
    if not isinstance(data, dict):
        return None
    return data.get("tid")
