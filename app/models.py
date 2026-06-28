"""SQLAlchemy ORM models: User, Ticket, Payment."""
from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_uuid() -> str:
    return str(uuid.uuid4())


class Role(str, enum.Enum):
    student = "student"
    volunteer = "volunteer"


class TicketStatus(str, enum.Enum):
    pending_payment = "pending_payment"
    confirmed = "confirmed"
    checked_in = "checked_in"


class PaymentStatus(str, enum.Enum):
    created = "created"
    paid = "paid"
    failed = "failed"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[Role] = mapped_column(Enum(Role), default=Role.student, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    ticket: Mapped["Ticket | None"] = relationship(
        back_populates="user",
        uselist=False,
        foreign_keys="Ticket.user_id",
    )


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, nullable=False)
    status: Mapped[TicketStatus] = mapped_column(
        Enum(TicketStatus), default=TicketStatus.pending_payment, nullable=False, index=True
    )
    # Stable opaque id; the QR encodes a *signed* form of this (never the raw db id).
    ticket_uuid: Mapped[str] = mapped_column(
        String(36), unique=True, index=True, default=new_uuid, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    checked_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    checked_in_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    user: Mapped["User"] = relationship(back_populates="ticket", foreign_keys=[user_id])


class EventSeats(Base):
    """Singleton (id == 1) seat counter used for race-free capacity enforcement.

    Confirming a payment does ``UPDATE event_seats SET sold = sold + 1 WHERE id = 1
    AND sold < :capacity``. Because the condition and the increment happen in one
    atomic statement on a single row — and SQLite serializes writers — overselling
    the last seat is impossible no matter how many webhooks arrive at once.
    """

    __tablename__ = "event_seats"

    id: Mapped[int] = mapped_column(primary_key=True)  # always 1
    sold: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    order_id: Mapped[str] = mapped_column(String(40), unique=True, index=True, nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)  # paise
    currency: Mapped[str] = mapped_column(String(8), default="INR", nullable=False)
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus), default=PaymentStatus.created, nullable=False
    )
    provider_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
