"""Isolated end-to-end smoke test for MirageNet's synthetic API workflow.

Run from backend with: python scripts/smoke_test.py
Uses a temporary SQLite database and does not alter miragenet.db.
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

_tmp = tempfile.TemporaryDirectory(prefix="miragenet-smoke-")
_db_path = Path(_tmp.name) / "smoke.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_db_path.as_posix()}"

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402

SCENARIOS = [
    "insider-data-theft",
    "credential-lateral-movement",
    "slow-scan-theft",
    "benign-backup-noise",
]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    checks: list[dict] = []
    with TestClient(app) as client:
        health = client.get("/api/health")
        require(health.status_code == 200, "health endpoint failed")
        checks.append({"check": "health", "status": "pass"})

        forged_response = client.post("/api/forge/run", json={"count": 60, "company_profile": "fictional-demo-enterprise"})
        require(forged_response.status_code == 200, "forge failed")
        forged = forged_response.json()
        require(forged["created"] == 60, "forge did not create 60 decoys")
        decoys = forged["decoys"]
        require(len({d["token"] for d in decoys}) == 60, "decoy tokens are not unique")
        require(len({d["type"] for d in decoys}) == 5, "expected five decoy types")
        require(len(forged["breadcrumb_chain"]["steps"]) == 3, "three-step breadcrumb missing")
        checks.append({"check": "forge_60_unique_tokens_five_types_three_step_breadcrumb", "status": "pass"})

        deployed_response = client.post("/api/deploy")
        require(deployed_response.status_code == 200 and deployed_response.json()["deployed"] == 60, "deploy failed")
        checks.append({"check": "deploy_60", "status": "pass"})

        play_entry = client.get("/api/play/filesystem").json()["entries"][0]
        play_read = client.post("/api/play/read", json={"decoy_id": play_entry["id"], "actor_id": "smoke-play-actor"})
        require(play_read.status_code == 200, "Play mode read failed")
        play_result = play_read.json()
        require(len(play_result.get("preview", "")) > 20, "Play mode did not return a readable synthetic body")
        require(play_result.get("event", {}).get("event_type") == "file_read", "Play mode did not use shared sensor path")
        require(play_result.get("alert") is not None, "Play mode did not generate an alert")
        checks.append({"check": "play_read_body_sensor_event_and_alert", "status": "pass"})

        scenario_results = []
        for scenario in SCENARIOS:
            response = client.post(f"/api/scenarios/{scenario}/run")
            require(response.status_code == 200, f"scenario failed: {scenario}")
            result = response.json()
            require(result["status"] == "completed" and result["safe_mode"] is True, f"scenario incomplete: {scenario}")
            require(result["events_emitted"] == result["expected_events"], f"event count mismatch: {scenario}")
            require(result["timeline_step_f1"] >= 0.99, f"timeline ground-truth target missed: {scenario} F1={result['timeline_step_f1']}")
            if scenario == "slow-scan-theft":
                first = client.get("/api/alerts", params={"limit": 200}).json()
                scan_alerts = [a for a in first if "file_enumeration" in a.get("title", "").lower()]
                require(bool(scan_alerts), "slow scan discovery step did not alert")
                require(scan_alerts[0]["severity"] == "low", "slow scan discovery alert must be low severity")
            if result["ground_truth"] == "benign":
                require(result["benign_high_severity_alerts"] == 0, "benign high-severity alert emitted")
            else:
                require(result["time_to_first_alert_seconds"] is not None, f"missing first-alert timing: {scenario}")
            scenario_results.append({
                "scenario": scenario,
                "ground_truth": result["ground_truth"],
                "events_emitted": result["events_emitted"],
                "alerts_emitted": result["alerts_emitted"],
                "observed_detection_rate": result["observed_detection_rate"],
                "timeline_step_f1": result["timeline_step_f1"],
                "time_to_first_alert_seconds": result["time_to_first_alert_seconds"],
                "benign_high_severity_alerts": result["benign_high_severity_alerts"],
            })
        checks.append({"check": "all_four_scenarios_and_ordered_ground_truth_f1", "status": "pass"})

        malicious_run = client.post("/api/scenarios/credential-lateral-movement/run").json()
        incident_response = client.post("/api/incidents/reconstruct", json={"event_ids": malicious_run["event_ids"]})
        require(incident_response.status_code == 200, "incident reconstruction failed")
        incident = incident_response.json()
        incident_id = incident["id"]
        require(incident["evidence"]["event_count"] == len(malicious_run["event_ids"]), "incident evidence count mismatch")
        json_report = client.get(f"/api/incidents/{incident_id}/report?format=json")
        md_report = client.get(f"/api/incidents/{incident_id}/report?format=md")
        require(json_report.status_code == 200 and md_report.status_code == 200, "incident report export failed")
        require("Generated from MirageNet synthetic simulator data only." in md_report.text, "Markdown report safety footer missing")
        checks.append({"check": "incident_reconstruction_and_md_json_exports", "status": "pass"})

        old = client.get("/api/decoys").json()[0]
        rotation_response = client.post(f"/api/decoys/{old['id']}/burn")
        require(rotation_response.status_code == 200, "decoy rotation failed")
        rotation = rotation_response.json()
        require(rotation["status"] == "burned", "old decoy not marked burned")
        require(rotation["replacement"]["status"] == "deployed", "replacement not deployed")
        require(rotation["replacement"]["token"] != old["token"], "rotation reused token")
        checks.append({"check": "burn_and_fresh_token_rotation", "status": "pass"})

        evaluation = client.get("/api/eval")
        require(evaluation.status_code == 200, "evaluation endpoint failed")
        metrics = evaluation.json()
        require(metrics["measured"]["runs_total"] >= 4, "evaluation did not include scenario runs")
        checks.append({"check": "evaluation_metrics", "status": "pass"})

        report = {
            "project": "MirageNet",
            "verification_type": "isolated backend API smoke test",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "database": "temporary SQLite database; project database not modified",
            "result": "PASS",
            "checks_passed": len(checks),
            "checks_failed": 0,
            "checks": checks,
            "forge": {"created": forged["created"], "unique_tokens": len({d["token"] for d in decoys}),
                      "types": sorted({d["type"] for d in decoys}), "source_mode": forged["source_mode"]},
            "scenarios": scenario_results,
            "evaluation": metrics,
            "limitations": [
                "This is an API-level synthetic simulator smoke test, not browser-level end-to-end testing.",
                "Adaption vendor compatibility is not verified unless a documented compatible gateway is configured.",
                "Metrics are generated from synthetic scenarios and are not real-world detection efficacy claims.",
            ],
        }
        output = Path(__file__).resolve().parents[2] / "evidence" / "backend-smoke-results.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps({"result": report["result"], "checks_passed": report["checks_passed"], "evidence_file": str(output)}, indent=2))
    _tmp.cleanup()


if __name__ == "__main__":
    main()
