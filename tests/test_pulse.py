from fastapi.testclient import TestClient

from app.main import app


def test_pulse_default_session():
    client = TestClient(app)
    r = client.get("/v1/pulse")
    assert r.status_code == 200
    body = r.json()
    assert body["session"] == "us"
    assert body["regime"] in {"risk_on", "risk_off", "mixed", "consolidation"}
    assert -1.0 <= body["score"] <= 1.0
    assert isinstance(body["drivers"], list) and body["drivers"]
    assert isinstance(body["confirmations"], list)
    assert isinstance(body["invalidations"], list) and body["invalidations"]


def test_pulse_rejects_bad_session():
    client = TestClient(app)
    r = client.get("/v1/pulse", params={"session": "lunar"})
    assert r.status_code == 422


def test_pulse_is_deterministic_for_date():
    client = TestClient(app)
    a = client.get("/v1/pulse", params={"session": "us", "on": "2026-09-14"}).json()
    b = client.get("/v1/pulse", params={"session": "us", "on": "2026-09-14"}).json()
    assert a == b
