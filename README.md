# MirageNet

MirageNet is a **sandbox-only cyber deception simulator**. It generates fictional decoy artifacts, records simulated file/auth/endpoint activity through a shared sensor pipeline, streams alerts over WebSockets, and reconstructs scenario timelines against ordered ground truth. It does not access real files, execute shell commands, scan networks, or use real credentials.

## Requirements
- Python 3.11 recommended
- Node.js 20+ and npm
- Optional: an Adaption API key for the official Adaption SDK. Without it, the labeled local cache is used.

## Start the backend
```bash
cd backend
python -m venv .venv
# Windows PowerShell: .venv\\Scripts\\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```
Backend API docs: http://127.0.0.1:8000/docs

## Start the frontend
In a second terminal:
```bash
cd frontend
npm install
npm run dev
```
Open the URL printed by Vite. If the API is hosted elsewhere, set `VITE_API_BASE_URL` and `VITE_WS_BASE_URL` in `frontend/.env.local`; the WebSocket base should be `ws://host:port` or `wss://host:port`.

## Demo flow
1. Open Decoy Lab and forge at least 60 artifacts.
2. Deploy the staged artifacts.
3. Open Intruder Play, select a synthetic file, and read it. The action is sent through the shared sensor pipeline and should appear in Live Alerts and the security monitor.
4. Run the scenario suite in Evaluation Lab, including imperfect replays and benign controls.
5. Inspect incidents and export Markdown/JSON reports.

## Ground truth and evaluation
Ordered step definitions are in `data/scenarios/*.json`. Scenario steps use simulated timestamps separated by two minutes. The API reports ordered event/host/technique matching metrics alongside observed alerts. These are simulator metrics, not claims about real-world detection performance. The eight-query TF-IDF score is a heuristic ranking signal, not a calibrated probability.

## Tests
```bash
cd backend
PYTHONPATH=. pytest -q
PYTHONPATH=. python scripts/smoke_test.py
```
The smoke test uses a temporary SQLite database and asserts the main workflows, ground-truth matching, and low-severity slow-scan discovery behavior.

## Safety boundaries
All hostnames, files, tokens, events, and scenario actions are fictional and local to the simulator. No real operating-system filesystem or network activity is performed.

## Demo-ready operator UI

The frontend includes a guided **Run full demo** action that executes the four named synthetic scenarios in order and then opens Evaluation Lab. Incident reconstruction supports linked timeline/edge selection, ATT&CK technique badges, an evidence inspector, and step-controlled host-path playback. In Live Network, select a host to inspect matching decoys/alerts or select an edge to inspect its configured topology evidence. Intruder Play includes a read-only synthetic file browser, content preview, safe simulated terminal commands (`help`, `list`, `status`, `clear`), live WebSocket monitor, and reset control. Settings displays local API health and accessibility preferences.

Framer Motion provides page and path transitions. The interface respects the OS `prefers-reduced-motion` setting. UI styling follows the existing dark SOC design tokens and component classes; Tailwind is not installed in this project, so these are CSS-based components rather than Tailwind utility classes.

### Demo sequence
1. Start the backend and frontend as described above.
2. Forge/deploy synthetic decoys in Decoy Lab if the environment starts empty.
3. Click **Run full demo** for the core scenario walkthrough, then use Evaluation Lab for the broader benign/imperfect suite and session replay.
4. Open Incidents, reconstruct a story, select timeline entries/edges, and open the evidence inspector.
5. In Live Network, click a host or edge. In Intruder Play, read a synthetic artifact and observe the monitor/terminal output.

The full-demo runner sends scenario requests to the local simulator API. All actions remain synthetic; the terminal does not execute shell commands and topology edges are not claims of observed real traffic.


## Phase 6–8 correctness notes

- Evaluation normalizes `ground_truth_label` (`positive`/`negative`) into `malicious`/`benign`; this prevents recorded runs from silently disappearing from Evaluation Lab.
- Timeline F1 is calculated by ordered matching of persisted events against `data/scenarios/*.json`, requiring event type, host, and ATT&CK technique agreement. Benign runs have no positive timeline F1 and are shown as `n/a`.
- Sensor HTTP responses expose measured request/response duration in the `X-Sensor-Latency-Seconds` response header. This is local simulator endpoint latency, not production network latency.
- `backend/tests/test_phase8_acceptance.py` asserts the three malicious scenario detection targets (100%), ordered timeline F1 (>= 0.90), zero benign high-severity alerts, latency header presence, and ground-truth normalization.
- `evidence/webhook_siem_sample.json` is an illustrative synthetic JSON export shape; it is not an active webhook delivery configuration.
- Decoy enticement is now fit across the full batch of decoys plus eight attacker-style queries, so the TF-IDF vocabulary and similarities are corpus-based rather than independently fit per template.

## Phase 9: correctness, reset, and SIEM export

- `POST /api/reset` clears synthetic events, alerts, incidents, sessions, and old decoys, then creates and deploys a fresh 60-decoy demo inventory while retaining the seven-host topology.
- The UI's **Reset demo** action asks for confirmation before invoking the endpoint.
- `GET /api/alerts/{alert_id}/siem` returns a normalized SIEM/webhook JSON event for one alert.
- Evaluation normalizes host casing when comparing scenario steps with `data/scenarios/*.json` ground truth.
- The first three decoys have explicit breadcrumb names for WS-01 credential note, JMP-01 SSH config, and DB-01 backup dump.
- Benign scenario timeline F1 is `null` (display as n/a), because the benign control has no positive attack timeline.

## Verification notes

Backend tests are run with `cd backend && PYTHONPATH=. pytest -q`. Frontend installation/build status and errors are recorded in `FRONTEND_BUILD_RESULTS.md`. All activity remains synthetic and local.


## Decorative 3D welcome hero
The Phase 9 backend/API fixes are retained in this merged build. The Route A React Three Fiber hero is lazy-loaded on the welcome splash; the splash dismissal is remembered for the current browser session. The live operational topology remains Cytoscape. A static fallback is shown when WebGL is unavailable.

Optional Route B: install Blender 3.6+ and run `blender --background --python tools/blender/generate_hero.py`. The script supports Blender 3.6/4.x emission socket names and exports meshes only; Three.js supplies runtime lighting. The GLB is not bundled until generated locally.

## Adaption SDK integration and evidence

MirageNet now uses the official `adaption` Python SDK (`datasets.invent`, `datasets.get`, `datasets.download`, and `datasets.get_evaluation`) when `ADAPTION_API_KEY` is set in the backend environment. The exact Northwind Logistics brief is stored in `data/adaption_evidence/brief.txt`. Run **Adaption · Invent a Dataset** in Decoy Lab to start a 200-row job; run **Generate labelled sessions** to create session trajectories for the Evaluation Lab black-box replay button. Dataset IDs, row counts, evaluation status, and evaluation metrics are written to `data/adaption_evidence/job_manifest.json`.

Without an API key, the UI clearly labels the path as **CACHE**. `data/decoys.jsonl` is a filtered cache built from the uploaded prompt/completion export. Its row scores use a transparent local quality rubric because that export does not carry verifiable Adaption job metadata or per-row Adaption scores. Adaption's returned dataset-level evaluation score is displayed separately and is never copied onto every row as if it were a row-level score. The Decoy Lab accepts a real PNG/JPEG screenshot of the Adaption job UI and stores it in `data/adaption_evidence/`; the screenshot must be captured from the real provider UI, not fabricated.

For a live run, set `ADAPTION_API_KEY` in the backend process environment (do not commit the key), restart the backend, then click the Adaption job button. The provider may consume credits. If the key is absent, no live job is started. For reproducible offline evaluation, use the labelled local session fixtures and **Replay session dataset**. Evaluation reports event-derived timeline F1, actual TF-IDF cosine ranking against the attacker query set, per-scenario metrics, latency buckets, and a run-level confusion matrix. The deliberately imperfect scenarios include a missing step, an extra benign step, and reordered steps; benign controls include scanner, backup, health-check, and admin-login behavior.

## Phase 5 differentiators

This build adds two evidence-backed differentiators: high-confidence synthetic decoy auto burn-and-rotate (threshold 0.80, replacement token shown in Live Alerts) and ATT&CK-sequence adversary-playbook replay. See `PHASE5_INNOVATION.md` for behavior, provenance, and verification details. Both operate only on fictional MirageNet data.
