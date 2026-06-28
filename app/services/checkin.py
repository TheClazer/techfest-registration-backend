"""Check-in business logic: verify the QR token and atomically admit the holder."""
from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..errors import AppError
from ..models import Ticket, TicketStatus, User, utcnow
from ..security import verify_ticket


def check_in(db: Session, *, ticket_code: str, volunteer: User) -> tuple[Ticket, User]:
    ticket_uuid = verify_ticket(ticket_code)
    if ticket_uuid is None:
        raise AppError(400, "invalid_ticket", "This QR code is invalid or has been tampered with.")

    ticket = db.scalar(select(Ticket).where(Ticket.ticket_uuid == ticket_uuid))
    if ticket is None:
        raise AppError(404, "ticket_not_found", "No ticket matches this code.")

    # Atomic, conditional transition: confirmed -> checked_in. Two volunteers scanning
    # the same ticket at once is safe — SQLite serializes the writes, so exactly one
    # UPDATE matches `status == confirmed` and the other affects zero rows.
    result = db.execute(
        update(Ticket)
        .where(Ticket.id == ticket.id, Ticket.status == TicketStatus.confirmed)
        .values(status=TicketStatus.checked_in, checked_in_at=utcnow(), checked_in_by=volunteer.id)
    )

    if result.rowcount == 0:
        db.rollback()
        current = db.get(Ticket, ticket.id)  # fresh read after rollback
        if current is not None and current.status == TicketStatus.checked_in:
            when = current.checked_in_at.isoformat() if current.checked_in_at else "earlier"
            raise AppError(409, "already_checked_in", f"This ticket was already checked in at {when}.")
        raise AppError(409, "not_confirmed", "This ticket is not paid/confirmed and cannot be checked in.")

    db.commit()
    db.refresh(ticket)
    student = db.get(User, ticket.user_id)
    return ticket, student
