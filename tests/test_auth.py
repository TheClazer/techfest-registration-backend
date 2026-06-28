"""Authentication: registration and login, including edge cases."""
from tests.utils import register


def test_register_success_creates_pending_ticket(client):
    resp = register(client, email="asha@rvce.edu")
    assert resp.status_code == 201
    body = resp.json()
    assert body["user"]["email"] == "asha@rvce.edu"
    assert body["user"]["role"] == "student"
    assert body["ticket"]["status"] == "pending_payment"
    assert body["access_token"]


def test_register_duplicate_email_is_rejected(client):
    register(client, email="dup@rvce.edu")
    resp = register(client, email="dup@rvce.edu")
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "email_taken"


def test_register_duplicate_email_is_case_insensitive(client):
    register(client, email="Case@RVCE.edu")
    resp = register(client, email="case@rvce.edu")
    assert resp.status_code == 409


def test_register_invalid_input_returns_422(client):
    assert client.post("/auth/register", json={"name": "X", "email": "not-an-email", "password": "password123"}).status_code == 422
    assert client.post("/auth/register", json={"name": "X", "email": "x@rvce.edu", "password": "short"}).status_code == 422
    assert client.post("/auth/register", json={"email": "x@rvce.edu", "password": "password123"}).status_code == 422


def test_login_success(client):
    register(client, email="login@rvce.edu", password="password123")
    resp = client.post("/auth/login", json={"email": "login@rvce.edu", "password": "password123"})
    assert resp.status_code == 200
    assert resp.json()["access_token"]


def test_login_wrong_password_is_generic_401(client):
    register(client, email="login@rvce.edu", password="password123")
    resp = client.post("/auth/login", json={"email": "login@rvce.edu", "password": "wrongpass"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "invalid_credentials"


def test_login_unknown_email_is_generic_401(client):
    resp = client.post("/auth/login", json={"email": "nobody@rvce.edu", "password": "password123"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "invalid_credentials"
