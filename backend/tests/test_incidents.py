from uuid import uuid4
from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models import Event, Node

client = TestClient(app)

def test_reconstruct_incident_and_reports():
    with SessionLocal() as db:
        host = db.query(Node).first()
        event_id = f"evt-{uuid4().hex[:14]}"
        actor_id = f"phase4-{uuid4().hex[:8]}"
        db.add(Event(id=event_id, event_type="file_read", host_id=host.id,
                     actor_id=actor_id, evidence={"action":"read", "decoy_name":"finance-credentials.txt",
                     "decoy_type":"credential_note", "credential_evidence":1.0, "simulated":True}))
        db.commit()
    response = client.post("/api/incidents/reconstruct", json={"actor_id": actor_id})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["evidence"]["event_count"] == 1
    assert body["evidence"]["timeline"][0]["id"] == event_id
    assert any(t["technique_id"] == "T1552.001" for t in body["evidence"]["attack_techniques"])
    assert client.get(f"/api/incidents/{body['id']}").status_code == 200
    markdown = client.get(f"/api/incidents/{body['id']}/report?format=md")
    assert markdown.status_code == 200
    assert "Evidence timeline" in markdown.text
    json_report = client.get(f"/api/incidents/{body['id']}/report?format=json")
    assert json_report.status_code == 200
    assert json_report.json()["id"] == body["id"]

def test_reconstruct_requires_events():
    response = client.post("/api/incidents/reconstruct", json={"actor_id": f"missing-{uuid4().hex}"})
    assert response.status_code == 404
