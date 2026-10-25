"""sensor_pipeline/alert.py — Alert creation and decoy-rotation logic.

Extracted from sensors.py. No FastAPI imports.
"""
from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy.orm import Session as DBSession

from app.models import Alert, Decoy, Event, Incident
from app.services.sensor_pipeline.incident import attach_event_to_incident


def create_alert(
    *,
    db: DBSession,
    event: Event,
    event_id: str,
    evidence: dict,
    actor_id: str,
    actor_session,
    host_id: str,
    now: datetime,
    confidence: float,
    severity: str,
    action: str,
    decoy: Decoy | None,
    token_reuse: bool,
    is_benign: bool,
    run_id: str | None,
) -> tuple[Alert, dict | None]:
    """Create an alert, attach to incident, maybe rotate decoy. Returns (alert, rotation_dict | None)."""
    if token_reuse:
        alert_title = f"Token reuse: {decoy.name}"
    elif is_benign:
        alert_title = f"Benign allow-listed activity: {action}"
    elif decoy:
        alert_title = f"Synthetic decoy {action}: {decoy.name}"
    else:
        alert_title = f"Sensor signal: {event.event_type}"

    alert = Alert(
        id=f"alr-{uuid4().hex[:16]}",
        title=alert_title,
        severity=severity,
        confidence=confidence,
        host_id=host_id,
        status="open",
        timestamp=now,
        evidence={**evidence, "event_id": event_id},
    )
    db.add(alert)
    db.flush()
    attach_event_to_incident(db, actor_session.id, run_id, event, alert, severity)

    rotation = None
    if decoy is not None and decoy.status == "deployed" and confidence >= 0.80 and not is_benign:
        rotation = maybe_rotate(db, decoy, event, alert, confidence)

    return alert, rotation


def maybe_rotate(
    db: DBSession,
    decoy: Decoy,
    event: Event,
    alert: Alert,
    confidence: float,
) -> dict | None:
    """Burn the touched decoy and deploy a fresh replacement. Returns rotation metadata or None."""
    from app.services.forge import rotate_decoy, serialize_decoy
    replacement = rotate_decoy(db, decoy, commit=False)
    rotation = {
        "trigger": "high_confidence_touch",
        "threshold": 0.80,
        "confidence": round(confidence, 4),
        "burned_decoy_id": decoy.id,
        "burned_token": decoy.token,
        "replacement": serialize_decoy(replacement),
        "automatic": True,
        "synthetic_only": True,
    }
    # Keep the incident timeline in sync
    incident = next(
        (i for i in db.query(Incident).all()
         if event.id in ((i.evidence or {}).get("event_ids", []))),
        None,
    )
    if incident:
        story = dict(incident.evidence or {})
        for item in story.get("timeline", []):
            if item.get("id") == event.id:
                item["evidence"] = event.evidence
        incident.evidence = story
    return rotation
