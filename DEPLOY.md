# MirageNet Deployment Guide

This guide describes how to deploy MirageNet to production hosting services (such as Render/Railway for the backend and Vercel for the frontend) so judges and operators can access a live URL.

## Architecture

- **Backend**: FastAPI + SQLAlchemy + SQLite running inside a Python 3.11 Docker container.
- **Frontend**: React + Vite + TypeScript single-page application served via Vercel (or Docker Nginx).
- **Decoys and Topology**: Fictional, synthetic sandbox-only simulation data.

---

## 1. Backend Deployment (Render or Railway)

### Option A: Render (recommended via `render.yaml`)

1. Connect your GitHub repository to Render (https://dashboard.render.com).
2. Choose **Blueprints** -> **New Blueprint Instance**.
3. Select this repository. Render will automatically detect `render.yaml`.
4. Configure the following environment variables on the Render service:
   - `PORT`: `10000` (set automatically by Render)
   - `DATABASE_URL`: `sqlite:////var/data/miragenet.db` (persistent disk mount)
   - `CORS_ORIGINS`: `https://<your-vercel-domain>.vercel.app,http://localhost:5173`
   - `ADAPTION_API_KEY`: *(Optional)* Your Adaption API key if you want live AI dataset generation. If omitted, MirageNet runs in reproducible `cache` mode.
5. Deploy. When deployed, note your backend URL (e.g. `https://miragenet-api.onrender.com`).
6. Verify deployment by visiting `https://miragenet-api.onrender.com/api/health`.

### Option B: Railway

1. In Railway (https://railway.app), create a new project from your GitHub repo.
2. Railway detects `backend/Dockerfile` using `railway.json`.
3. Under **Variables**, add:
   - `PORT`: `8000`
   - `DATABASE_URL`: `sqlite:////app/data/miragenet.db` (or mount a Railway Volume to `/app/data`)
   - `CORS_ORIGINS`: `*` (or your frontend domain)
   - `ADAPTION_API_KEY`: *(Optional)*
4. Generate a public domain under **Settings -> Networking**.

---

## 2. Frontend Deployment (Vercel)

1. Import the repository into Vercel (https://vercel.com).
2. Set **Root Directory** to `frontend`.
3. Framework Preset: **Vite**.
4. Build Command: `npm run build`
5. Output Directory: `dist`
6. Under **Environment Variables**, configure:
   - `VITE_API_BASE_URL`: `https://miragenet-api.onrender.com` (your backend URL without trailing slash)
   - `VITE_WS_BASE_URL`: `wss://miragenet-api.onrender.com` (WebSocket secure URL for live alert streaming)
7. Deploy. `frontend/vercel.json` ensures all SPA routes rewrite to `/index.html`.

---

## 3. Environment Variables Summary

### Backend (`.env` or Cloud Provider Settings)

| Variable | Required | Default | Description |
|---|---|---|---|
| `PORT` | Optional | `8000` | Port for the Uvicorn server |
| `DATABASE_URL` | Optional | `sqlite:///./miragenet.db` | SQLAlchemy DB connection string (use a persistent path for SQLite in containers) |
| `CORS_ORIGINS` | Optional | `*` or comma-separated list | Allowed origins for web and WebSocket clients |
| `ADAPTION_API_KEY` | Optional | *(empty)* | Secret key for live Adaption SDK API. If omitted, MirageNet uses local labeled cache |

### Frontend (`.env.production` or Vercel Settings)

| Variable | Required | Default | Description |
|---|---|---|---|
| `VITE_API_BASE_URL` | Yes (for prod) | `""` (same origin) | Full HTTPS URL of the backend API (e.g. `https://miragenet-api.onrender.com`) |
| `VITE_WS_BASE_URL` | Yes (for prod) | `wss://<host>` | Full WSS URL for the alert WebSocket (e.g. `wss://miragenet-api.onrender.com`) |

---

## 4. First-Boot Behavior

When booted against an empty database:
1. MirageNet creates database tables (`miragenet.db`).
2. Seeds the 7 fictional network hosts (`WEB-01`, `WS-01`, `FS-01`, `JMP-01`, `DB-01`, `GIT-01`, `BKP-01`).
3. If no decoys exist, auto-forges 60 synthetic artifacts from `data/decoys.jsonl` and marks them `deployed`.
4. The system is immediately ready for simulation and judge demonstration.

---

## 5. Local Docker Verification

To test the containerized backend locally:

```bash
docker build -t miragenet-backend -f backend/Dockerfile .
docker run --rm -p 8000:8000 -e PORT=8000 miragenet-backend
curl http://127.0.0.1:8000/api/health
```
