"""Health check and generic error-shape behaviour."""


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_unknown_route_uses_error_envelope(client):
    resp = client.get("/this/does/not/exist")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"


def test_request_id_header_present(client):
    resp = client.get("/health")
    assert resp.headers.get("X-Request-ID")
