"""routers/sensors.py — Thin HTTP layer.

All event-recording logic lives in sensor_pipeline/record.py.
This file only handles HTTP concerns: request parsing, host validation, response shape.

Honey-login endpoints:
  GET  /admin  — fictional login form (HTML)
  POST /admin  — fictional credential check against deployed decoy credential_note artifacts
"""
from __future__ import annotations

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Decoy, Event, Node
from app.services.sensor_pipeline.record import record_event, BENIGN_ACTORS

router = APIRouter(tags=["synthetic sensors"])


# ──────────────────────────────────────────────────────────────────────────────
# Pydantic payload models (kept here; imported by play.py, scenarios.py, etc.)
# ──────────────────────────────────────────────────────────────────────────────

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


# ──────────────────────────────────────────────────────────────────────────────
# Thin helper: validates host, delegates to record_event
# ──────────────────────────────────────────────────────────────────────────────

async def _record(event_type: str, payload: SensorPayload, db: Session,
                  decoy_sensitive: bool, auth_event: bool = False) -> dict:
    host = db.get(Node, payload.host_id)
    if host is None:
        raise HTTPException(status_code=404, detail="Host is not part of the synthetic network")
    if payload.decoy_id:
        chk = db.get(Decoy, payload.decoy_id)
        if chk is None:
            raise HTTPException(status_code=404, detail="Synthetic decoy not found")
        if payload.token and payload.token != chk.token:
            raise HTTPException(status_code=400, detail="Tracking token does not match the selected decoy")
    try:
        return await record_event(
            event_type=event_type,
            actor_id=payload.actor_id,
            host_id=payload.host_id,
            decoy_id=payload.decoy_id,
            token=payload.token,
            action=payload.action,
            credential_used=payload.credential_used,
            breadcrumb_step=payload.breadcrumb_step,
            benign=payload.benign,
            metadata=payload.metadata,
            simulated_timestamp=payload.simulated_timestamp,
            db=db,
            decoy_sensitive=decoy_sensitive,
            auth_event=auth_event,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ──────────────────────────────────────────────────────────────────────────────
# Standard sensor endpoints
# ──────────────────────────────────────────────────────────────────────────────

@router.post("/api/sensor/file")
async def file_sensor(payload: SensorPayload, db: Session = Depends(get_db)):
    return await _record("file_read", payload, db, decoy_sensitive=True)


@router.post("/api/sensor/auth")
async def auth_sensor(payload: SensorPayload, db: Session = Depends(get_db)):
    return await _record("auth_attempt", payload, db, decoy_sensitive=True, auth_event=True)


@router.post("/api/sensor/endpoint")
async def endpoint_sensor(payload: SensorPayload, db: Session = Depends(get_db)):
    return await _record("endpoint_activity", payload, db,
                         decoy_sensitive=bool(payload.decoy_id or payload.token))


@router.post("/api/sensor/touch")
async def simulate_touch(payload: TouchPayload, db: Session = Depends(get_db)):
    decoy = db.get(Decoy, payload.decoy_id)
    if decoy is None:
        raise HTTPException(status_code=404, detail="Synthetic decoy not found")
    if decoy.status != "deployed":
        raise HTTPException(status_code=409,
                            detail=f"Decoy must be deployed before touch (status={decoy.status})")
    sensor_payload = SensorPayload(
        actor_id=payload.actor_id, host_id=decoy.host_id,
        decoy_id=decoy.id, token=decoy.token,
        action=payload.action, credential_used=payload.credential_used,
        breadcrumb_step=payload.breadcrumb_step, benign=payload.benign,
        simulated_timestamp=payload.simulated_timestamp,
        metadata={"decoy_name": decoy.name, "decoy_type": decoy.decoy_type},
    )
    return await _record("file_read", sensor_payload, db, decoy_sensitive=True,
                         auth_event=payload.credential_used)


@router.get("/api/events")
def list_events(limit: int = 50, db: Session = Depends(get_db)):
    rows = (db.query(Event).order_by(Event.timestamp.desc())
            .limit(max(1, min(limit, 200))).all())
    return [{"id": e.id, "event_type": e.event_type, "host_id": e.host_id,
             "actor_id": e.actor_id, "timestamp": e.timestamp.isoformat(),
             "evidence": e.evidence} for e in rows]


# ──────────────────────────────────────────────────────────────────────────────
# Honey-login: fictional WEB-01 admin portal
# ──────────────────────────────────────────────────────────────────────────────

_HONEY_LOGIN_PAGE = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Northwind Logistics — Admin Portal [FICTIONAL DECOY]</title>
  <style>
    body{font-family:monospace;background:#0d1117;color:#58a6ff;display:flex;
         flex-direction:column;align-items:center;justify-content:center;min-height:100vh;margin:0}
    .box{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:2rem;width:340px}
    h1{font-size:1.1rem;color:#e6edf3;margin:0 0 .5rem}
    .badge{font-size:.65rem;color:#f85149;background:#2d1a1a;border:1px solid #f85149;
           border-radius:4px;padding:2px 6px;display:inline-block;margin-bottom:1rem}
    label{font-size:.8rem;color:#8b949e;display:block;margin:.6rem 0 .2rem}
    input{width:100%;box-sizing:border-box;background:#0d1117;border:1px solid #30363d;
          color:#e6edf3;padding:.4rem .6rem;border-radius:4px;font-family:monospace}
    button{margin-top:1rem;width:100%;background:#238636;color:#fff;border:none;
           padding:.5rem;border-radius:4px;cursor:pointer;font-family:monospace}
    .note{font-size:.7rem;color:#484f58;margin-top:1rem;text-align:center}
    .err{color:#f85149;font-size:.8rem;margin-top:.5rem}
  </style>
</head>
<body>
  <div class="box">
    <div class="badge">⚠ FICTIONAL DECOY — NOT A REAL ADMIN PANEL</div>
    <h1>Northwind Logistics<br>Internal Admin Portal</h1>
    <form method="POST" action="/admin">
      <label>Username</label>
      <input id="admin-username" name="username" type="text" autocomplete="off" required>
      <label>Password</label>
      <input id="admin-password" name="password" type="password" autocomplete="off" required>
      <button id="admin-login-btn" type="submit">Log in</button>
    </form>
    <p class="note">Sandbox only · No real authentication · All activity is logged</p>
  </div>
</body>
</html>
"""

_HONEY_DASHBOARD_PAGE = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Admin Dashboard [FICTIONAL DECOY]</title>
  <style>
    body{{font-family:monospace;background:#0d1117;color:#58a6ff;padding:2rem;margin:0}}
    .badge{{color:#f85149;border:1px solid #f85149;border-radius:4px;
            padding:2px 8px;font-size:.7rem;display:inline-block;margin-bottom:1rem}}
    h1{{color:#e6edf3;font-size:1.2rem}}
    table{{border-collapse:collapse;width:100%;margin-top:1rem;font-size:.85rem}}
    th,td{{text-align:left;padding:.4rem .7rem;border-bottom:1px solid #21262d}}
    th{{color:#8b949e}}
    .note{{color:#484f58;font-size:.75rem;margin-top:2rem}}
  </style>
</head>
<body>
  <div class="badge">⚠ FICTIONAL DECOY DASHBOARD — SANDBOX ONLY</div>
  <h1>Welcome, {username}</h1>
  <p style="color:#8b949e;font-size:.85rem">You authenticated with a honey credential.
  This access has been logged. No real systems were accessed.</p>
  <table>
    <tr><th>Host</th><th>Role</th><th>Status</th></tr>
    {rows}
  </table>
  <p class="note">
    This is a fictional admin panel generated by MirageNet.<br>
    All displayed data is synthetic. No real network, credentials, or systems are involved.<br>
    Alert ID: <code>{alert_id}</code>
  </p>
</body>
</html>
"""


from app.services.sensor_pipeline.sensors import match_credential as _match_credential


@router.get("/admin", include_in_schema=False)
async def honey_login_get(
    request: Request,
    actor_id: str | None = None,
    db: Session = Depends(get_db),
):
    """Fictional admin login lure — records GET probe, serves login page or JSON telemetry."""
    host = db.query(Node).filter(Node.hostname == "WEB-01").first()
    act = actor_id or "web-probe"
    result = None
    if host:
        result = await record_event(
            event_type="endpoint_activity",
            actor_id=act,
            host_id=host.id,
            decoy_id=None, token=None,
            action="open_honey_admin_page",
            credential_used=False, breadcrumb_step=1,
            benign=False,
            metadata={"sensor": "honey_admin_get", "scenario": "web-lure-demo", "force_alert": True},
            simulated_timestamp=None,
            db=db, decoy_sensitive=True, auth_event=False,
        )
    accept = request.headers.get("accept", "")
    if actor_id is not None or "application/json" in accept:
        return {
            "mode": "synthetic-sandbox-only",
            "endpoint": "/admin",
            "message": "Fictional admin portal lure — no login or admin action is available.",
            "telemetry": result,
        }
    return HTMLResponse(content=_HONEY_LOGIN_PAGE, status_code=200)


@router.post("/admin", response_class=HTMLResponse, include_in_schema=False)
async def honey_login_post(
    username: str = Form(...),
    password: str = Form(...),
    actor_id: str = Form(default="honey-login-actor"),
    db: Session = Depends(get_db),
):
    """
    Fictional honey-credential login.

    Accepts ONLY credentials that exist inside a deployed credential_note decoy.
    - Match  → high-confidence alert, auth event (credential_used=True), decoy dashboard.
    - No match → low-severity log event, generic rejection message.
    No real authentication, no real shell, no real network calls.
    """
    host = db.query(Node).filter(Node.hostname == "WEB-01").first()
    if host is None:
        return HTMLResponse("<p>Fictional host WEB-01 not seeded.</p>", status_code=503)

    is_benign_actor = actor_id in BENIGN_ACTORS
    matched_decoy = _match_credential(username, password, db)

    if matched_decoy:
        # ── HIT: credential found in a deployed decoy ─────────────────────────
        # Build a node table for the dashboard
        nodes = db.query(Node).all()
        rows_html = "".join(
            f"<tr><td>{n.hostname}</td><td>{n.role}</td>"
            f"<td style='color:#3fb950'>online (simulated)</td></tr>"
            for n in nodes
        )
        result = await record_event(
            event_type="auth_attempt",
            actor_id=actor_id,
            host_id=host.id,
            decoy_id=matched_decoy.id,
            token=matched_decoy.token,
            action="honey_credential_login",
            credential_used=True,
            breadcrumb_step=2,
            benign=is_benign_actor,
            metadata={
                "sensor": "honey_admin_post",
                "honey_login": True,
                "matched_decoy_id": matched_decoy.id,
                "matched_decoy_name": matched_decoy.name,
                "username_presented": username,
                "force_alert": True,
            },
            simulated_timestamp=None,
            db=db, decoy_sensitive=True, auth_event=True,
        )
        alert_id = (result.get("alert") or {}).get("id", "n/a")
        dashboard = _HONEY_DASHBOARD_PAGE.format(
            username=username,
            rows=rows_html,
            alert_id=alert_id,
        )
        return HTMLResponse(content=dashboard, status_code=200)

    else:
        # ── MISS: reject with generic message, log low-severity event ─────────
        await record_event(
            event_type="auth_attempt",
            actor_id=actor_id,
            host_id=host.id,
            decoy_id=None, token=None,
            action="failed_honey_login",
            credential_used=False,
            breadcrumb_step=1,
            benign=is_benign_actor,
            metadata={
                "sensor": "honey_admin_post",
                "honey_login": True,
                "credential_match": False,
                "username_presented": username,
                "force_low_alert": True,
            },
            simulated_timestamp=None,
            db=db, decoy_sensitive=True, auth_event=False,
        )
        fail_page = """\
<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>Login failed</title>
<style>body{font-family:monospace;background:#0d1117;color:#f85149;
display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0}
.box{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:2rem;width:340px;text-align:center}
a{color:#58a6ff}</style></head>
<body><div class="box"><p>Invalid credentials.</p>
<p style="color:#8b949e;font-size:.8rem">This attempt has been logged.</p>
<a href="/admin">Try again</a></div></body></html>"""
        return HTMLResponse(content=fail_page, status_code=401)


# ──────────────────────────────────────────────────────────────────────────────
# Existing web lures (backup.zip kept for parity)
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/backup.zip")
async def fake_backup_endpoint(actor_id: str = "demo-web-probe", db: Session = Depends(get_db)):
    """Fictional backup lure; returns metadata only, not an archive or real data."""
    host = db.query(Node).filter(Node.hostname == "WEB-01").first()
    if host is None:
        raise HTTPException(status_code=404, detail="Synthetic WEB-01 host is not seeded")
    result = await record_event(
        event_type="endpoint_activity",
        actor_id=actor_id,
        host_id=host.id,
        decoy_id=None, token=None,
        action="request_fake_backup_archive",
        credential_used=False, breadcrumb_step=1,
        benign=False,
        metadata={"sensor": "fake_backup_endpoint", "scenario": "web-lure-demo", "force_alert": True},
        simulated_timestamp=None,
        db=db, decoy_sensitive=True, auth_event=False,
    )
    return {
        "mode": "synthetic-sandbox-only", "endpoint": "/backup.zip",
        "artifact": {"filename": "backup.zip", "content": "[FICTIONAL BACKUP METADATA ONLY]", "bytes": 0},
        "telemetry": result,
    }
