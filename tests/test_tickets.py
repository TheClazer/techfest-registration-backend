"""Ticket viewing and QR issuance."""
from tests.utils import pay, student_headers


def test_ticket_requires_auth(client):
    assert client.get("/tickets/me").status_code == 401


def test_pending_ticket_has_no_code_or_qr(client):
    headers = student_headers(client)
    body = client.get("/tickets/me", headers=headers).json()
    assert body["status"] == "pending_payment"
    assert body["ticket_code"] is None
    assert body["qr_png_base64"] is None


def test_qr_endpoint_409_before_confirmation(client):
    headers = student_headers(client)
    resp = client.get("/tickets/me/qr", headers=headers)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "ticket_not_confirmed"


def test_confirmed_ticket_exposes_code_and_qr(client):
    headers = student_headers(client)
    pay(client, headers)
    body = client.get("/tickets/me", headers=headers).json()
    assert body["status"] == "confirmed"
    assert body["ticket_code"]
    assert body["qr_png_base64"]


def test_qr_png_after_confirmation(client):
    headers = student_headers(client)
    pay(client, headers)
    resp = client.get("/tickets/me/qr", headers=headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"
    assert resp.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_invalid_token_rejected(client):
    assert client.get("/tickets/me", headers={"Authorization": "Bearer garbage"}).status_code == 401
