from datetime import timedelta, timezone
from app.models import Event, Session as ActorSession
from uuid import uuid4

def correlate_session(db, actor_id, now, token=None, credential_signal=False):
    cutoff = now - timedelta(minutes=15)
    sessions = db.query(ActorSession).filter(ActorSession.actor_id == actor_id).all()
    session = next((s for s in sorted(sessions, key=lambda s:s.last_seen_at, reverse=True)
        if (s.last_seen_at.replace(tzinfo=timezone.utc) if s.last_seen_at.tzinfo is None else s.last_seen_at.astimezone(timezone.utc)) >= cutoff), None)
    stitched = False
    if session is None and (credential_signal or token):
        for event in db.query(Event).order_by(Event.timestamp.desc()).limit(500).all():
            ts = event.timestamp.replace(tzinfo=timezone.utc) if event.timestamp.tzinfo is None else event.timestamp.astimezone(timezone.utc)
            ev = event.evidence or {}
            if cutoff <= ts <= now and ((token and ev.get('token') == token) or (credential_signal and ev.get('credential_evidence'))):
                candidate = db.get(ActorSession, ev.get('session_id')) if ev.get('session_id') else None
                if candidate:
                    session, stitched = candidate, True
                    break
    is_new = session is None
    if session is None:
        session = ActorSession(id=f"ses-{uuid4().hex[:16]}", actor_id=actor_id, started_at=now, last_seen_at=now, confidence=0.0, status="observing")
        db.add(session); db.flush()
    return session, is_new, stitched
