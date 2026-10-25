"""
Run the full Adaption SDK live flow for MirageNet.

Executes:
  1. datasets.invent() for decoy corpus (brief.txt)
  2. Poll to completion
  3. datasets.get_evaluation() until resolved
  4. Download JSONL -> rebuild data/decoys.jsonl
  5. datasets.invent() for session trajectories (session_brief.txt)
  6. Poll session dataset to completion; download rows
  7. Save old sessions to sessions_local_fixtures.jsonl
  8. Save new Adaption sessions to sessions.jsonl
  9. Write all real IDs/scores into job_manifest.json

Run from backend/ with the venv active:
  python scripts/run_adaption_live.py
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

# Add backend app to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Load .env so we get ADAPTION_API_KEY
env_path = Path(__file__).resolve().parents[1] / ".env"
if env_path.exists():
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

from app.services.adaption_integration import (
    BRIEF_PATH, SESSION_BRIEF_PATH, EVIDENCE_DIR, CACHE_PATH,
    _sdk_client, _wait_dataset, _download_rows, _normalize_record,
    write_manifest, _plain, _load_manifest, _json_candidate
)


def main() -> None:
    api_key = os.getenv("ADAPTION_API_KEY", "").strip()
    if not api_key:
        print("ERROR: ADAPTION_API_KEY is not set in backend/.env. Stopping at step 2.", flush=True)
        sys.exit(1)

    print(f"[OK] ADAPTION_API_KEY is set ({api_key[:8]}...)", flush=True)
    client = _sdk_client()

    # STEP 1: Invent decoy dataset
    brief = BRIEF_PATH.read_text(encoding="utf-8").strip()
    print(f"\n[STEP 1] Inventing decoy dataset ({len(brief)} chars brief) ...", flush=True)
    created = client.datasets.invent(
        dataset_prompt=brief,
        rows=200,
        name="MirageNet Northwind Logistics decoy artifacts",
        training_type="instruction_dataset"
    )
    decoy_dataset_id = str(getattr(created, "dataset_id", "") or "")
    if not decoy_dataset_id:
        print("ERROR: Adaption returned no dataset_id for decoy job.", flush=True)
        sys.exit(1)
    print(f"[STEP 1] Decoy dataset created: {decoy_dataset_id}", flush=True)
    write_manifest({
        "status": "adaption_running",
        "dataset_id": decoy_dataset_id,
        "dataset_name": "MirageNet Northwind Logistics decoy artifacts",
        "exact_brief": brief,
        "requested_rows": 200,
        "provider": "Adaption SDK",
    })

    # STEP 2: Poll decoy dataset to completion
    print(f"[STEP 2] Polling decoy dataset {decoy_dataset_id} ...", flush=True)
    dataset = _wait_dataset(client, decoy_dataset_id, timeout=1200)
    print(f"[STEP 2] Dataset status: {getattr(dataset, 'status', '?')}", flush=True)

    # STEP 3: Download JSONL rows
    print(f"[STEP 3] Downloading decoy JSONL rows ...", flush=True)
    raw_rows = _download_rows(client, decoy_dataset_id)
    print(f"[STEP 3] Downloaded {len(raw_rows)} raw rows", flush=True)

    # STEP 4: Call dataset evaluation
    print(f"[STEP 4] Requesting dataset evaluation ...", flush=True)
    evaluation_data = None
    evaluation_status = "unavailable"
    score_before = None
    score_after = None
    try:
        deadline = time.monotonic() + 600
        while time.monotonic() < deadline:
            evaluation = client.datasets.get_evaluation(decoy_dataset_id)
            evaluation_status = str(getattr(evaluation, "status", "unknown"))
            quality = _plain(getattr(evaluation, "quality", None))
            if isinstance(quality, dict):
                evaluation_data = quality
                sb = quality.get("score_before")
                sa = quality.get("score_after")
                score_before = float(sb) if isinstance(sb, (int, float)) else None
                score_after = float(sa) if isinstance(sa, (int, float)) else None
                # Try nested structures
                if score_before is None and score_after is None:
                    for k, v in quality.items():
                        if isinstance(v, dict):
                            sb2 = v.get("score_before") or v.get("before")
                            sa2 = v.get("score_after") or v.get("after")
                            if isinstance(sb2, (int, float)):
                                score_before = float(sb2)
                            if isinstance(sa2, (int, float)):
                                score_after = float(sa2)
            print(f"  evaluation_status={evaluation_status}, score_before={score_before}, score_after={score_after}", flush=True)
            if evaluation_status in ("succeeded", "failed", "skipped", "completed"):
                break
            time.sleep(8)
    except Exception as exc:
        evaluation_data = {"error": str(exc)}
        print(f"[STEP 4] Evaluation error: {exc}", flush=True)
    print(f"[STEP 4] Final evaluation_status={evaluation_status}", flush=True)
    print(f"[STEP 4] score_before={score_before}, score_after={score_after}", flush=True)
    print(f"[STEP 4] Full quality dict: {json.dumps(evaluation_data, indent=2, default=str)}", flush=True)

    # STEP 5: Normalize and write decoys.jsonl
    threshold = float(os.getenv("MIRAGENET_MIN_DECOY_QUALITY", "0.85"))
    normalized = []
    for idx, row in enumerate(raw_rows):
        item = _normalize_record(row, idx, "adaption_generated")
        if item:
            normalized.append(item)
    retained = [r for r in normalized if r["quality_score"] >= threshold]
    retained = retained[:200]
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CACHE_PATH.open("w", encoding="utf-8") as f:
        for row in retained:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"[STEP 5] Wrote {len(retained)} retained decoys to data/decoys.jsonl "
          f"(valid={len(normalized)}, raw={len(raw_rows)})", flush=True)

    # STEP 6: Update manifest with real decoy IDs/scores
    write_manifest({
        "status": "adaption_succeeded",
        "provider": "Adaption SDK",
        "dataset_id": decoy_dataset_id,
        "dataset_kind": getattr(dataset, "kind", "invented"),
        "exact_brief": brief,
        "requested_rows": 200,
        "generated_rows": len(raw_rows),
        "valid_rows": len(normalized),
        "retained_rows": len(retained),
        "dropped_rows": max(0, len(raw_rows) - len(retained)),
        "quality_threshold": threshold,
        "evaluation_status": evaluation_status,
        "dataset_quality": evaluation_data,
        "score_before": score_before,
        "score_after": score_after,
        "dataset_quality_score_before_0_to_10": score_before,
        "dataset_quality_score_after_0_to_10": score_after,
        "row_quality_source": "provider_row_score_when_present_else_cache_rubric",
        "screenshot": "data/adaption_evidence/adaption_job_screenshot.jpg",
    })
    print(f"[STEP 6] Manifest updated with dataset_id={decoy_dataset_id}", flush=True)

    # STEP 7: Backup existing session fixtures
    sessions_path = EVIDENCE_DIR / "sessions.jsonl"
    fixtures_path = EVIDENCE_DIR / "sessions_local_fixtures.jsonl"
    if sessions_path.exists() and not fixtures_path.exists():
        fixtures_path.write_bytes(sessions_path.read_bytes())
        print(f"[STEP 7] Backed up old fixtures -> sessions_local_fixtures.jsonl", flush=True)
    else:
        print(f"[STEP 7] sessions_local_fixtures.jsonl already exists -- skipping backup", flush=True)

    # STEP 8: Invent session dataset
    session_brief_text = SESSION_BRIEF_PATH.read_text(encoding="utf-8").strip() if SESSION_BRIEF_PATH.exists() else (
        "Generate labelled synthetic cybersecurity intruder-session trajectories for the fictional Northwind Logistics "
        "MirageNet sandbox. Return one JSON object per row with session_id, label (malicious or benign), scenario, "
        "and separate ground_truth_steps from observed_steps. Each step must have event_type, host (one of WEB-01, WS-01, FS-01, JMP-01, DB-01, GIT-01, BKP-01), "
        "action, and technique (ATT&CK ID or null). observed_steps are black-box event input; ground_truth_steps are labels for post-hoc scoring only. "
        "Include realistic imperfect trajectories: one missed step, one extra benign health-check step, and one reordered step. "
        "Include scanner, backup, health-check, and admin-login benign sessions. All activity is fictional simulator input, "
        "uses no real hosts, credentials, endpoints, or real-world targeting instructions.")
    print(f"\n[STEP 8] Inventing session dataset ({len(session_brief_text)} chars brief) ...", flush=True)
    sess_created = client.datasets.invent(
        dataset_prompt=session_brief_text,
        rows=30,
        name="MirageNet labelled intruder session trajectories",
        training_type="instruction_dataset"
    )
    session_dataset_id = str(getattr(sess_created, "dataset_id", "") or "")
    if not session_dataset_id:
        print("ERROR: Adaption returned no dataset_id for session job.", flush=True)
        sys.exit(1)
    print(f"[STEP 8] Session dataset created: {session_dataset_id}", flush=True)
    write_manifest({
        "session_dataset_status": "adaption_running",
        "session_dataset_id": session_dataset_id,
        "session_requested_rows": 30,
        "session_brief": session_brief_text,
    })

    # STEP 9: Poll and download session dataset
    print(f"[STEP 9] Polling session dataset {session_dataset_id} ...", flush=True)
    _wait_dataset(client, session_dataset_id, timeout=1200)
    sess_raw = _download_rows(client, session_dataset_id)
    print(f"[STEP 9] Downloaded {len(sess_raw)} session rows", flush=True)

    kept = []
    for idx, row in enumerate(sess_raw):
        candidate = row.get("completion") or row.get("response") or row.get("output") or row
        if isinstance(candidate, str):
            candidate = _json_candidate(candidate) or {}
        if isinstance(candidate, dict):
            obs = candidate.get("observed_steps") or candidate.get("steps", [])
            gt = candidate.get("ground_truth_steps") or candidate.get("steps", [])
            label = candidate.get("label", "")
            if isinstance(obs, list) and label in {"malicious", "benign"}:
                candidate.setdefault("observed_steps", obs)
                candidate.setdefault("ground_truth_steps", gt)
                candidate.setdefault("session_id", f"adaption-session-{idx:03d}")
                candidate["session_dataset_id"] = session_dataset_id
                kept.append(candidate)

    with sessions_path.open("w", encoding="utf-8") as f:
        for row in kept:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"[STEP 9] Wrote {len(kept)} sessions to sessions.jsonl", flush=True)

    # STEP 10: Final manifest update
    write_manifest({
        "session_dataset_id": session_dataset_id,
        "session_dataset_status": "adaption_generated",
        "session_generated_rows": len(sess_raw),
        "session_retained_rows": len(kept),
        "session_brief": session_brief_text,
    })
    print(f"\n[DONE] Full Adaption live run complete.", flush=True)
    print(f"       decoy dataset_id  : {decoy_dataset_id}", flush=True)
    print(f"       session dataset_id: {session_dataset_id}", flush=True)
    print(f"       score_before      : {score_before}", flush=True)
    print(f"       score_after       : {score_after}", flush=True)
    print(f"       decoys retained   : {len(retained)}", flush=True)
    print(f"       sessions retained : {len(kept)}", flush=True)


if __name__ == "__main__":
    main()
