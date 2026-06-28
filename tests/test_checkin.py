"""Gate check-in, including the deliberate edge cases."""
from app.security import sign_ticket
from app.database import SessionLocal
from app.models import Ticket, User
from tests.utils import pay, student_headers, ticket_code, volunteer_headers


def _signed_code_for(email):
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == email).first()
        ticket = db.query(Ticket).filter(Ticket.user_id == user.id).first()
        return sign_ticket(ticket.ticket_uuid)


def test_checkin_requires_auth(client):
    assert client.post("/checkin", json={"ticket_code": "x"}).status_code == 401


def test_student_cannot_check_in(client):
    headers = student_headers(client)
    pay(client, headers)
    code = ticket_code(client, headers)
    resp = client.post("/checkin", headers=headers, json={"ticket_code": code})
    assert resp.status_code == 403


def test_forged_ticket_rejected(client):
    vol = volunteer_headers(client)
    resp = client.post("/checkin", headers=vol, json={"ticket_code": "forged.invalid.token"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_ticket"


def test_unpaid_ticket_cannot_check_in(client):
    student_headers(client, email="unpaid@rvce.edu")
    vol = volunteer_headers(client)
    code = _signed_code_for("unpaid@rvce.edu")
    resp = client.post("/checkin", headers=vol, json={"ticket_code": code})
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "not_confirmed"


def test_successful_checkin(client):
    headers = student_headers(client, email="go@rvce.edu")
    pay(client, headers)
    code = ticket_code(client, headers)
    vol = volunteer_headers(client)
    resp = client.post("/checkin", headers=vol, json={"ticket_code": code})
    assert resp.status_code == 200
    assert resp.json()["status"] == "checked_in"
    assert resp.json()["student"]["email"] == "go@rvce.edu"


def test_double_checkin_rejected(client):
    headers = student_headers(client, email="go@rvce.edu")
    pay(client, headers)
    code = ticket_code(client, headers)
    vol = volunteer_headers(client)
    client.post("/checkin", headers=vol, json={"ticket_code": code})
    resp = client.post("/checkin", headers=vol, json={"ticket_code": code})
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "already_checked_in"
