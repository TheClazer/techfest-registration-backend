"""Ticket endpoints — a student views their own ticket and QR."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import Response

from ..deps import get_current_user
from ..errors import AppError
from ..models import Ticket, TicketStatus, User
from ..qr import make_qr_png_base64, make_qr_png_bytes
from ..schemas import TicketOut
from ..security import sign_ticket

router = APIRouter(prefix="/tickets", tags=["tickets"])

_TICKET_READY = (TicketStatus.confirmed, TicketStatus.checked_in)


def _ticket_out(ticket: Ticket) -> TicketOut:
    out = TicketOut.model_validate(ticket)
    # The signed code + QR are only meaningful (and only issued) once paid/confirmed.
    if ticket.status in _TICKET_READY:
        token = sign_ticket(ticket.ticket_uuid)
        out.ticket_code = token
        out.qr_png_base64 = make_qr_png_base64(token)
    return out


@router.get("/me", response_model=TicketOut, summary="View your own ticket (and QR once confirmed)")
def my_ticket(user: User = Depends(get_current_user)) -> TicketOut:
    if user.ticket is None:
        raise AppError(404, "no_ticket", "You do not have a ticket yet.")
    return _ticket_out(user.ticket)


@router.get("/me/qr", summary="Download your ticket QR as a PNG image")
def my_ticket_qr(user: User = Depends(get_current_user)) -> Response:
    ticket = user.ticket
    if ticket is None:
        raise AppError(404, "no_ticket", "You do not have a ticket yet.")
    if ticket.status not in _TICKET_READY:
        raise AppError(
            409, "ticket_not_confirmed", "Your ticket is not confirmed yet — complete payment first."
        )
    png = make_qr_png_bytes(sign_ticket(ticket.ticket_uuid))
    return Response(content=png, media_type="image/png")
