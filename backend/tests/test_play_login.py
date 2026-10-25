import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models import Decoy, Alert, Event
from app.services.sensor_pipeline.sensors import extract_credentials

client = TestClient(app)


def _get_or_create_honey_credential_decoy(db):
    for d in db.query(Decoy).filter(Decoy.status == "deployed", Decoy.decoy_type == "credential_note").all():
        creds = extract_credentials(d)
        if creds:
            return d, creds[0][0], creds[0][1]

    decoy = Decoy(
        id="test-honey-note-play-01",
        name="Test Play Admin Credentials Note",
        decoy_type="credential_note",
        status="deployed",
        host_id="ws-01",
        content={"username": "svc_secops_adm", "password": "Winter2024!TempPass#44"},
        token="test-honey-token-play-xyz",
    )
    db.merge(decoy)
    db.commit()
    return decoy, "svc_secops_adm", "Winter2024!TempPass#44"


def test_play_login_matching_credential():
    """POST /api/play/login with decoy credentials returns access_granted, dashboard, and alert."""
    db = SessionLocal()
    try:
        decoy, username, password = _get_or_create_honey_credential_decoy(db)

        resp = client.post(
            "/api/play/login",
            json={
                "username": username,
                "password": password,
                "actor_id": "play-adversary-1",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["mode"] == "honey-credential-match"
        assert data["result"] == "access_granted_to_fictional_dashboard"
        assert data["alert"] is not None
        assert data["alert"]["severity"] == "high"
        assert "fictional_dashboard" in data
        assert len(data["fictional_dashboard"]["hosts"]) > 0
    finally:
        db.close()


def test_play_login_invalid_credential():
    """POST /api/play/login with invalid credentials returns access_denied."""
    resp = client.post(
        "/api/play/login",
        json={
            "username": "fictional_intruder",
            "password": "wrong_password_999",
            "actor_id": "play-adversary-2",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["mode"] == "honey-credential-miss"
    assert data["result"] == "access_denied"
    assert data["event"]["evidence"]["action"] == "failed_honey_login"
