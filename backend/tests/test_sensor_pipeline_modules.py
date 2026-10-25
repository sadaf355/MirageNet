from datetime import datetime, timezone
from types import SimpleNamespace
from app.services.sensor_pipeline.score import score_event
from app.services.sensor_pipeline.sensors import edge_evidence

def test_score_module_exposes_all_components_and_benign_adjustment():
    score = score_event(SimpleNamespace(enticement_score=.8), True, True, True, False, 2, set(), None, True)
    assert set(("D","N","U","P","raw_weighted_score","benign_adjustment","confidence","severity")) <= set(score)
    assert score["benign_adjustment"] == -.4
    assert score["confidence"] < score["raw_weighted_score"]

def test_sensor_module_marks_only_explicit_transition_as_observed():
    assert edge_evidence({}, "evt-1", "WEB-01") == []
    edges = edge_evidence({"observed_transition":True,"source_host":"WS-01"}, "evt-2", "WEB-01")
    assert edges == [{"source":"ws-01","target":"web-01","edge_type":"observed","evidence_event_id":"evt-2"}]

def test_correlate_module_reuses_recent_actor_session():
    from datetime import datetime, timezone
    from app.database import SessionLocal
    from app.models import Session as ActorSession
    from app.services.sensor_pipeline.correlate import correlate_session
    db = SessionLocal()
    actor = 'module-test-correlate-unique'
    try:
        now = datetime.now(timezone.utc)
        first, is_new, stitched = correlate_session(db, actor, now)
        assert is_new is True and stitched is False
        db.commit()
        second, is_new_again, stitched_again = correlate_session(db, actor, now)
        assert second.id == first.id
        assert is_new_again is False and stitched_again is False
    finally:
        db.query(ActorSession).filter(ActorSession.actor_id == actor).delete()
        db.commit(); db.close()
