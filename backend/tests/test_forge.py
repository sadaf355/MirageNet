from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_forge_creates_requested_synthetic_decoys():
    response = client.post("/api/forge/run", json={"count": 10})
    assert response.status_code == 200
    body = response.json()
    assert body["created"] == 10
    assert body["source_mode"] in {"cache", "local_synthetic_fallback", "adaption_generated"}
    assert len({d["token"] for d in body["decoys"]}) == 10
    assert {d["type"] for d in body["decoys"]} == {
        "finance_hr", "credential_note", "config", "database", "api_artifact"
    }
    assert len(body["breadcrumb_chain"]["steps"]) == 3

def test_forge_rejects_count_over_limit():
    response = client.post("/api/forge/run", json={"count": 201})
    assert response.status_code == 422

def test_deploy_marks_staged_decoys_deployed():
    client.post("/api/forge/run", json={"count": 2})
    response = client.post("/api/deploy")
    assert response.status_code == 200
    assert response.json()["deployed"] >= 2
