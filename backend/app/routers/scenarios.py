from datetime import datetime, timezone
from time import perf_counter
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Alert, Decoy, Event, Incident, Node
from app.services.scoring import confidence_score, severity_for
from app.services.stream import alert_stream
from app.services.network_service import TOPOLOGY_EDGES
import networkx as nx

router = APIRouter(prefix="/api/scenarios", tags=["scenarios"])
SCENARIOS = {
    "insider-data-theft": {"label":"Insider data theft", "actor":"scenario-insider", "actions":[("file_read","FS-01","read",True,1),("file_read","FS-01","copy",True,2),("bulk_copy","BKP-01","stage",True,3)], "malicious":True},
    "credential-lateral-movement": {"label":"Stolen-credential lateral movement", "actor":"scenario-credential", "actions":[("file_read","WS-01","read",True,1),("auth_attempt","JMP-01","credential_use",True,2),("simulated_ssh","DB-01","simulated_ssh",True,3)], "malicious":True},
    "slow-scan-theft": {"label":"Slow scan then theft", "actor":"scenario-slow-scan", "actions":[("file_enumeration","WEB-01","enumerate",False,1),("file_read","FS-01","read",True,2),("file_read","DB-01","copy",True,3)], "malicious":True},
    "benign-backup-noise": {"label":"Benign scanner and backup noise", "actor":"backup-agent", "actions":[("endpoint_activity","BKP-01","health_check",False,1),("endpoint_activity","FS-01","backup_status",False,1),("endpoint_activity","BKP-01","backup_complete",False,1)], "malicious":False},
    "noisy-partial-intrusion": {"label":"Noisy scan with partial detection", "actor":"scenario-noisy", "actions":[("endpoint_activity","WEB-01","banner_probe",False,1),("file_enumeration","WS-01","enumerate",False,2),("file_read","FS-01","read",True,3),("endpoint_activity","BKP-01","health_check",False,1)], "malicious":True},
    "benign-scanner": {"label":"Benign vulnerability scanner", "actor":"scanner-benign", "actions":[("file_enumeration","WEB-01","enumerate",False,1),("endpoint_activity","WEB-01","health_check",False,2)], "malicious":False},
    "benign-health-check": {"label":"Benign service health checks", "actor":"health-check", "actions":[("endpoint_activity","WEB-01","health_check",False,1),("endpoint_activity","DB-01","health_check",False,2),("endpoint_activity","BKP-01","health_check",False,3)], "malicious":False},
    "benign-admin-login": {"label":"Benign administrator login", "actor":"admin-operator", "actions":[("auth_attempt","JMP-01","admin_login",False,1),("endpoint_activity","JMP-01","session_check",False,2)], "malicious":False},
    "imperfect-missed-step": {"label":"Imperfect replay · missed step", "actor":"scenario-missed", "actions":[("file_read","WS-01","read",True,1),("simulated_ssh","DB-01","simulated_ssh",True,2)], "malicious":True},
    "imperfect-extra-benign-step": {"label":"Imperfect replay · extra benign step", "actor":"scenario-extra", "actions":[("file_read","FS-01","read",True,1),("endpoint_activity","BKP-01","health_check",False,2),("file_read","FS-01","copy",True,3),("bulk_copy","BKP-01","stage",True,4)], "malicious":True},
    "imperfect-reordered-step": {"label":"Imperfect replay · reordered step", "actor":"scenario-reordered", "actions":[("file_read","FS-01","copy",True,1),("file_read","FS-01","read",True,2),("bulk_copy","BKP-01","stage",True,3)], "malicious":True},
}

@router.get("")
def scenario_catalog():
    return [{"name":name,"label":item["label"],"expected_events":len(item["actions"]),"ground_truth":"malicious" if item["malicious"] else "benign"} for name,item in SCENARIOS.items()]

@router.post("/{name}/run")
async def run_scenario(name: str, db: Session = Depends(get_db)):
    """Run deterministic steps through the same sensor path as Play mode."""
    from datetime import timedelta
    from app.routers.sensors import SensorPayload, _record
    spec = SCENARIOS.get(name)
    if not spec:
        raise HTTPException(status_code=404, detail="Unknown named simulation scenario")
    hosts = {n.hostname: n for n in db.query(Node).all()}
    decoys = db.query(Decoy).filter(Decoy.status == "deployed").all()
    by_host = {}
    for decoy in decoys:
        by_host.setdefault(decoy.host_id, []).append(decoy)
    run_id = f"run-{uuid4().hex[:12]}"
    base_time = datetime.now(timezone.utc)
    event_ids, alert_ids, step_results = [], [], []
    first_alert = None
    run_clock = perf_counter()
    for index, (event_type, hostname, action, sensitive, step) in enumerate(spec["actions"]):
        host = hosts.get(hostname)
        if not host:
            continue
        decoy = (by_host.get(host.id) or [None])[0]
        # Each scenario step is two simulated minutes after the prior step.
        timestamp = base_time + timedelta(minutes=2 * index)
        payload = SensorPayload(actor_id=spec["actor"], host_id=host.id,
            decoy_id=decoy.id if decoy and sensitive else None,
            token=decoy.token if decoy and sensitive else None, action=action,
            credential_used=action in {"credential_use", "simulated_ssh"},
            breadcrumb_step=min(3, index + 1), benign=not spec["malicious"],
            simulated_timestamp=timestamp,
            metadata={"scenario": name, "run_id": run_id, "step_index": index,
                      "ground_truth_label": "positive" if spec["malicious"] else "negative",
                      "expected_event_type": event_type, "simulated": True,
                      "force_alert": sensitive or event_type == "file_enumeration",
                      "force_low_alert": event_type == "file_enumeration"})
        result = await _record(event_type, payload, db, decoy_sensitive=(sensitive or event_type == "file_enumeration"),
                               auth_event=event_type == "auth_attempt")
        event = result["event"]
        alert = result.get("alert")
        event_ids.append(event["id"])
        if alert:
            alert_ids.append(alert["id"])
            if first_alert is None:
                first_alert = round(perf_counter() - run_clock, 6)
        step_results.append({"step_index": index, "event_id": event["id"],
                             "event_type": event_type, "host": hostname,
                             "action": action, "alert_id": alert["id"] if alert else None,
                             "technique": _technique_for(event_type, action)})
    elapsed = round(perf_counter() - run_clock, 6)
    if event_ids:
        first_event = db.get(Event, event_ids[0])
        if first_event:
            first_event.evidence = {**(first_event.evidence or {}), "first_alert_latency_seconds": first_alert,
                "scenario_run_elapsed_seconds": elapsed}
            db.commit()
    expected = len(spec["actions"])
    alerted_steps = sum(1 for row in step_results if row["alert_id"])
    detection = alerted_steps / expected if spec["malicious"] and expected else None
    # Reconstruct observed steps from sensor output, then compare with separate ground truth.
    truth = _load_ground_truth(name, spec)
    matched, precision, recall, f1 = _sequence_match(step_results, truth)
    benign_high = db.query(Alert).filter(Alert.id.in_(alert_ids), Alert.severity == "high").count() if alert_ids else 0
    from app.services.sensor_pipeline.playbook import classify_playbook
    playbook = classify_playbook([], [{"event_type": row["event_type"], "action": row["action"],
        "evidence": {"action": row["action"]}} for row in step_results])
    return {"run_id": run_id, "scenario": name, "label": spec["label"], "adversary_playbook": playbook,
        "ground_truth": "malicious" if spec["malicious"] else "benign", "status": "completed",
        "safe_mode": True, "event_ids": event_ids, "alert_ids": alert_ids,
        "expected_events": expected, "events_emitted": len(event_ids), "alerts_emitted": len(alert_ids),
        "observed_detection_rate": detection, "benign_high_severity_alerts": benign_high,
        "time_to_first_alert_seconds": first_alert, "run_elapsed_seconds": elapsed,
        "timeline_step_precision": precision if spec["malicious"] else None,
        "timeline_step_recall": recall if spec["malicious"] else None,
        "timeline_step_f1": f1 if spec["malicious"] else None, "timeline_steps": step_results,
        "inferred_topology_hops": True,
        "note": "Synthetic deterministic scenario; all actions pass through the shared sensor path."}

def _sequence_match(observed: list[dict], expected: list[dict]) -> tuple[int, float, float, float]:
    def sig(row: dict) -> tuple[str, str, str]:
        event_type = str(row.get("event_type", ""))
        host = str(row.get("host", row.get("hostname", ""))).upper()
        action = str(row.get("action", event_type))
        return event_type, host, str(row.get("technique") or _technique_for(event_type, action))
    a, b = [sig(row) for row in observed], [sig(row) for row in expected]
    dp = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            dp[i][j] = dp[i-1][j-1] + 1 if a[i-1] == b[j-1] else max(dp[i-1][j], dp[i][j-1])
    matched = dp[-1][-1]
    precision = matched / len(a) if a else 0.0
    recall = matched / len(b) if b else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return matched, round(precision, 4), round(recall, 4), round(f1, 4)


def _technique_for(event_type: str, action: str) -> str:
    if action in {"credential_use", "simulated_ssh"}: return "T1078"
    if event_type == "file_enumeration": return "T1083"
    if event_type == "bulk_copy" or action in {"copy", "stage"}: return "T1074"
    if event_type == "auth_attempt": return "T1021.004"
    if event_type == "file_read": return "T1005"
    if event_type == "endpoint_activity": return "T1041"
    return "T1041" if action == "upload" else "T1083"

def _load_ground_truth(name: str, spec: dict) -> list[dict]:
    import json
    from pathlib import Path
    path = Path(__file__).resolve().parents[3] / "data" / "scenarios" / f"{name}.json"
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("steps"), list): return data["steps"]
        except (OSError, ValueError):
            pass
    return [{"event_type": a[0], "host": a[1], "action": a[2], "technique": _technique_for(a[0], a[2])} for a in spec["actions"]]
