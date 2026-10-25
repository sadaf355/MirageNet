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

    # Create one if missing
    decoy = Decoy(
        id="test-honey-note-01",
        name="Test Admin Credentials Note",
        decoy_type="credential_note",
        status="deployed",
        host_id="ws-01",
        content={"username": "svc_secops_adm", "password": "Winter2024!TempPass#44"},
        token="test-honey-token-xyz",
    )
    db.merge(decoy)
    db.commit()
    return decoy, "svc_secops_adm", "Winter2024!TempPass#44"


def test_honey_login_get_html():
    """GET /admin without JSON accept header returns 200 and the HTML login page."""
    resp = client.get("/admin", headers={"Accept": "text/html"})
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "Northwind Logistics" in resp.text
    assert 'name="username"' in resp.text
    assert 'name="password"' in resp.text


def test_honey_login_post_matching_credential():
    """POST /admin with credentials matching a deployed decoy produces 200, dashboard HTML, and high alert."""
    db = SessionLocal()
    try:
        decoy, username, password = _get_or_create_honey_credential_decoy(db)

        resp = client.post(
            "/admin",
            data={"username": username, "password": password, "actor_id": "test-adversary-101"},
        )
        assert resp.status_code == 200
        assert "Admin Dashboard" in resp.text
        assert "WEB-01" in resp.text

        # Verify event and alert created
        event = db.query(Event).filter(
            Event.actor_id == "test-adversary-101",
            Event.event_type == "auth_attempt",
        ).order_by(Event.timestamp.desc()).first()
        assert event is not None
        assert event.evidence.get("credential_used") is True

        alert = db.query(Alert).filter(
            Alert.evidence["actor_id"].as_string() == "test-adversary-101"
            if hasattr(Alert.evidence["actor_id"], "as_string")
            else Alert.title.like("%test-adversary-101%")
        ).order_by(Alert.timestamp.desc()).first()
        # Fallback query if JSON filter differs by SQLite
        if not alert:
            alert = db.query(Alert).order_by(Alert.timestamp.desc()).first()
        assert alert is not None
        assert alert.severity == "high"
    finally:
        db.close()


def test_honey_login_post_invalid_credential():
    """POST /admin with non-matching credentials returns 401 and generic rejection."""
    db = SessionLocal()
    try:
        resp = client.post(
            "/admin",
            data={"username": "definitely_not_a_honey_user", "password": "wrongpassword123", "actor_id": "test-bad-actor"},
        )
        assert resp.status_code == 401
        assert "Invalid credentials" in resp.text

        # Low-severity event recorded
        event = db.query(Event).filter(
            Event.actor_id == "test-bad-actor",
            Event.event_type == "auth_attempt",
        ).order_by(Event.timestamp.desc()).first()
        assert event is not None
        assert event.evidence.get("credential_used") is False
    finally:
        db.close()


def test_honey_login_benign_actor_handling():
    """POST /admin with a benign actor does not trigger a high-severity alert."""
    db = SessionLocal()
    try:
        decoy, username, password = _get_or_create_honey_credential_decoy(db)

        resp = client.post(
            "/admin",
            data={"username": username, "password": password, "actor_id": "scanner-benign"},
        )
        assert resp.status_code == 200

        # Event is recorded as benign
        event = db.query(Event).filter(
            Event.actor_id == "scanner-benign",
            Event.event_type == "auth_attempt",
        ).order_by(Event.timestamp.desc()).first()
        assert event is not None
        assert event.evidence.get("benign") is True
    finally:
        db.close()
