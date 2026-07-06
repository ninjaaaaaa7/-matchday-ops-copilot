"""Integration tests for the FastAPI endpoints using the test client."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_ok():
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    # ai_enabled is a boolean regardless of whether a key is configured.
    assert isinstance(body["ai_enabled"], bool)


def test_sample_is_valid():
    response = client.get("/api/sample")
    assert response.status_code == 200
    body = response.json()
    assert body["stadium"]
    assert len(body["zones"]) >= 1


def test_assess_returns_ranked_zones():
    state = client.get("/api/sample").json()
    response = client.post("/api/assess", json=state)
    assert response.status_code == 200
    body = response.json()
    scores = [z["risk_score"] for z in body["zones"]]
    # Zones must be sorted from highest to lowest risk.
    assert scores == sorted(scores, reverse=True)
    assert body["overall_risk_level"] in {"LOW", "MODERATE", "HIGH", "CRITICAL"}


def test_copilot_demo_mode_answers():
    state = client.get("/api/sample").json()
    payload = {"state": state, "question": "What should I prioritise?", "language": "English"}
    response = client.post("/api/copilot", json=payload)
    assert response.status_code == 200
    body = response.json()
    # Without an API key the service answers in demo mode, but still answers.
    assert body["mode"] in {"demo", "live"}
    assert len(body["answer"]) > 0
    assert body["assessment"]["zones"]


def test_assess_rejects_invalid_payload():
    # capacity must be > 0; an invalid body should be rejected with 422.
    bad_state = {
        "stadium": "X",
        "match": {"fixture": "F", "minutes_to_kickoff": 10},
        "zones": [{"id": "z", "name": "Z", "capacity": 0, "occupancy": 5}],
    }
    response = client.post("/api/assess", json=bad_state)
    assert response.status_code == 422


def test_copilot_rejects_empty_question():
    state = client.get("/api/sample").json()
    payload = {"state": state, "question": "", "language": "English"}
    response = client.post("/api/copilot", json=payload)
    assert response.status_code == 422
