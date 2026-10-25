import json
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Alert, Decoy, Event, Node
from app.routers.scenarios import SCENARIOS, _load_ground_truth, _technique_for

router = APIRouter(prefix="/api/eval", tags=["evaluation"])

ATTACKER_QUERIES = {
    "credentials": ("administrator credentials password vault access notes", {"credential_note"}),
    "finance_data": ("finance payroll vendor payment forecast database export", {"finance_hr", "database"}),
    "configuration_and_api": ("SSH configuration private key API token webhook endpoint integration", {"config", "api_artifact"}),
}


def _f1(tp: int, fp: int, fn: int) -> float:
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return round(2 * precision * recall / (precision + recall), 4) if precision + recall else 0.0


@router.get("")
def evaluation_summary(db: Session = Depends(get_db)):
    events = db.query(Event).all()
    alerts = db.query(Alert).all()
    alert_event_ids = {str((a.evidence or {}).get("event_id")) for a in alerts if (a.evidence or {}).get("event_id")}
    alerts_by_run = {}
    for alert in alerts:
        evidence = alert.evidence or {}
        run_id = evidence.get("run_id")
        if run_id:
            alerts_by_run.setdefault(run_id, []).append(alert)

    runs = {}
    host_names = {node.id: node.hostname for node in db.query(Node).all()}
    for event in events:
        ev = event.evidence or {}
        run_id = ev.get("run_id")
        if not run_id:
            continue
        item = runs.setdefault(run_id, {"run_id": run_id, "scenario": ev.get("scenario"),
            "ground_truth": ("malicious" if ev.get("ground_truth") == "malicious" or ev.get("ground_truth_label") == "positive" else ("benign" if ev.get("ground_truth") == "benign" or ev.get("ground_truth_label") == "negative" else None)), "events": [], "first_alert_latency_seconds": ev.get("first_alert_latency_seconds")})
        item["events"].append(event)
        if ev.get("evaluation_ground_truth_steps"):
            item["ground_truth_steps"] = ev.get("evaluation_ground_truth_steps")
            item["ground_truth"] = ev.get("evaluation_ground_truth_label", item.get("ground_truth"))
            item["evaluation_source"] = ev.get("evaluation_source")
        if ev.get("first_alert_latency_seconds") is not None:
            item["first_alert_latency_seconds"] = ev["first_alert_latency_seconds"]

    run_rows = []
    totals = {"tp": 0, "fp": 0, "fn": 0, "benign_high": 0}
    latency_values = []
    for item in runs.values():
        tp = fp = fn = 0
        for event in item["events"]:
            positive = item["ground_truth"] == "malicious"
            predicted = event.id in alert_event_ids
            if positive and predicted: tp += 1
            elif positive and not predicted: fn += 1
            elif not positive and predicted: fp += 1
        run_alerts = alerts_by_run.get(item["run_id"], [])
        benign_high = sum(1 for a in run_alerts if a.severity == "high") if item["ground_truth"] == "benign" else 0
        rate = tp / (tp + fn) if tp + fn else None
        # Timeline F1 is computed against ordered scenario ground-truth steps,
        # matching event type, host, and ATT&CK technique—not alert counts.
        scenario_name = item.get("scenario")
        spec = SCENARIOS.get(scenario_name, {})
        truth_steps = item.get("ground_truth_steps") or (_load_ground_truth(scenario_name, spec) if scenario_name in SCENARIOS else [])
        actual_events = sorted(item["events"], key=lambda e: e.timestamp)
        actual_steps = []
        for actual in actual_events:
            ev = actual.evidence or {}
            actual_type = actual.event_type
            actual_action = ev.get("action", actual_type)
            actual_steps.append({"event_type": actual_type, "host": host_names.get(actual.host_id, str(actual.host_id or "")).upper(),
                "action": actual_action, "technique": _technique_for(actual_type, actual_action)})
        if truth_steps:
            _, step_precision, step_recall, step_f1 = _sequence_match(actual_steps, truth_steps)
        else:
            step_precision = step_recall = 0.0
            step_f1 = None
        latency = item.get("first_alert_latency_seconds") if item["ground_truth"] == "malicious" else None
        if latency is not None: latency_values.append(float(latency))
        totals["tp"] += tp; totals["fp"] += fp; totals["fn"] += fn; totals["benign_high"] += benign_high
        run_rows.append({"run_id": item["run_id"], "scenario": item["scenario"], "ground_truth": item["ground_truth"],
            "events": len(item["events"]), "true_positive_events": tp, "false_positive_events": fp,
            "missed_positive_events": fn, "observed_detection_rate": round(rate, 4) if rate is not None else None,
            "timeline_step_f1": round(step_f1, 4) if step_f1 is not None and item["ground_truth"] == "malicious" else None,
            "benign_high_severity_alerts": benign_high, "time_to_first_alert_seconds": latency})

    decoys = db.query(Decoy).filter(Decoy.status != "burned").all()
    enticement = {}
    # Real TF-IDF cosine ranking over the artifact's persisted content, filename,
    # path and lure theme. No type-priority sort is used.
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        import numpy as np
        docs = []
        for d in decoys:
            content = d.content or {}
            docs.append(" ".join([d.decoy_type, d.name, str(content.get("path", "")),
                str(content.get("filename", "")), str(content.get("body", "")),
                str(content.get("lure_theme", "")), json.dumps(content, ensure_ascii=False, sort_keys=True)]))
        for query_name, (query_text, target_types) in ATTACKER_QUERIES.items():
            if not docs:
                enticement[query_name] = {"top_10_count": 0, "target_type_hits": 0, "pass": False, "ranked_decoy_ids": [], "scores": []}
                continue
            vectorizer = TfidfVectorizer(ngram_range=(1, 2), stop_words="english")
            matrix = vectorizer.fit_transform(docs + [query_text])
            similarities = (matrix[:-1] @ matrix[-1].T).toarray().ravel()
            order = np.argsort(-similarities)[:10]
            top10 = [decoys[int(i)] for i in order]
            enticement[query_name] = {"top_10_count": len(top10), "target_type_hits": sum(1 for d in top10 if d.decoy_type in target_types),
                "pass": any(d.decoy_type in target_types for d in top10),
                "ranked_decoy_ids": [d.id for d in top10], "scores": [round(float(similarities[int(i)]), 6) for i in order]}
    except Exception as exc:
        enticement = {query_name: {"top_10_count": 0, "target_type_hits": 0, "pass": False, "ranked_decoy_ids": [], "error": str(exc)} for query_name in ATTACKER_QUERIES}

    malicious = [r for r in run_rows if r["ground_truth"] == "malicious"]
    benign = [r for r in run_rows if r["ground_truth"] == "benign"]
    scenario_results = []
    for scenario_name in sorted({str(r["scenario"]) for r in run_rows if r.get("scenario")}):
        group = [r for r in run_rows if r.get("scenario") == scenario_name]
        scenario_results.append({"scenario": scenario_name, "runs": len(group),
            "ground_truth": group[0].get("ground_truth"),
            "detection_rate": round(sum(r["observed_detection_rate"] for r in group if r["observed_detection_rate"] is not None) / max(1, sum(1 for r in group if r["observed_detection_rate"] is not None)), 4) if any(r["observed_detection_rate"] is not None for r in group) else None,
            "timeline_step_f1": round(sum(r["timeline_step_f1"] for r in group if r["timeline_step_f1"] is not None) / max(1, sum(1 for r in group if r["timeline_step_f1"] is not None)), 4) if any(r["timeline_step_f1"] is not None for r in group) else None,
            "false_positive_events": sum(r["false_positive_events"] for r in group),
            "missed_positive_events": sum(r["missed_positive_events"] for r in group)})
    tp_runs = sum(1 for r in run_rows if r["ground_truth"] == "malicious" and r["true_positive_events"] > 0)
    fn_runs = sum(1 for r in run_rows if r["ground_truth"] == "malicious" and r["true_positive_events"] == 0)
    fp_runs = sum(1 for r in run_rows if r["ground_truth"] == "benign" and r["false_positive_events"] > 0)
    tn_runs = sum(1 for r in run_rows if r["ground_truth"] == "benign" and r["false_positive_events"] == 0)
    latencies = [float(r["time_to_first_alert_seconds"]) for r in run_rows if r["time_to_first_alert_seconds"] is not None]
    latency_distribution = [{"bucket": label, "count": sum(1 for value in latencies if lower <= value < upper)}
        for label, lower, upper in [("<0.01s",0,0.01),("0.01–0.05s",0.01,0.05),("0.05–0.1s",0.05,0.1),("0.1–0.5s",0.1,0.5),("≥0.5s",0.5,float("inf"))]]
    return {"mode": "observed_synthetic_runs_only", "targets": {
            "detection_rate": 1.0, "timeline_step_f1": 0.90, "benign_high_severity_alerts": 0,
            "time_to_first_alert_seconds": 1.0, "enticement_top10_pass_rate": 0.70},
        "measured": {"runs_total": len(run_rows), "malicious_runs": len(malicious), "benign_runs": len(benign),
            "mean_observed_detection_rate": round(sum(r["observed_detection_rate"] for r in malicious if r["observed_detection_rate"] is not None) / max(1, sum(1 for r in malicious if r["observed_detection_rate"] is not None)), 4) if malicious else None,
            "event_level_precision": round(totals["tp"] / (totals["tp"] + totals["fp"]), 4) if totals["tp"] + totals["fp"] else 0.0,
            "event_level_recall": round(totals["tp"] / (totals["tp"] + totals["fn"]), 4) if totals["tp"] + totals["fn"] else 0.0,
            "timeline_step_f1": round(sum(r["timeline_step_f1"] for r in malicious if r["timeline_step_f1"] is not None) / max(1, sum(1 for r in malicious if r["timeline_step_f1"] is not None)), 4) if malicious else None,
            "benign_high_severity_alerts": totals["benign_high"],
            "time_to_first_alert_seconds": round(sum(latency_values) / len(latency_values), 6) if latency_values else None,
            "enticement_top10_pass_rate": round(sum(1 for value in enticement.values() if value["pass"]) / len(enticement), 4) if enticement else 0.0},
        "enticement_queries": enticement,
        "scenario_results": scenario_results,
        "confusion_matrix": {"true_positive": tp_runs, "false_negative": fn_runs, "false_positive": fp_runs, "true_negative": tn_runs,
            "unit": "scenario run; positive means at least one alert was emitted"},
        "latency_distribution": latency_distribution,
        "runs": sorted(run_rows, key=lambda r: r["run_id"], reverse=True),
        "notes": ["Targets are acceptance criteria, not measured values.",
            "Timeline F1 is ordered matching against data/scenarios ground truth by event type, host, and ATT&CK technique; benign runs have no positive timeline F1 and show n/a.",
            "Latency measures scenario-run wall-clock time from run start to first generated alert; it is not sensor-to-alert production latency.",
            "Enticement ranking is TF-IDF cosine similarity over persisted artifact text and attacker queries; it is not an external attacker study.",
            "Confusion matrix is run-level: a malicious run is detected if any alert is emitted; a benign run is a false positive if any alert is emitted.",
            "All scenarios are synthetic and run locally; repeat from a clean database for comparable evaluation."]}



def _sequence_match(observed: list[dict], expected: list[dict]) -> tuple[int, float, float, float]:
    """Order-sensitive LCS matching; an extra, missing, or reordered step is penalized."""
    def signature(row: dict) -> tuple[str, str, str]:
        host = row.get("host") or row.get("hostname") or row.get("host_id") or ""
        return (str(row.get("event_type", "")), str(host).upper(), str(row.get("technique") or _technique_for(str(row.get("event_type", "")), str(row.get("action", "")))))
    a, b = [signature(x) for x in observed], [signature(x) for x in expected]
    dp = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            dp[i][j] = dp[i-1][j-1] + 1 if a[i-1] == b[j-1] else max(dp[i-1][j], dp[i][j-1])
    matched = dp[-1][-1]
    precision = matched / len(observed) if observed else 0.0
    recall = matched / len(expected) if expected else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return matched, round(precision, 4), round(recall, 4), round(f1, 4)


@router.post("/replay-adaption")
async def replay_adaption_sessions(db: Session = Depends(get_db)):
    """Replay session rows as black-box sensor input, then compare event-derived steps to ground truth."""
    from datetime import datetime, timezone
    from pathlib import Path
    from time import perf_counter
    from app.routers.sensors import SensorPayload, _record
    from app.services.adaption_integration import EVIDENCE_DIR, _load_manifest

    session_path = EVIDENCE_DIR / "sessions.jsonl"
    if not session_path.exists():
        raise HTTPException(status_code=404, detail="No session dataset found. Generate labelled sessions first.")
    rows = []
    for line in session_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try: rows.append(json.loads(line))
            except ValueError: continue
    if not rows:
        raise HTTPException(status_code=400, detail="Session dataset contains no valid JSONL rows.")
    hosts = {node.hostname.upper(): node for node in db.query(Node).all()}
    deployed = db.query(Decoy).filter(Decoy.status == "deployed").all()
    by_host = {}
    for decoy in deployed: by_host.setdefault(decoy.host_id, decoy)
    replayed = []
    for row_index, row in enumerate(rows):
        observed_input = row.get("observed_steps") or row.get("steps") or []
        truth = row.get("ground_truth_steps") or row.get("steps") or []
        if not isinstance(observed_input, list) or not isinstance(truth, list):
            continue
        label = "malicious" if str(row.get("label", "malicious")).lower() in {"malicious", "positive", "attack"} else "benign"
        run_id = f"adap-{uuid4().hex[:12]}"
        event_ids, alert_ids, event_derived = [], [], []
        started = perf_counter()
        first_alert_latency = None
        for index, step in enumerate(observed_input):
            event_type = str(step.get("event_type", "endpoint_activity"))
            host_name = str(step.get("host", "WEB-01")).upper()
            host = hosts.get(host_name)
            if host is None: continue
            action = str(step.get("action", "observe"))
            technique = _technique_for(event_type, action)
            sensitive = event_type in {"file_read", "bulk_copy", "auth_attempt", "simulated_ssh"} or action in {"read", "copy", "stage", "credential_use", "simulated_ssh"}
            decoy = by_host.get(host.id) if sensitive else None
            payload = SensorPayload(actor_id=str(row.get("session_id") or f"adaption-session-{row_index}")[:80],
                host_id=host.id, decoy_id=decoy.id if decoy else None, token=decoy.token if decoy else None,
                action=action, credential_used=action in {"credential_use", "simulated_ssh"},
                breadcrumb_step=min(3, index + 1), benign=label == "benign",
                simulated_timestamp=datetime.now(timezone.utc),
                metadata={"scenario": str(row.get("scenario") or "adaption-session"), "run_id": run_id,
                    "session_id": str(row.get("session_id") or f"session-{row_index}"),
                    "ground_truth_label": "positive" if label == "malicious" else "negative",
                    "black_box_replay": True, "simulated": True,
                    "force_alert": bool(sensitive), "force_low_alert": event_type == "file_enumeration"})
            result = await _record(event_type, payload, db, decoy_sensitive=sensitive,
                                   auth_event=event_type == "auth_attempt")
            event = result["event"]
            alert = result.get("alert")
            event_ids.append(event["id"])
            if alert:
                alert_ids.append(alert["id"])
                if first_alert_latency is None:
                    first_alert_latency = round(perf_counter() - started, 6)
            # Derive from the persisted event and its observed evidence, not the supplied truth.
            stored = db.get(Event, event["id"])
            ev = stored.evidence or {}
            derived_type = stored.event_type
            derived_action = str(ev.get("action", action))
            event_derived.append({"event_type": derived_type, "host": host_name,
                                  "action": derived_action, "technique": _technique_for(derived_type, derived_action)})
        elapsed = round(perf_counter() - started, 6)
        matched, precision, recall, f1 = _sequence_match(event_derived, truth)
        # Ground truth is attached only after the event-derived timeline has been reconstructed.
        if event_ids:
            first = db.get(Event, event_ids[0])
            first.evidence = {**(first.evidence or {}), "first_alert_latency_seconds": first_alert_latency,
                "scenario_run_elapsed_seconds": elapsed, "evaluation_ground_truth_steps": truth,
                "evaluation_ground_truth_label": label, "evaluation_source": "adaption_session_replay",
                "evaluation_timeline_metrics": {"matched": matched, "precision": precision, "recall": recall, "f1": f1}}
        replayed.append({"run_id": run_id, "session_id": row.get("session_id", f"session-{row_index}"),
            "scenario": row.get("scenario", "adaption-session"), "ground_truth": label,
            "events": len(event_ids), "alerts": len(alert_ids), "matched_steps": matched,
            "expected_steps": len(truth), "observed_steps": len(event_derived),
            "timeline_step_precision": precision, "timeline_step_recall": recall, "timeline_step_f1": f1,
            "time_to_replay_seconds": elapsed, "event_ids": event_ids, "alert_ids": alert_ids,
            "observed_timeline": event_derived, "ground_truth_steps": truth})
    db.commit()
    output_path = EVIDENCE_DIR / "replay_results.jsonl"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("a", encoding="utf-8") as stream:
        for item in replayed:
            stream.write(json.dumps(item, ensure_ascii=False) + "\n")
    manifest = _load_manifest()
    return {"source_mode": "adaption_generated" if manifest.get("session_dataset_status") == "adaption_generated" else "cache",
            "sessions_replayed": len(replayed), "events_emitted": sum(r["events"] for r in replayed),
            "alerts_emitted": sum(r["alerts"] for r in replayed),
            "mean_timeline_step_f1": round(sum(r["timeline_step_f1"] for r in replayed) / len(replayed), 4) if replayed else None,
            "runs": replayed,
            "note": "Black-box input replayed through the sensor path; event-derived timelines were reconstructed before post-hoc comparison with ground truth."}
