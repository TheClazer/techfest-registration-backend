"""Shared helpers for tests."""
from app.database import SessionLocal
from app.models import Role, User
from app.security import hash_password
from app.services.payments import compute_signature


def register(client, email="student@rvce.edu", password="password123", name="Student"):
    return client.post("/auth/register", json={"name": name, "email": email, "password": password})


def student_headers(client, email="student@rvce.edu", password="password123", name="Student"):
    resp = register(client, email=email, password=password, name=name)
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def pay(client, headers):
    """Create an order and confirm it via a correctly-signed webhook."""
    order_id = client.post("/payments/order", headers=headers).json()["order_id"]
    sig = compute_signature(order_id, "paid")
    client.post("/payments/webhook", json={"order_id": order_id, "status": "paid", "signature": sig})
    return order_id


def ticket_code(client, headers):
    return client.get("/tickets/me", headers=headers).json()["ticket_code"]


def volunteer_headers(client, email="volunteer@rvce.edu", password="password123"):
    with SessionLocal() as db:
        db.add(User(name="Vol", email=email, password_hash=hash_password(password), role=Role.volunteer))
        db.commit()
    token = client.post("/auth/login", json={"email": email, "password": password}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
