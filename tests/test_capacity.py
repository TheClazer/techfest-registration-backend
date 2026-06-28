"""Capacity / sold-out enforcement."""
from app.config import settings
from app.services.payments import compute_signature
from tests.utils import student_headers, volunteer_headers


def _confirm(client, headers):
    order_id = client.post("/payments/order", headers=headers).json()["order_id"]
    sig = compute_signature(order_id, "paid")
    return client.post("/payments/webhook", json={"order_id": order_id, "status": "paid", "signature": sig})


def test_capacity_prevents_oversell(client, monkeypatch):
    monkeypatch.setattr(settings, "capacity", 1)

    first = student_headers(client, email="first@rvce.edu")
    second = student_headers(client, email="second@rvce.edu")

    r1 = _confirm(client, first)
    assert r1.status_code == 200
    assert r1.json()["ticket_status"] == "confirmed"

    r2 = _confirm(client, second)
    assert r2.status_code == 409
    assert r2.json()["error"]["code"] == "sold_out"

    vol = volunteer_headers(client)
    stats = client.get("/stats", headers=vol).json()
    assert stats["paid"] == 1
    assert stats["remaining"] == 0
