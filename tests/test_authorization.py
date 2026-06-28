"""Role-based access control on volunteer-only endpoints."""
from tests.utils import student_headers, volunteer_headers


def test_student_cannot_list_registrations(client):
    headers = student_headers(client)
    assert client.get("/registrations", headers=headers).status_code == 403


def test_student_cannot_view_stats(client):
    headers = student_headers(client)
    assert client.get("/stats", headers=headers).status_code == 403


def test_unauthenticated_cannot_list_registrations(client):
    assert client.get("/registrations").status_code == 401


def test_volunteer_can_list_registrations_and_stats(client):
    student_headers(client, email="a@rvce.edu")
    student_headers(client, email="b@rvce.edu")
    vol = volunteer_headers(client)

    regs = client.get("/registrations", headers=vol)
    assert regs.status_code == 200
    assert regs.json()["total"] == 2

    stats = client.get("/stats", headers=vol)
    assert stats.status_code == 200
    assert stats.json()["total_registered"] == 2


def test_registrations_status_filter(client):
    paid_student = student_headers(client, email="paid@rvce.edu")
    from tests.utils import pay
    pay(client, paid_student)
    student_headers(client, email="pending@rvce.edu")
    vol = volunteer_headers(client)

    confirmed = client.get("/registrations?status=confirmed", headers=vol).json()
    assert confirmed["total"] == 1
    assert confirmed["items"][0]["ticket_status"] == "confirmed"
