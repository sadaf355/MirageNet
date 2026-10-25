import pytest
from app.database import SessionLocal
from app.models import Node, Decoy, Event, Alert, Session as ActorSession
from app.services.sensor_pipeline.score import score_event
from app.services.sensor_pipeline.sensors import extract_credentials, match_credential, edge_evidence
from app.services.sensor_pipeline.alert import create_alert, maybe_rotate
from app.services.sensor_pipeline.correlate import correlate_session
from app.services.sensor_pipeline.record import record_event, BENIGN_ACTORS
from datetime import datetime, timezone


def test_score_event_calculation():
    """Unit test score_event logic for malicious vs benign actors."""
    decoy = Decoy(
        id="d-test-score",
        name="Test Decoy",
        decoy_type="credential_note",
        host_id="ws-01",
        token="tok-score-test",
        enticement_score=0.9,
    )
    # Malicious actor with credential used
    res = score_event(
        decoy=decoy,
        decoy_sensitive=True,
        is_new_actor=True,
        credential_used=True,
        auth_event=True,
        breadcrumb_step=1,
        prior_chain_steps=set(),
        chain_id=None,
        benign=False,
    )
    assert res["D"] == 0.9
    assert res["U"] == 1.0
    assert res["confidence"] >= 0.70
    assert res["severity"] == "high"

    # Benign actor discount
    res_benign = score_event(
        decoy=decoy,
        decoy_sensitive=True,
        is_new_actor=False,
        credential_used=False,
        auth_event=False,
        breadcrumb_step=0,
        prior_chain_steps=set(),
        chain_id=None,
        benign=True,
    )
    assert res_benign["benign_adjustment"] < 0
    assert res_benign["confidence"] <= 0.49
    assert res_benign["severity"] == "low"


def test_sensors_credential_extractor():
    """Unit test regex and CSV credential extraction from decoy notes."""
    # Note with Key-Value
    d1 = Decoy(
        id="d1", name="note.txt", decoy_type="credential_note", host_id="ws-01", token="t1",
        content={"body": "Server: WEB-01\nUsername: test_admin\nPassword: SecretPassword#99"}
    )
    creds1 = extract_credentials(d1)
    assert len(creds1) == 1
    assert creds1[0] == ("test_admin", "SecretPassword#99")

    # Note with CSV
    d2 = Decoy(
        id="d2", name="creds.csv", decoy_type="credential_note", host_id="ws-01", token="t2",
        content={"body": "URL,Username,Password\nhttps://portal.example.invalid,svc_ops,OpsPass!123"}
    )
    creds2 = extract_credentials(d2)
    assert ("svc_ops", "OpsPass!123") in creds2


def test_edge_evidence_helper():
    """Unit test edge_evidence generation for lateral hops."""
    ev = edge_evidence({"observed_transition": True, "source_host": "WS-01"}, "evt-123", "JMP-01")
    assert len(ev) == 1
    assert ev[0]["source"] == "ws-01"
    assert ev[0]["target"] == "jmp-01"
    assert ev[0]["edge_type"] == "observed"

    # Empty when no transition
    ev_empty = edge_evidence({}, "evt-124", "WEB-01")
    assert ev_empty == []


def test_correlate_session_pipeline():
    """Unit test correlate_session stitches into an actor session."""
    db = SessionLocal()
    try:
        session, is_new, stitched = correlate_session(
            db=db,
            actor_id="test-correlate-actor",
            now=datetime.now(timezone.utc),
            token="test-token-correlate",
            credential_signal=False,
        )
        assert session is not None
        assert session.actor_id == "test-correlate-actor"
    finally:
        db.close()


@pytest.mark.anyio
async def test_record_event_full_pipeline():
    """Integration test record_event writes Event, ActorSession, and creates Alert."""
    db = SessionLocal()
    try:
        host = db.query(Node).first()
        if not host:
            host = Node(id="ws-01", hostname="WS-01", role="workstation", zone="corp")
            db.merge(host)
            db.commit()

        res = await record_event(
            event_type="file_read",
            actor_id="pipeline-test-actor",
            host_id=host.id,
            decoy_id=None,
            token=None,
            action="read_synthetic_evidence",
            credential_used=False,
            breadcrumb_step=1,
            benign=False,
            metadata={"source": "test_pipeline", "force_alert": True},
            simulated_timestamp=None,
            db=db,
            decoy_sensitive=True,
            auth_event=False,
        )
        assert "event" in res
        assert res["event"]["actor_id"] == "pipeline-test-actor"
        assert res["event"]["evidence"]["action"] == "read_synthetic_evidence"
        assert "alert" in res
        assert res["alert"] is not None
    finally:
        db.close()
