"""Race-condition tests: fire simultaneous requests and assert exactly-one-winner.

A `threading.Barrier` releases all worker threads at the same instant to maximise
overlap, so these genuinely exercise the atomic SQL paths (not just rapid succession).
"""
import threading
from concurrent.futures import ThreadPoolExecutor

from app.config import settings
from app.services.payments import compute_signature
from tests.utils import pay, student_headers, ticket_code, volunteer_headers


def _fire(n, fn):
    barrier = threading.Barrier(n)

    def worker(i):
        barrier.wait()  # all threads block here, then go together
        return fn(i)

    with ThreadPoolExecutor(max_workers=n) as pool:
        return list(pool.map(worker, range(n)))


def test_concurrent_duplicate_registration_creates_exactly_one_user(client):
    n = 8

    def register(_i):
        return client.post(
            "/auth/register",
            json={"name": "Race", "email": "race@rvce.edu", "password": "password123"},
        ).status_code

    codes = _fire(n, register)
    assert codes.count(201) == 1
    assert codes.count(409) == n - 1

    vol = volunteer_headers(client)
    assert client.get("/registrations", headers=vol).json()["total"] == 1


def test_concurrent_double_checkin_admits_once(client):
    headers = student_headers(client, email="once@rvce.edu")
    pay(client, headers)
    code = ticket_code(client, headers)
    vol = volunteer_headers(client)
    n = 6

    def do_checkin(_i):
        return client.post("/checkin", headers=vol, json={"ticket_code": code}).status_code

    codes = _fire(n, do_checkin)
    assert codes.count(200) == 1
    assert codes.count(409) == n - 1


def test_concurrent_last_seat_is_not_oversold(client, monkeypatch):
    monkeypatch.setattr(settings, "capacity", 1)

    a = student_headers(client, email="a@rvce.edu")
    b = student_headers(client, email="b@rvce.edu")
    orders = [
        client.post("/payments/order", headers=a).json()["order_id"],
        client.post("/payments/order", headers=b).json()["order_id"],
    ]

    def confirm(i):
        oid = orders[i]
        sig = compute_signature(oid, "paid")
        return client.post(
            "/payments/webhook", json={"order_id": oid, "status": "paid", "signature": sig}
        ).status_code

    codes = _fire(2, confirm)
    assert codes.count(200) == 1
    assert codes.count(409) == 1

    vol = volunteer_headers(client)
    assert client.get("/stats", headers=vol).json()["paid"] == 1
