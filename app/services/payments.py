"""Payment business logic: order creation and (mock) signed-webhook confirmation."""
from __future__ import annotations

import hashlib
import hmac
import secrets

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..config import settings
from ..errors import AppError
from ..models import EventSeats, Payment, PaymentStatus, Ticket, TicketStatus, User, utcnow

_READY = (TicketStatus.confirmed, TicketStatus.checked_in)


def _gen_order_id() -> str:
    return "order_" + secrets.token_hex(12)


def compute_signature(order_id: str, status: str) -> str:
    """HMAC-SHA256 of ``"<order_id>:<status>"`` keyed by the webhook secret."""
    message = f"{order_id}:{status}".encode()
    return hmac.new(settings.payment_webhook_secret.encode(), message, hashlib.sha256).hexdigest()


def create_order(db: Session, *, user: User) -> Payment:
    ticket = user.ticket
    if ticket is None:
        raise AppError(404, "no_ticket", "You do not have a ticket to pay for.")
    if ticket.status in _READY:
        raise AppError(409, "already_paid", "This ticket has already been paid for.")

    # Idempotent: reuse the open order instead of minting a second one.
    existing = db.scalar(
        select(Payment).where(Payment.ticket_id == ticket.id, Payment.status == PaymentStatus.created)
    )
    if existing is not None:
        return existing

    payment = Payment(
        ticket_id=ticket.id,
        user_id=user.id,
        order_id=_gen_order_id(),
        amount=settings.ticket_price,
        currency=settings.currency,
        status=PaymentStatus.created,
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return payment


def process_webhook(db: Session, *, order_id: str, status: str, signature: str) -> tuple[Payment, Ticket]:
    expected = compute_signature(order_id, status)
    if not hmac.compare_digest(expected, signature):
        raise AppError(400, "invalid_signature", "Webhook signature verification failed.")

    payment = db.scalar(select(Payment).where(Payment.order_id == order_id))
    if payment is None:
        raise AppError(404, "order_not_found", "No payment order with that id.")
    ticket = db.get(Ticket, payment.ticket_id)

    # Idempotency: a replayed webhook must not double-process.
    if payment.status == PaymentStatus.paid:
        return payment, ticket
    if payment.status == PaymentStatus.failed:
        raise AppError(409, "payment_failed", "This payment has already been marked failed.")

    # Gateway reported a non-success outcome.
    if status != "paid":
        payment.status = PaymentStatus.failed
        db.commit()
        db.refresh(payment)
        db.refresh(ticket)
        return payment, ticket

    # Success path: atomically claim a seat, then confirm the ticket.
    seat = db.execute(
        update(EventSeats)
        .where(EventSeats.id == 1, EventSeats.sold < settings.capacity)
        .values(sold=EventSeats.sold + 1)
    )
    if seat.rowcount == 0:
        payment.status = PaymentStatus.failed
        db.commit()
        raise AppError(409, "sold_out", "The event is sold out.")

    confirmed = db.execute(
        update(Ticket)
        .where(Ticket.id == ticket.id, Ticket.status == TicketStatus.pending_payment)
        .values(status=TicketStatus.confirmed, confirmed_at=utcnow())
    )
    if confirmed.rowcount == 0:
        # Ticket wasn't pending (already confirmed by another path) — give the seat back.
        db.execute(update(EventSeats).where(EventSeats.id == 1).values(sold=EventSeats.sold - 1))

    payment.status = PaymentStatus.paid
    payment.paid_at = utcnow()
    payment.provider_ref = "mock_" + secrets.token_hex(8)
    db.commit()
    db.refresh(payment)
    db.refresh(ticket)
    return payment, ticket
