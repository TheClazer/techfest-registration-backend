"""Additive async registration path: queue + worker pool + status polling."""
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from tests.utils import student_headers, volunteer_headers


def _poll(client, job_id, timeout=10.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        body = client.get(f"/auth/register/status/{job_id}").json()
        if body["status"] in ("completed", "failed"):
            return body
        time.sleep(0.05)
    raise AssertionError("job did not finish in time")


def test_async_registration_accepts_then_completes(client):
    resp = client.post(
        "/auth/register-async",
        json={"name": "Async", "email": "async@rvce.edu", "password": "password123"},
    )
    assert resp.status_code == 202
    job_id = resp.json()["job_id"]

    done = _poll(client, job_id)
    assert done["status"] == "completed"
    assert done["result"]["user"]["email"] == "async@rvce.edu"
    assert done["result"]["ticket"]["status"] == "pending_payment"
    assert done["result"]["access_token"]


def test_async_registration_rejects_known_duplicate(client):
    student_headers(client, email="dupe@rvce.edu")  # create via the sync path first
    resp = client.post(
        "/auth/register-async",
        json={"name": "X", "email": "dupe@rvce.edu", "password": "password123"},
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "email_taken"


def test_async_status_unknown_job_404(client):
    assert client.get("/auth/register/status/does-not-exist").status_code == 404


def test_async_concurrent_same_email_creates_one_user(client):
    barrier = threading.Barrier(6)

    def go(_i):
        barrier.wait()
        return client.post(
            "/auth/register-async",
            json={"name": "Con", "email": "con@rvce.edu", "password": "password123"},
        ).status_code

    with ThreadPoolExecutor(max_workers=6) as pool:
        codes = list(pool.map(go, range(6)))

    assert all(c in (202, 409) for c in codes)  # accepted or de-duped, never a crash

    vol = volunteer_headers(client)
    for _ in range(40):
        items = client.get("/registrations", headers=vol).json()["items"]
        if any(i["email"] == "con@rvce.edu" for i in items):
            break
        time.sleep(0.05)

    items = client.get("/registrations", headers=vol).json()["items"]
    assert len([i for i in items if i["email"] == "con@rvce.edu"]) == 1
