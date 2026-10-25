from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_is_sandboxed():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["safety_mode"] == "synthetic-sandbox-only"

def test_network_has_seven_hosts_and_required_edges():
    response = client.get("/api/network")
    assert response.status_code == 200
    body = response.json()
    assert len(body["nodes"]) == 7
    edges = {(e["source"], e["target"]) for e in body["edges"]}
    assert ("web-01", "ws-01") in edges
    assert ("jmp-01", "db-01") in edges
    assert ("fs-01", "bkp-01") in edges

def test_unknown_scenario_is_rejected():
    response = client.post("/api/scenarios/not-real/run")
    assert response.status_code == 404
