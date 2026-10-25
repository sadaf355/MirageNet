"""sensor_pipeline/record.py — Core event-recording logic extracted from sensors.py.

All sensor endpoints delegate here. No FastAPI imports; pure domain logic.
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.orm import Session as DBSession

from app.models import Alert, Decoy, Event, Node, Session as ActorSession
from app.services.sensor_pipeline.correlate import correlate_session
from app.services.sensor_pipeline.score import score_event
from app.services.sensor_pipeline.sensors import edge_evidence
from app.services.sensor_pipeline.alert import create_alert, maybe_rotate
from app.services.stream import alert_stream

BENIGN_ACTORS = {"backup-agent", "health-check", "scanner-benign"}


async def record_event(
    event_type: str,
    actor_id: str,
    host_id: str,
    decoy_id: str | None,
    token: str | None,
    action: str,
    credential_used: bool,
    breadcrumb_step: int,
    benign: bool,
    metadata: dict,
    simulated_timestamp: datetime | None,
    db: DBSession,
    decoy_sensitive: bool,
    auth_event: bool = False,
) -> dict:
    """Record a synthetic sensor event, optionally raise an alert, return result dict."""
    host = db.get(Node, host_id)
    if host is None:
        raise ValueError(f"Host '{host_id}' is not part of the synthetic network")

    decoy = db.get(Decoy, decoy_id) if decoy_id else None
    token_reuse = False
    if token and not decoy:
        decoy = db.query(Decoy).filter(Decoy.token == token).first()
        token_reuse = bool(decoy and decoy.host_id != host_id)
    if decoy_id and decoy is None:
        raise ValueError("Synthetic decoy not found")
    if decoy and decoy.host_id != host_id and token == decoy.token:
        token_reuse = True
    if decoy and token and token != decoy.token:
        raise ValueError("Tracking token does not match the selected decoy")
    if token_reuse:
        metadata = {**metadata, "token_reuse_detected": True,
                    "original_decoy_host": decoy.host_id, "original_decoy_id": decoy.id}

    now = simulated_timestamp or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    actor_session, is_new_actor, stitched_by_credential = correlate_session(
        db, actor_id, now, token=token,
        credential_signal=bool(credential_used or auth_event))

    touched_tokens: set[str] = set()
    for ev in db.query(Event).filter(Event.actor_id == actor_id).all():
        t = (ev.evidence or {}).get("token")
        if t:
            touched_tokens.add(t)
    if decoy:
        touched_tokens.add(decoy.token)

    breadcrumb = (decoy.content or {}).get("breadcrumb") if decoy else None
    chain_id = breadcrumb.get("chain_id") if isinstance(breadcrumb, dict) else None
    prior_chain_steps: set = set()
    if chain_id:
        for prior_event in db.query(Event).filter(Event.actor_id == actor_id).all():
            prior_evidence = prior_event.evidence or {}
            if prior_evidence.get("breadcrumb_chain_id") == chain_id:
                prior_chain_steps.add(prior_evidence.get("breadcrumb_step"))

    is_benign = benign or actor_id in BENIGN_ACTORS
    score = score_event(decoy, decoy_sensitive, is_new_actor, credential_used,
                        auth_event, breadcrumb_step, prior_chain_steps, chain_id, is_benign)
    D, N, U, P = score["D"], score["N"], score["U"], score["P"]
    confidence, severity = score["confidence"], score["severity"]

    event_id = f"evt-{uuid4().hex[:16]}"
    evidence = {
        "actor_id": actor_id, "action": action,
        "decoy_id": decoy.id if decoy else None,
        "decoy_name": decoy.name if decoy else None,
        "decoy_type": decoy.decoy_type if decoy else None,
        "token": decoy.token if decoy else token,
        "decoy_sensitivity": round(D, 4), "actor_novelty": round(N, 4),
        "credential_evidence": round(U, 4), "breadcrumb_progress": round(P, 4),
        "breadcrumb_chain_id": chain_id,
        "breadcrumb_step": breadcrumb.get("step") if isinstance(breadcrumb, dict) else breadcrumb_step,
        "benign_allowlisted": is_benign,
        "benign": is_benign,
        "credential_used": credential_used,
        "score_breakdown": {k: score[k] for k in ("D", "N", "U", "P", "raw_weighted_score", "benign_adjustment", "confidence")},
        "why_fired": (
            "Credential-use evidence detected" if U else "Synthetic decoy interaction detected"
        ) + (f"; breadcrumb progress {P:.2f}" if P else "") + ("; benign allow-list adjustment applied" if is_benign else ""),
        "recommended_next_action": "Review this session timeline and validate the synthetic credential-use evidence; do not take real-world action.",
        "token_reuse_detected": token_reuse,
        "original_decoy_host": decoy.host_id if token_reuse and decoy else None,
        "score_formula": "0.35D + 0.25N + 0.20U + 0.20P - 0.40Ib",
        "metadata": metadata,
        "session_id": actor_session.id,
        "session_stitched_by_credential_or_token": stitched_by_credential,
        "simulated": True,
        "scenario": metadata.get("scenario"),
        "run_id": metadata.get("run_id"),
        "step_index": metadata.get("step_index"),
        "ground_truth_label": metadata.get("ground_truth_label"),
    }

    # Inferred topology hops from prior actor location
    prior_actor_event = (db.query(Event).filter(Event.actor_id == actor_id)
                         .order_by(Event.timestamp.desc()).first())
    if prior_actor_event and prior_actor_event.host_id and prior_actor_event.host_id != host_id:
        from app.services.network_service import TOPOLOGY_EDGES
        import networkx as nx
        graph = nx.Graph()
        graph.add_edges_from(TOPOLOGY_EDGES)
        try:
            path = nx.shortest_path(graph, prior_actor_event.host_id.lower(), host_id.lower())
            evidence["inferred_hops"] = [
                {"source": a, "target": b, "edge_type": "inferred"}
                for a, b in zip(path, path[1:])
            ]
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            evidence["inferred_hops"] = []
    evidence["observed_edges"] = edge_evidence(metadata, event_id, host_id)

    event = Event(id=event_id, event_type=event_type, host_id=host_id,
                  actor_id=actor_id, timestamp=now, evidence=evidence)
    db.add(event)
    actor_session.last_seen_at = now
    actor_session.confidence = max(actor_session.confidence or 0.0, confidence)
    actor_session.status = ("benign-observed" if is_benign
                            else ("suspicious" if confidence >= 0.5 else "observing"))

    # Confidence / severity adjustments
    if metadata.get("force_high_alert") or (metadata.get("honey_login") and metadata.get("matched_decoy_id")):
        if not is_benign:
            confidence = max(confidence, 0.88)
            severity = "high"
    if metadata.get("force_low_alert"):
        confidence = min(confidence, 0.49)
        severity = "low"
    if is_benign and decoy_sensitive:
        severity = "low"
        confidence = min(confidence, 0.49)
    evidence["score_breakdown"] = {**(evidence.get("score_breakdown") or {}), "confidence": round(confidence, 4)}
    evidence["severity"] = severity

    alert = None
    if decoy_sensitive and (decoy is not None or auth_event or token or metadata.get("force_alert")):
        alert, rotation = create_alert(
            db=db,
            event=event,
            event_id=event_id,
            evidence=evidence,
            actor_id=actor_id,
            actor_session=actor_session,
            host_id=host_id,
            now=now,
            confidence=confidence,
            severity=severity,
            action=action,
            decoy=decoy,
            token_reuse=token_reuse,
            is_benign=is_benign,
            run_id=metadata.get("run_id"),
        )
        if rotation:
            evidence["auto_rotation"] = rotation
            event.evidence = {**(event.evidence or {}), "auto_rotation": rotation}
            alert.evidence = {**(alert.evidence or {}), "auto_rotation": rotation}

    db.commit()

    response: dict = {
        "event": {
            "id": event.id, "event_type": event.event_type, "host_id": event.host_id,
            "actor_id": event.actor_id, "timestamp": now.isoformat(), "evidence": evidence,
        },
        "session": {
            "id": actor_session.id,
            "status": actor_session.status,
            "confidence": actor_session.confidence,
        },
        "alert": None,
        "auto_rotation": evidence.get("auto_rotation"),
    }
    if alert:
        from app.models import Incident
        related_incident = next(
            (i for i in db.query(Incident).all()
             if event.id in ((i.evidence or {}).get("event_ids", []))),
            None,
        )
        response["alert"] = {
            "id": alert.id, "title": alert.title, "severity": alert.severity,
            "confidence": alert.confidence, "host_id": alert.host_id, "status": alert.status,
            "timestamp": now.isoformat(),
            "incident_id": related_incident.id if related_incident else None,
            "evidence": alert.evidence,
        }
        await alert_stream.publish({"type": "alert", "alert": response["alert"]})
    await alert_stream.publish({"type": "event", "event": response["event"]})
    return response
