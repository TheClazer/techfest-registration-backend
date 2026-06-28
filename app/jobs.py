"""In-memory background registration queue — the additive async path from SCALE.md.

`register-async` accepts a job and returns ``202`` immediately; a fixed pool of worker
threads drains the queue and runs the memory-hard hash off the request path. Hashing is
still bounded by the same Argon2 semaphore (`security.py`), so the memory ceiling is
unchanged. Job state is in-memory and is lost on restart — a durable queue (Redis) would
be the next step (see SCALE.md). The synchronous `/auth/register` is unaffected.
"""
from __future__ import annotations

import queue
import threading
import uuid
from typing import Any

from .config import settings
from .database import SessionLocal
from .errors import AppError
from .schemas import RegisterResponse, TicketOut, UserOut
from .security import create_access_token
from .services.registration import register_student

_jobs: dict[str, dict[str, Any]] = {}
_inflight: dict[str, str] = {}  # normalized email -> pending job_id (dedupe before enqueue)
_lock = threading.Lock()
_queue: "queue.Queue[tuple[str, dict]]" = queue.Queue(maxsize=settings.queue_max)
_started = False


def _set(job_id: str, status: str, *, result: Any = None, error: Any = None) -> None:
    with _lock:
        _jobs[job_id] = {"status": status, "result": result, "error": error}


def get_job(job_id: str) -> dict | None:
    with _lock:
        job = _jobs.get(job_id)
        return dict(job) if job else None


def submit(*, name: str, email: str, password: str) -> str:
    """Enqueue a registration job and return its id.

    Dedupe-before-enqueue: if a job for this email is already pending, its id is returned
    instead of queuing a second (each queued job is ~46 MiB of future work). Raises a 503
    AppError if the queue is full (graceful load-shedding).
    """
    email_norm = email.strip().lower()
    with _lock:
        existing = _inflight.get(email_norm)
        if existing is not None:
            return existing
        job_id = uuid.uuid4().hex
        _inflight[email_norm] = job_id
        _jobs[job_id] = {"status": "pending", "result": None, "error": None}

    try:
        _queue.put_nowait((job_id, {"name": name, "email": email, "password": password}))
    except queue.Full:
        with _lock:
            _inflight.pop(email_norm, None)
            _jobs.pop(job_id, None)
        raise AppError(503, "overloaded", "Registration queue is full. Please retry shortly.")
    return job_id


def _worker() -> None:
    while True:
        job_id, payload = _queue.get()
        email_norm = payload["email"].strip().lower()
        db = SessionLocal()
        try:
            user, ticket = register_student(
                db, name=payload["name"], email=payload["email"], password=payload["password"]
            )
            token = create_access_token(user_id=user.id, role=user.role.value)
            result = RegisterResponse(
                user=UserOut.model_validate(user),
                ticket=TicketOut.model_validate(ticket),
                access_token=token,
            ).model_dump(mode="json")
            _set(job_id, "completed", result=result)
        except AppError as exc:
            _set(job_id, "failed", error={"code": exc.code, "message": exc.message})
        except Exception:
            _set(job_id, "failed", error={"code": "internal_error", "message": "Registration failed."})
        finally:
            db.close()
            with _lock:
                _inflight.pop(email_norm, None)
            _queue.task_done()


def start_workers() -> None:
    """Start the worker pool once (idempotent). Pool size == HASH_CONCURRENCY."""
    global _started
    with _lock:
        if _started:
            return
        _started = True
    for i in range(max(1, settings.hash_concurrency)):
        threading.Thread(target=_worker, name=f"reg-worker-{i}", daemon=True).start()
