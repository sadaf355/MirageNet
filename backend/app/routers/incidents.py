import os
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Alert, Event, Incident, Node
from app.services.network_service import TOPOLOGY_EDGES

router = APIRouter(prefix="/api/incidents", tags=["incidents"])


def _executive_summary(incident, evidence: dict) -> tuple[str, str]:
    """
    Return (summary_text, source_label).

    Default: plain template. If MIRAGENET_LLM_ENDPOINT is set, try calling it
    with a minimal prompt. Always falls back to the template on any failure.
    Labels the report with which mode was used.
    """
    techniques = [t["technique_id"] for t in evidence.get("attack_techniques", [])]
    hosts = [h.get("hostname", h.get("host_id")) for h in evidence.get("host_path", [])]
    event_count = evidence.get("event_count", 0)
    actors = ", ".join(evidence.get("actor_ids", [incident.id]))

    template = (
        f"This synthetic MirageNet incident ({incident.id}) recorded {event_count} "
        f"simulator event(s) attributed to actor(s) {actors} across "
        f"{len(hosts)} host(s): {', '.join(hosts) or 'none'}. "
        f"The evidence supports {len(techniques)} ATT\u0026CK technique mapping(s)"
        + (f": {', '.join(techniques)}" if techniques else "") +
        ". Severity is classified as "
        f"{incident.severity}. This summary was generated from synthetic simulator "
        "data only; no real intrusion, host, or credential is described."
    )

    llm_endpoint = os.getenv("MIRAGENET_LLM_ENDPOINT", "").strip()
    if not llm_endpoint:
        return template, "template"

    # Optional LLM path — never raises; always falls back to template.
    try:
        import urllib.request, json as _json, urllib.error
        prompt = (
            f"Write a concise 3-sentence executive summary for a synthetic cybersecurity "
            f"incident report. Incident ID: {incident.id}. Severity: {incident.severity}. "
            f"Events: {event_count}. Hosts: {', '.join(hosts)}. "
            f"ATT\u0026CK techniques: {', '.join(techniques) or 'none'}. "
            "Remind the reader this is all synthetic simulator data."
        )
        payload = _json.dumps({"prompt": prompt, "max_tokens": 200}).encode()
        req = urllib.request.Request(
            llm_endpoint, data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            body = _json.loads(resp.read())
        text = (
            body.get("choices", [{}])[0].get("text", "")
            or body.get("text", "")
            or body.get("response", "")
        ).strip()
        if text and len(text) > 40:
            return text, "llm"
    except Exception:
        pass
    return template, "template"

class ReconstructPayload(BaseModel):
    actor_id: str | None = None
    event_ids: list[str] | None = None
    title: str | None = None

def _iso(value):
    return value.isoformat() if value else None

def _event_view(event, hostname=None):
    ev = event.evidence or {}
    action = ev.get("action", event.event_type)
    return {
        "id": event.id, "event_type": event.event_type, "timestamp": _iso(event.timestamp),
        "host_id": event.host_id, "hostname": hostname or event.host_id,
        "actor_id": event.actor_id, "action": action,
        "summary": f"{event.actor_id} {str(action).replace('_', ' ')} on {hostname or event.host_id or 'unknown host'}",
        "evidence": ev,
    }

def _build_story(events, db):
    host_names = {n.id: n.hostname for n in db.query(Node).all()}
    timeline = [_event_view(e, host_names.get(e.host_id)) for e in sorted(events, key=lambda x: x.timestamp)]
    host_path = []
    for item in timeline:
        host_id = item["host_id"]
        if host_id and (not host_path or host_path[-1]["host_id"] != host_id):
            host_path.append({"host_id": host_id, "hostname": host_names.get(host_id, host_id),
                              "first_seen": item["timestamp"], "event_id": item["id"]})

    allowed_edges = {tuple(sorted((a.upper(), b.upper()))) for a, b in TOPOLOGY_EDGES}
    graph_edges = {}
    for event in events:
        for hop in (event.evidence or {}).get("inferred_hops", []):
            source, target = hop.get("source"), hop.get("target")
            if not source or not target or tuple(sorted((source, target))) not in allowed_edges:
                continue
            key = tuple(sorted((source, target)))
            graph_edges[key] = {"source": source, "target": target,
                                "basis": "topology_shortest_path_inference",
                                "evidence_event_ids": sorted(set(graph_edges.get(key, {}).get("evidence_event_ids", []) + [event.id]))}

    technique_rules = [
        ("T1083", "File and Directory Discovery", lambda e: e.event_type in {"file_enumeration"} or (e.event_type == "file_read" and (e.evidence or {}).get("action") == "enumerate")),
        ("T1005", "Data from Local System", lambda e: e.event_type == "file_read" and (e.evidence or {}).get("action") in {"read", "copy"}),
        ("T1552.001", "Credentials In Files", lambda e: e.event_type == "file_read" and ("credential" in str((e.evidence or {}).get("decoy_type", "")).lower() or "credential" in str((e.evidence or {}).get("decoy_name", "")).lower())),
        ("T1078", "Valid Accounts", lambda e: e.event_type == "auth_attempt" and bool((e.evidence or {}).get("credential_evidence"))),
        ("T1021.002", "SMB/Windows Admin Shares", lambda e: e.event_type == "simulated_smb"),
        ("T1021.004", "SSH", lambda e: e.event_type == "simulated_ssh"),
        ("T1213", "Data from Information Repositories", lambda e: e.event_type == "database_query"),
        ("T1074", "Data Staged", lambda e: e.event_type == "bulk_copy"),
        ("T1041", "Exfiltration Over C2 Channel", lambda e: e.event_type == "simulated_upload"),
    ]
    techniques = {}
    for event in events:
        for technique_id, name, predicate in technique_rules:
            if predicate(event):
                techniques.setdefault(technique_id, {"technique_id": technique_id, "name": name, "evidence_event_ids": []})
                if event.id not in techniques[technique_id]["evidence_event_ids"]:
                    techniques[technique_id]["evidence_event_ids"].append(event.id)

    event_ids = {e.id for e in events}
    alerts = db.query(Alert).all()
    related_alerts = [a for a in alerts if (a.evidence or {}).get("event_id") in event_ids]
    severity = "high" if any(a.severity == "high" for a in related_alerts) else ("medium" if techniques or len(events) >= 2 else "low")
    recommendations = [
        "Preserve the synthetic event sequence and evidence IDs for review.",
        "Inspect the decoy artifacts and breadcrumb order involved in this session.",
        "Validate actor classification before taking any real-world response action.",
    ]
    if any(t["technique_id"] in {"T1078", "T1552.001"} for t in techniques.values()):
        recommendations.insert(0, "Review the simulated credential-use sequence; use only disposable lab credentials.")
    return {
        "timeline": timeline, "host_path": host_path, "graph_edges": list(graph_edges.values()),
        "graph_note": "Edges are inferred from the simulator topology between sequential observed hosts; they are not claims of real network traffic.",
        "attack_techniques": sorted(techniques.values(), key=lambda x: x["technique_id"]),
        "alert_ids": [a.id for a in related_alerts], "recommendations": recommendations,
        "event_count": len(events), "actor_ids": sorted({e.actor_id for e in events}),
        "source": "reconstructed_from_persisted_synthetic_events",
        "event_ids": [e.id for e in sorted(events, key=lambda x: x.timestamp)],
        "ended_at": _iso(max(e.timestamp for e in events)),
    }, severity

def _serialize(incident):
    exec_summary, exec_source = _executive_summary(incident, incident.evidence or {})
    return {"id": incident.id, "title": incident.title, "status": incident.status,
            "severity": incident.severity, "started_at": _iso(incident.started_at),
            "summary": incident.summary,
            "executive_summary": exec_summary,
            "executive_summary_source": exec_source,
            "evidence": incident.evidence or {}}

@router.get("")
def list_incidents(db: Session = Depends(get_db)):
    rows = db.query(Incident).order_by(Incident.started_at.desc()).limit(50).all()
    return [{"id": i.id, "title": i.title, "status": i.status, "severity": i.severity,
             "started_at": _iso(i.started_at), "summary": i.summary,
             "event_count": (i.evidence or {}).get("event_count", 0)} for i in rows]

@router.post("/reconstruct")
def reconstruct(payload: ReconstructPayload, db: Session = Depends(get_db)):
    query = db.query(Event)
    if payload.event_ids:
        query = query.filter(Event.id.in_(payload.event_ids))
    elif payload.actor_id:
        query = query.filter(Event.actor_id == payload.actor_id)
    else:
        query = query.order_by(Event.timestamp.desc()).limit(100)
    events = sorted(query.all(), key=lambda e: e.timestamp)
    if not events:
        raise HTTPException(status_code=404, detail="No persisted simulator events found for reconstruction")
    story, severity = _build_story(events, db)
    actors = ", ".join(story["actor_ids"])
    incident = Incident(
        id=f"inc-{uuid4().hex[:16]}",
        title=(payload.title or f"Simulated intrusion story · {actors}")[:180],
        status="investigating", severity=severity, started_at=events[0].timestamp,
        summary=f"Reconstructed {len(events)} persisted synthetic events across {len(story['host_path'])} distinct hosts. "
                f"Evidence supports {len(story['attack_techniques'])} ATT&CK technique mapping(s).",
        evidence=story,
    )
    db.add(incident)
    db.commit()
    db.refresh(incident)
    return _serialize(incident)

@router.get("/{incident_id}")
def get_incident(incident_id: str, db: Session = Depends(get_db)):
    incident = db.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return _serialize(incident)

@router.get("/{incident_id}/report")
def incident_report(incident_id: str, format: str = Query(default="json", pattern="^(json|md)$"),
                    db: Session = Depends(get_db)):
    incident = db.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    data = _serialize(incident)
    if format == "json":
        return JSONResponse(content=data, headers={"Content-Disposition": f'attachment; filename="{incident_id}-report.json"'})
    evidence = data["evidence"]
    exec_summary = data.get("executive_summary", "")
    exec_source = data.get("executive_summary_source", "template")
    lines = [
        f"# {incident.title}", "", f"- **Incident ID:** `{incident.id}`",
        f"- **Status:** {incident.status}", f"- **Severity:** {incident.severity}",
        f"- **Started:** {_iso(incident.started_at)}", f"- **Events:** {evidence.get('event_count', 0)}", "",
        "## Executive Summary", f"_Generated by: {exec_source}_", "",
        exec_summary, "",
        "## Summary", "", incident.summary, "", "## Host path", ""
    ]
    for index, host in enumerate(evidence.get("host_path", []), 1):
        lines.append(f"{index}. **{host.get('hostname', host.get('host_id'))}** (`{host.get('host_id')}`)")
    lines += ["", "## Evidence timeline", ""]
    for item in evidence.get("timeline", []):
        lines.append(f"- {item.get('timestamp')} — **{item.get('hostname')}**: {item.get('summary')} (event `{item.get('id')}`)")
    lines += ["", "## MITRE ATT&CK mappings", ""]
    if evidence.get("attack_techniques"):
        for technique in evidence["attack_techniques"]:
            ids = ", ".join(f"`{x}`" for x in technique.get("evidence_event_ids", []))
            lines.append(f"- **{technique['technique_id']} — {technique['name']}**; evidence: {ids}")
    else:
        lines.append("No ATT&CK technique met the current evidence rules.")
    lines += ["", "## Response recommendations", ""]
    lines += [f"- {item}" for item in evidence.get("recommendations", [])]
    lines += ["", "---", "Generated from MirageNet synthetic simulator data only."]
    return PlainTextResponse("\n".join(lines), media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{incident_id}-report.md"'})
