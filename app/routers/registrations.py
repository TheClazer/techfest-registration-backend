"""Volunteer/admin views: list all registrations and event stats."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from ..config import settings
from ..database import get_db
from ..deps import require_role
from ..models import EventSeats, Role, Ticket, TicketStatus, User
from ..schemas import RegistrationItem, RegistrationsPage, StatsResponse

router = APIRouter(tags=["volunteer"])


@router.get("/registrations", response_model=RegistrationsPage, summary="List all registrations (volunteers only)")
def list_registrations(
    status: TicketStatus | None = Query(None, description="Optional filter by ticket status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    _volunteer: User = Depends(require_role(Role.volunteer)),
    db: Session = Depends(get_db),
) -> RegistrationsPage:
    count_stmt = select(func.count(Ticket.id))
    list_stmt = select(Ticket).options(joinedload(Ticket.user)).order_by(Ticket.id)
    if status is not None:
        count_stmt = count_stmt.where(Ticket.status == status)
        list_stmt = list_stmt.where(Ticket.status == status)

    total = db.scalar(count_stmt) or 0
    rows = db.scalars(list_stmt.offset((page - 1) * page_size).limit(page_size)).all()

    items = [
        RegistrationItem(
            user_id=t.user_id,
            name=t.user.name,
            email=t.user.email,
            ticket_id=t.id,
            ticket_status=t.status,
            registered_at=t.created_at,
            checked_in_at=t.checked_in_at,
        )
        for t in rows
    ]
    return RegistrationsPage(items=items, total=total, page=page, page_size=page_size)


@router.get("/stats", response_model=StatsResponse, summary="Event registration stats (volunteers only)")
def stats(
    _volunteer: User = Depends(require_role(Role.volunteer)),
    db: Session = Depends(get_db),
) -> StatsResponse:
    total = db.scalar(select(func.count(Ticket.id))) or 0
    checked_in = db.scalar(
        select(func.count(Ticket.id)).where(Ticket.status == TicketStatus.checked_in)
    ) or 0
    seats = db.get(EventSeats, 1)
    sold = seats.sold if seats else 0
    return StatsResponse(
        event=settings.event_name,
        capacity=settings.capacity,
        total_registered=total,
        paid=sold,
        checked_in=checked_in,
        remaining=max(settings.capacity - sold, 0),
    )
