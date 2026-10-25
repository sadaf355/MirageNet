# MirageNet

MirageNet is a **sandbox-only cyber deception simulator**. It generates fictional decoy artifacts, records simulated file/auth/endpoint activity through a shared sensor pipeline, streams alerts over WebSockets, and reconstructs scenario timelines against ordered ground truth. It does not access real files, execute shell commands, scan networks, or use real credentials.

## Requirements
- Python 3.11 recommended
- Node.js 20+ and npm
- Optional: an Adaption API key for the official Adaption SDK. Without it, the labelled local cache is used.

## Start the backend
```bash
cd backend
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
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

## Correctness notes

- Evaluation normalizes `ground_truth_label` (`positive`/`negative`) into `malicious`/`benign`; this prevents recorded runs from silently disappearing from Evaluation Lab.
- Timeline F1 is calculated by ordered matching of persisted events against `data/scenarios/*.json`, requiring event type, host, and ATT&CK technique agreement. Benign runs have no positive timeline F1 and are shown as `n/a`.
- Sensor HTTP responses expose measured request/response duration in the `X-Sensor-Latency-Seconds` response header. This is local simulator endpoint latency, not production network latency.
- `evidence/webhook_siem_sample.json` is an illustrative synthetic JSON export shape; it is not an active webhook delivery configuration.
- Decoy enticement is fit across the full batch of decoys plus eight attacker-style queries, so the TF-IDF vocabulary and similarities are corpus-based rather than independently fit per template.
- `POST /api/reset` clears synthetic events, alerts, incidents, sessions, and old decoys, then creates and deploys a fresh 60-decoy demo inventory while retaining the seven-host topology.
- The first three decoys have explicit breadcrumb names for WS-01 credential note, JMP-01 SSH config, and DB-01 backup dump.
- Benign scenario timeline F1 is `null` (display as n/a), because the benign control has no positive attack timeline.

## Honey-credential login

`GET/POST /admin` on WEB-01 is a fictional admin login page. It accepts only credentials that exist inside a deployed decoy. A matching login records a `credential_used` auth event, links the decoy token, stitches the actor session, and raises a high-confidence alert. Any other login is rejected with a generic message and logged as a low-severity event. No real authentication, shell, or network calls are made.

In Intruder Play, use the **Login to admin portal** action with credentials discovered in a synthetic note to trigger the honey-credential flow and observe the alert in the live security monitor.

## Decorative 3D welcome hero

The welcome splash uses a React Three Fiber scene (`HeroScene.tsx`) rendering a seven-node rotating network island. A static CSS fallback is shown when WebGL is unavailable. The live operational topology in Live Network uses Cytoscape and is unaffected by the hero scene.

## Adaption SDK integration and evidence

MirageNet uses the official `adaption` Python SDK (`datasets.invent`, `datasets.get`, `datasets.download`, and `datasets.get_evaluation`) when `ADAPTION_API_KEY` is set in the backend environment. The exact Northwind Logistics brief is stored in `data/adaption_evidence/brief.txt`. Dataset IDs, row counts, evaluation status, and evaluation metrics are written to `data/adaption_evidence/job_manifest.json`.

Without an API key, the UI clearly labels the path as **CACHE**. `data/decoys.jsonl` is a filtered cache built from the uploaded prompt/completion export. Its row scores use a transparent local quality rubric because that export does not carry verifiable Adaption job metadata or per-row Adaption scores.

For a live run, set `ADAPTION_API_KEY` in the backend process environment (do not commit the key), restart the backend, then click the Adaption job button. For read-only inspection of an existing dataset, use:
```bash
cd backend
python scripts/run_adaption_live.py --read-only 804c2643-496f-4951-9ff8-f7814c73071b
```

For reproducible offline evaluation, use the labelled local session fixtures and **Replay session dataset** in Evaluation Lab.

## Honest limitations

- Adaption invent jobs were not completed locally due to API credit constraints (402 responses). The dataset ID `804c2643-496f-4951-9ff8-f7814c73071b` is user-provided evidence. Cache row quality scores are a local rubric, not Adaption row-level scores. See `data/adaption_evidence/job_manifest.json` and `backend/evidence/ADAPTION_USAGE.md` for details.
- The executive-summary paragraph in incident reports uses a plain template by default. Set `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` in the backend environment to enable LLM generation; the template is always the fallback.
- Auto burn-and-rotate fires at a synthetic enticement threshold of 0.80 and replaces the decoy token in Live Alerts. Both operate only on fictional MirageNet data.

## Repository layout

```
MirageNet/
├── backend/
│   ├── app/            # FastAPI application
│   ├── scripts/        # smoke_test.py, run_adaption_live.py
│   ├── tests/          # pytest suite
│   ├── evidence/       # ADAPTION_USAGE.md (referenced by backend Dockerfile)
│   └── requirements.txt
├── data/
│   ├── decoys.jsonl             # decoy cache (source of truth)
│   ├── network.json             # topology
│   ├── org_profiles/            # Northwind Logistics profile
│   ├── scenarios/               # ground-truth evaluation scenarios
│   └── adaption_evidence/       # Adaption SDK evidence artefacts
├── evidence/           # smoke results, screenshots, SIEM sample
├── frontend/
│   ├── src/            # React + TypeScript UI
│   ├── index.html
│   ├── vite.config.ts
│   └── .env.example    # VITE_API_BASE_URL, VITE_WS_BASE_URL
├── .env.example        # ADAPTION_API_KEY, DATABASE_URL, CORS_ORIGINS, etc.
├── Dockerfile          # root build (backend + data, used by Render)
├── docker-compose.yml
├── render.yaml
├── railway.json
└── start.sh / start.ps1
```
