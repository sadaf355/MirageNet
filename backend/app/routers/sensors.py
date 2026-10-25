from datetime import datetime, timedelta, timezone
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Alert, Decoy, Event, Node, Session as ActorSession
from app.services.scoring import confidence_score, severity_for
from app.services.sensor_pipeline.correlate import correlate_session
from app.services.sensor_pipeline.score import score_event
from app.services.sensor_pipeline.incident import attach_event_to_incident
from app.services.sensor_pipeline.sensors import edge_evidence
from app.services.stream import alert_stream

router = APIRouter(tags=["synthetic sensors"])
BENIGN_ACTORS = {"backup-agent", "health-check", "scanner-benign"}

class SensorPayload(BaseModel):
    actor_id: str = Field(default="simulated-intruder", min_length=1, max_length=80)
    host_id: str = Field(min_length=1, max_length=32)
    decoy_id: str | None = None
    token: str | None = None
    action: str = Field(default="read", max_length=64)
    credential_used: bool = False
    breadcrumb_step: int = Field(default=1, ge=1, le=3)
    benign: bool = False
    metadata: dict = Field(default_factory=dict)
    simulated_timestamp: datetime | None = None

class TouchPayload(BaseModel):
    decoy_id: str
    actor_id: str = "simulated-intruder"
    action: str = "read"
    credential_used: bool = False
    breadcrumb_step: int = Field(default=1, ge=1, le=3)
    benign: bool = False
    simulated_timestamp: datetime | None = None

@router.post("/api/sensor/file")
async def file_sensor(payload: SensorPayload, db: Session = Depends(get_db)):
    return await _record("file_read", payload, db, decoy_sensitive=True)

@router.post("/api/sensor/auth")
async def auth_sensor(payload: SensorPayload, db: Session = Depends(get_db)):
    return await _record("auth_attempt", payload, db, decoy_sensitive=True, auth_event=True)

@router.post("/api/sensor/endpoint")
async def endpoint_sensor(payload: SensorPayload, db: Session = Depends(get_db)):
    return await _record("endpoint_activity", payload, db, decoy_sensitive=bool(payload.decoy_id or payload.token))

@router.post("/api/sensor/touch")
async def simulate_touch(payload: TouchPayload, db: Session = Depends(get_db)):
    decoy = db.get(Decoy, payload.decoy_id)
    if decoy is None:
        raise HTTPException(status_code=404, detail="Synthetic decoy not found")
    if decoy.status != "deployed":
        raise HTTPException(status_code=409, detail=f"Decoy must be deployed before touch (status={decoy.status})")
    sensor_payload = SensorPayload(actor_id=payload.actor_id, host_id=decoy.host_id,
        decoy_id=decoy.id, token=decoy.token, action=payload.action,
        credential_used=payload.credential_used, breadcrumb_step=payload.breadcrumb_step,
        benign=payload.benign, simulated_timestamp=payload.simulated_timestamp, metadata={"decoy_name": decoy.name, "decoy_type": decoy.decoy_type})
    return await _record("file_read", sensor_payload, db, decoy_sensitive=True,
                         auth_event=payload.credential_used)

@router.get("/api/events")
def list_events(limit: int = 50, db: Session = Depends(get_db)):
    rows = db.query(Event).order_by(Event.timestamp.desc()).limit(max(1, min(limit, 200))).all()
    return [{"id": e.id, "event_type": e.event_type, "host_id": e.host_id, "actor_id": e.actor_id,
             "timestamp": e.timestamp.isoformat(), "evidence": e.evidence} for e in rows]

async def _record(event_type: str, payload: SensorPayload, db: Session,
                  decoy_sensitive: bool, auth_event: bool = False) -> dict:
    host = db.get(Node, payload.host_id)
    if host is None:
        raise HTTPException(status_code=404, detail="Host is not part of the synthetic network")
    decoy = db.get(Decoy, payload.decoy_id) if payload.decoy_id else None
    token_reuse = False
    if payload.token and not decoy:
        decoy = db.query(Decoy).filter(Decoy.token == payload.token).first()
        token_reuse = bool(decoy and decoy.host_id != payload.host_id)
    if payload.decoy_id and decoy is None:
        raise HTTPException(status_code=404, detail="Synthetic decoy not found")
    if decoy and decoy.host_id != payload.host_id and payload.token == decoy.token:
        token_reuse = True
    if decoy and payload.token and payload.token != decoy.token:
        raise HTTPException(status_code=400, detail="Tracking token does not match the selected decoy")
    if token_reuse:
        payload.metadata = {**payload.metadata, "token_reuse_detected": True, "original_decoy_host": decoy.host_id, "original_decoy_id": decoy.id}
    now = payload.simulated_timestamp or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    actor_session, is_new_actor, stitched_by_credential = correlate_session(
        db, payload.actor_id, now, token=payload.token,
        credential_signal=bool(payload.credential_used or auth_event))

    touched_tokens = set()
    for ev in db.query(Event).filter(Event.actor_id == payload.actor_id).all():
        token = (ev.evidence or {}).get("token")
        if token:
            touched_tokens.add(token)
    if decoy:
        touched_tokens.add(decoy.token)
    breadcrumb = (decoy.content or {}).get("breadcrumb") if decoy else None
    chain_id = breadcrumb.get("chain_id") if isinstance(breadcrumb, dict) else None
    prior_chain_steps = set()
    if chain_id:
        for prior_event in db.query(Event).filter(Event.actor_id == payload.actor_id).all():
            prior_evidence = prior_event.evidence or {}
            if prior_evidence.get("breadcrumb_chain_id") == chain_id:
                prior_chain_steps.add(prior_evidence.get("breadcrumb_step"))
    benign = payload.benign or payload.actor_id in BENIGN_ACTORS
    score = score_event(decoy, decoy_sensitive, is_new_actor, payload.credential_used,
                        auth_event, payload.breadcrumb_step, prior_chain_steps, chain_id, benign)
    D, N, U, P = score["D"], score["N"], score["U"], score["P"]
    confidence, severity = score["confidence"], score["severity"]
    event_id = f"evt-{uuid4().hex[:16]}"
    evidence = {"actor_id": payload.actor_id, "action": payload.action, "decoy_id": decoy.id if decoy else None,
                "decoy_name": decoy.name if decoy else None, "decoy_type": decoy.decoy_type if decoy else None, "token": decoy.token if decoy else payload.token,
                "decoy_sensitivity": round(D, 4), "actor_novelty": round(N, 4),
                "credential_evidence": round(U, 4), "breadcrumb_progress": round(P, 4), "breadcrumb_chain_id": chain_id, "breadcrumb_step": breadcrumb.get("step") if isinstance(breadcrumb, dict) else payload.breadcrumb_step,
                "benign_allowlisted": benign, "score_breakdown": {k: score[k] for k in ("D","N","U","P","raw_weighted_score","benign_adjustment","confidence")},
                "why_fired": ("Credential-use evidence detected" if U else "Synthetic decoy interaction detected") + (f"; breadcrumb progress {P:.2f}" if P else "") + ("; benign allow-list adjustment applied" if benign else ""),
                "recommended_next_action": "Review this session timeline and validate the synthetic credential-use evidence; do not take real-world action.", "token_reuse_detected": token_reuse, "original_decoy_host": decoy.host_id if token_reuse and decoy else None, "score_formula": "0.35D + 0.25N + 0.20U + 0.20P - 0.40Ib",
                "metadata": payload.metadata, "session_id": actor_session.id, "session_stitched_by_credential_or_token": stitched_by_credential, "simulated": True,
                "scenario": payload.metadata.get("scenario"), "run_id": payload.metadata.get("run_id"),
                "step_index": payload.metadata.get("step_index"), "ground_truth_label": payload.metadata.get("ground_truth_label")}
    prior_actor_event = db.query(Event).filter(Event.actor_id == payload.actor_id).order_by(Event.timestamp.desc()).first()
    if prior_actor_event and prior_actor_event.host_id and prior_actor_event.host_id != payload.host_id:
        from app.services.network_service import TOPOLOGY_EDGES
        import networkx as nx
        graph = nx.Graph(); graph.add_edges_from(TOPOLOGY_EDGES)
        try:
            path = nx.shortest_path(graph, prior_actor_event.host_id.lower(), payload.host_id.lower())
            evidence["inferred_hops"] = [{"source": a, "target": b, "edge_type": "inferred"} for a,b in zip(path, path[1:])]
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            evidence["inferred_hops"] = []
    evidence["observed_edges"] = edge_evidence(payload.metadata, event_id, payload.host_id)
    event = Event(id=event_id, event_type=event_type, host_id=payload.host_id,
                  actor_id=payload.actor_id, timestamp=now, evidence=evidence)
    db.add(event)
    actor_session.last_seen_at = now
    actor_session.confidence = max(actor_session.confidence or 0.0, confidence)
    actor_session.status = "benign-observed" if benign else ("suspicious" if confidence >= 0.5 else "observing")
    alert = None
    # Each decoy touch yields an auditable alert; generic endpoint noise is persisted as an event only.
    if payload.metadata.get("force_low_alert"):
        confidence = min(confidence, 0.49)
        severity = "low"
    if benign and decoy_sensitive:
        severity = "low"
        confidence = min(confidence, 0.49)
    evidence["score_breakdown"] = {**(evidence.get("score_breakdown") or {}), "confidence": round(confidence, 4)}
    evidence["severity"] = severity
    if decoy_sensitive and (decoy is not None or auth_event or payload.token or payload.metadata.get("force_alert")):
        if token_reuse:
            alert_title = f"Token reuse: {decoy.name}"
        elif benign:
            alert_title = f"Benign allow-listed activity: {payload.action}"
        elif decoy:
            alert_title = f"Synthetic decoy {payload.action}: {decoy.name}"
        else:
            alert_title = f"Sensor signal: {event_type}"
        alert = Alert(id=f"alr-{uuid4().hex[:16]}", title=alert_title,
            severity=severity, confidence=confidence, host_id=payload.host_id, status="open",
            timestamp=now, evidence={**evidence, "event_id": event_id})
        db.add(alert)
        db.flush()
        attach_event_to_incident(db, actor_session.id, payload.metadata.get("run_id"), event, alert, severity)
        # High-confidence non-benign touches automatically burn the old token and deploy a fresh synthetic replacement.
        if decoy is not None and decoy.status == "deployed" and confidence >= 0.80 and not benign:
            from app.services.forge import rotate_decoy, serialize_decoy
            replacement = rotate_decoy(db, decoy, commit=False)
            rotation = {"trigger": "high_confidence_touch", "threshold": 0.80,
                        "confidence": round(confidence, 4), "burned_decoy_id": decoy.id,
                        "burned_token": decoy.token, "replacement": serialize_decoy(replacement),
                        "automatic": True, "synthetic_only": True}
            evidence["auto_rotation"] = rotation
            event.evidence = {**(event.evidence or {}), "auto_rotation": rotation}
            alert.evidence = {**(alert.evidence or {}), "auto_rotation": rotation}
            # Keep the persisted incident timeline and its evidence in sync with the alert.
            incident = next((i for i in db.query(__import__("app.models", fromlist=["Incident"]).Incident).all()
                             if event.id in ((i.evidence or {}).get("event_ids", []))), None)
            if incident:
                story = dict(incident.evidence or {})
                for item in story.get("timeline", []):
                    if item.get("id") == event.id:
                        item["evidence"] = event.evidence
                incident.evidence = story
    db.commit()
    response = {"event": {"id": event.id, "event_type": event.event_type, "host_id": event.host_id,
                           "actor_id": event.actor_id, "timestamp": now.isoformat(), "evidence": evidence},
                "session": {"id": actor_session.id, "status": actor_session.status, "confidence": actor_session.confidence},
                "alert": None, "auto_rotation": evidence.get("auto_rotation")}
    if alert:
        related_incident = next((i for i in db.query(__import__("app.models", fromlist=["Incident"]).Incident).all() if event.id in ((i.evidence or {}).get("event_ids", []))), None)
        response["alert"] = {"id": alert.id, "title": alert.title, "severity": alert.severity,
            "confidence": alert.confidence, "host_id": alert.host_id, "status": alert.status,
            "timestamp": now.isoformat(), "incident_id": related_incident.id if related_incident else None, "evidence": alert.evidence}
        await alert_stream.publish({"type": "alert", "alert": response["alert"]})
    await alert_stream.publish({"type": "event", "event": response["event"]})
    return response

@router.get("/admin")
async def fake_admin_endpoint(actor_id: str = "demo-web-probe", db: Session = Depends(get_db)):
    """Fictional WEB-01 admin lure; never performs authentication or administration."""
    host = db.query(Node).filter(Node.hostname == "WEB-01").first()
    if host is None:
        raise HTTPException(status_code=404, detail="Synthetic WEB-01 host is not seeded")
    result = await _record("endpoint_activity", SensorPayload(actor_id=actor_id, host_id=host.id,
        action="open_fake_admin_endpoint", metadata={"sensor":"fake_admin_endpoint","scenario":"web-lure-demo","force_alert":True}), db, decoy_sensitive=True)
    return {"mode":"synthetic-sandbox-only","endpoint":"/admin","message":"Fictional admin portal lure — no login or admin action is available.","telemetry":result}

@router.get("/backup.zip")
async def fake_backup_endpoint(actor_id: str = "demo-web-probe", db: Session = Depends(get_db)):
    """Fictional backup lure; returns metadata only, not an archive or real data."""
    host = db.query(Node).filter(Node.hostname == "WEB-01").first()
    if host is None:
        raise HTTPException(status_code=404, detail="Synthetic WEB-01 host is not seeded")
    result = await _record("endpoint_activity", SensorPayload(actor_id=actor_id, host_id=host.id,
        action="request_fake_backup_archive", metadata={"sensor":"fake_backup_endpoint","scenario":"web-lure-demo","force_alert":True}), db, decoy_sensitive=True)
    return {"mode":"synthetic-sandbox-only","endpoint":"/backup.zip","artifact":{"filename":"backup.zip","content":"[FICTIONAL BACKUP METADATA ONLY]","bytes":0},"telemetry":result}
