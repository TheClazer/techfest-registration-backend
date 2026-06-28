"""Payments: order creation and signed-webhook confirmation, with idempotency."""
from app.services.payments import compute_signature
from tests.utils import student_headers


def test_order_is_idempotent(client):
    headers = student_headers(client)
    first = client.post("/payments/order", headers=headers).json()
    second = client.post("/payments/order", headers=headers).json()
    assert first["order_id"] == second["order_id"]
    assert first["status"] == "created"


def test_webhook_invalid_signature_rejected(client):
    headers = student_headers(client)
    order_id = client.post("/payments/order", headers=headers).json()["order_id"]
    resp = client.post("/payments/webhook", json={"order_id": order_id, "status": "paid", "signature": "deadbeef"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_signature"


def test_webhook_confirms_ticket(client):
    headers = student_headers(client)
    order_id = client.post("/payments/order", headers=headers).json()["order_id"]
    sig = compute_signature(order_id, "paid")
    resp = client.post("/payments/webhook", json={"order_id": order_id, "status": "paid", "signature": sig})
    assert resp.status_code == 200
    assert resp.json()["payment_status"] == "paid"
    assert resp.json()["ticket_status"] == "confirmed"


def test_webhook_replay_is_idempotent(client):
    headers = student_headers(client)
    order_id = client.post("/payments/order", headers=headers).json()["order_id"]
    sig = compute_signature(order_id, "paid")
    payload = {"order_id": order_id, "status": "paid", "signature": sig}
    client.post("/payments/webhook", json=payload)
    replay = client.post("/payments/webhook", json=payload)
    assert replay.status_code == 200
    assert replay.json()["ticket_status"] == "confirmed"


def test_webhook_unknown_order_404(client):
    sig = compute_signature("order_does_not_exist", "paid")
    resp = client.post("/payments/webhook", json={"order_id": "order_does_not_exist", "status": "paid", "signature": sig})
    assert resp.status_code == 404


def test_order_after_paid_conflicts(client):
    headers = student_headers(client)
    order_id = client.post("/payments/order", headers=headers).json()["order_id"]
    sig = compute_signature(order_id, "paid")
    client.post("/payments/webhook", json={"order_id": order_id, "status": "paid", "signature": sig})
    resp = client.post("/payments/order", headers=headers)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "already_paid"
