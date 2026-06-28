"""Additional edge cases: traceability, failed-payment retry, auth header forms, pagination."""
from app.services.payments import compute_signature
from tests.utils import student_headers, volunteer_headers


def test_error_body_includes_traceable_request_id(client):
    resp = client.get("/tickets/me")  # 401
    assert resp.status_code == 401
    rid = resp.json()["error"]["request_id"]
    assert rid
    assert resp.headers.get("X-Request-ID") == rid


def test_webhook_failed_status_leaves_ticket_pending(client):
    headers = student_headers(client, email="fail@rvce.edu")
    order_id = client.post("/payments/order", headers=headers).json()["order_id"]
    sig = compute_signature(order_id, "failed")
    resp = client.post("/payments/webhook", json={"order_id": order_id, "status": "failed", "signature": sig})
    assert resp.status_code == 200
    assert resp.json()["payment_status"] == "failed"
    assert resp.json()["ticket_status"] == "pending_payment"


def test_order_can_be_retried_after_a_failed_payment(client):
    headers = student_headers(client, email="retry@rvce.edu")
    first = client.post("/payments/order", headers=headers).json()["order_id"]
    client.post("/payments/webhook", json={"order_id": first, "status": "failed", "signature": compute_signature(first, "failed")})

    retry = client.post("/payments/order", headers=headers)
    assert retry.status_code == 200
    new_order = retry.json()["order_id"]
    assert new_order != first

    ok = client.post("/payments/webhook", json={"order_id": new_order, "status": "paid", "signature": compute_signature(new_order, "paid")})
    assert ok.status_code == 200
    assert ok.json()["ticket_status"] == "confirmed"


def test_malformed_authorization_header_is_401(client):
    assert client.get("/tickets/me", headers={"Authorization": "Basic xyz"}).status_code == 401
    assert client.get("/tickets/me", headers={"Authorization": "no-scheme-token"}).status_code == 401


def test_pagination_bounds_are_validated(client):
    vol = volunteer_headers(client)
    assert client.get("/registrations?page=0", headers=vol).status_code == 422
    assert client.get("/registrations?page_size=9999", headers=vol).status_code == 422
