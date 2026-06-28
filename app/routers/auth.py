"""Authentication endpoints: register and login.

Note: this module intentionally does NOT use ``from __future__ import annotations``.
slowapi's ``@limiter.limit`` wraps the endpoint, and FastAPI resolves string
annotations against the wrapper's globals — which would not contain our schema names.
Keeping real (eagerly-evaluated) annotations avoids that resolution failure.
"""
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..errors import AppError
from ..jobs import get_job, submit
from ..models import User
from ..ratelimit import LOGIN_LIMIT, REGISTER_LIMIT, limiter
from ..schemas import (
    JobAccepted,
    JobStatus,
    LoginRequest,
    RegisterRequest,
    RegisterResponse,
    TicketOut,
    TokenResponse,
    UserOut,
)
from ..security import DUMMY_PASSWORD_HASH, create_access_token, verify_password
from ..services.registration import register_student

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new student and create their pending ticket",
)
@limiter.limit(REGISTER_LIMIT)
def register(request: Request, payload: RegisterRequest, db: Session = Depends(get_db)) -> RegisterResponse:
    user, ticket = register_student(
        db, name=payload.name, email=payload.email, password=payload.password
    )
    token = create_access_token(user_id=user.id, role=user.role.value)
    return RegisterResponse(
        user=UserOut.model_validate(user),
        ticket=TicketOut.model_validate(ticket),
        access_token=token,
    )


@router.post("/login", response_model=TokenResponse, summary="Log in and receive a JWT access token")
@limiter.limit(LOGIN_LIMIT)
def login(request: Request, payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    email_norm = payload.email.strip().lower()
    user = db.scalar(select(User).where(User.email == email_norm))

    if user is None:
        # Spend the same time as a real verify so timing can't enumerate accounts.
        verify_password(DUMMY_PASSWORD_HASH, payload.password)
        raise AppError(401, "invalid_credentials", "Invalid email or password.")

    if not verify_password(user.password_hash, payload.password):
        raise AppError(401, "invalid_credentials", "Invalid email or password.")

    token = create_access_token(user_id=user.id, role=user.role.value)
    return TokenResponse(access_token=token, user=UserOut.model_validate(user))


@router.post(
    "/register-async",
    response_model=JobAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Queue a registration and return immediately (async path — see SCALE.md)",
)
@limiter.limit(REGISTER_LIMIT)
def register_async(request: Request, payload: RegisterRequest, db: Session = Depends(get_db)) -> JobAccepted:
    # Reject known duplicates up front (the worker also guards via the UNIQUE constraint).
    if db.scalar(select(User).where(User.email == payload.email.strip().lower())) is not None:
        raise AppError(409, "email_taken", "An account with this email already exists.")
    job_id = submit(name=payload.name, email=payload.email, password=payload.password)
    return JobAccepted(job_id=job_id, status="pending", status_url=f"/auth/register/status/{job_id}")


@router.get(
    "/register/status/{job_id}",
    response_model=JobStatus,
    summary="Poll the status of an async registration job",
)
def register_status(job_id: str) -> JobStatus:
    job = get_job(job_id)
    if job is None:
        raise AppError(404, "job_not_found", "No registration job with that id.")
    return JobStatus(job_id=job_id, status=job["status"], result=job["result"], error=job["error"])
