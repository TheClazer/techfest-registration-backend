"""Registration business logic: create a student + their pending ticket."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..errors import AppError
from ..models import Role, Ticket, User
from ..security import hash_password


def register_student(db: Session, *, name: str, email: str, password: str) -> tuple[User, Ticket]:
    """Create a student account and a pending-payment ticket.

    Idempotency / dedup: the email is normalized and checked up-front (fast, before the
    expensive hash), and the database UNIQUE constraint is the hard guarantee against a
    concurrent duplicate slipping through.
    """
    email_norm = email.strip().lower()

    if db.scalar(select(User).where(User.email == email_norm)) is not None:
        raise AppError(409, "email_taken", "An account with this email already exists.")

    # Only hash once we know the email is free (don't burn a memory-hard hash on a dup).
    password_hash = hash_password(password)

    user = User(name=name.strip(), email=email_norm, password_hash=password_hash, role=Role.student)
    ticket = Ticket(user=user)
    db.add(user)
    db.add(ticket)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        # Lost a race against a concurrent identical registration.
        raise AppError(409, "email_taken", "An account with this email already exists.") from exc

    db.refresh(user)
    db.refresh(ticket)
    return user, ticket
