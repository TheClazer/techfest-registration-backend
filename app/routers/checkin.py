"""Gate check-in endpoint (volunteers only)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_role
from ..models import Role, User
from ..schemas import CheckedInStudent, CheckinRequest, CheckinResponse
from ..services.checkin import check_in

router = APIRouter(tags=["check-in"])


@router.post("/checkin", response_model=CheckinResponse, summary="Scan a ticket QR and check the student in")
def checkin(
    payload: CheckinRequest,
    volunteer: User = Depends(require_role(Role.volunteer)),
    db: Session = Depends(get_db),
) -> CheckinResponse:
    ticket, student = check_in(db, ticket_code=payload.ticket_code, volunteer=volunteer)
    return CheckinResponse(
        ticket_id=ticket.id,
        status=ticket.status,
        student=CheckedInStudent(id=student.id, name=student.name, email=student.email),
        checked_in_at=ticket.checked_in_at,
    )
