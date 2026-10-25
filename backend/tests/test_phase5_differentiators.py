from app.services.sensor_pipeline.playbook import classify_playbook


def test_playbook_replay_labels_credential_sequence():
    timeline = [
        {"event_type": "file_read", "action": "read", "evidence": {"action": "read", "decoy_type": "credential_note"}},
        {"event_type": "auth_attempt", "action": "credential_use", "evidence": {"action": "credential_use", "credential_evidence": 1.0}},
        {"event_type": "simulated_ssh", "action": "simulated_ssh", "evidence": {"action": "simulated_ssh"}},
    ]
    techniques = [
        {"technique_id": "T1552.001"},
        {"technique_id": "T1078"},
        {"technique_id": "T1021.004"},
    ]
    result = classify_playbook(techniques, timeline)
    assert result["id"] == "credential-lateral-movement"
    assert result["confidence"] > 0
    assert result["technique_sequence"][:3] == ["T1552.001", "T1078", "T1021.004"]


def test_playbook_replay_does_not_force_label_for_unmatched_path():
    result = classify_playbook([], [{"event_type": "endpoint_activity", "action": "health_check", "evidence": {}}])
    assert result["id"] == "unclassified"
    assert result["confidence"] == 0.0


def test_high_confidence_touch_auto_burns_and_rotates(client):
    from app.database import SessionLocal
    from app.models import Decoy
    decoys = client.get('/api/decoys').json()
    decoy = next(d for d in decoys if d['status'] == 'deployed' and d['type'] == 'credential_note')
    # Make the test deterministic: this is a controlled synthetic high-confidence fixture.
    with SessionLocal() as db:
        row = db.get(Decoy, decoy['id'])
        row.enticement_score = 1.0
        db.commit()
    response = client.post('/api/sensor/touch', json={
        'decoy_id': decoy['id'], 'actor_id': 'phase5-rotation-test',
        'action': 'credential_use', 'credential_used': True, 'breadcrumb_step': 3,
        'benign': False,
    })
    assert response.status_code == 200, response.text
    body = response.json()
    assert body['event']['evidence']['score_breakdown']['confidence'] >= 0.8
    rotation = body.get('auto_rotation')
    assert rotation and rotation['automatic'] is True
    assert rotation['replacement']['token'] != decoy['token']
    inventory = client.get('/api/decoys').json()
    assert next(d for d in inventory if d['id'] == decoy['id'])['status'] == 'burned'
    assert next(d for d in inventory if d['id'] == rotation['replacement']['id'])['status'] == 'deployed'


def test_credential_scenario_returns_attack_sequence_playbook(client):
    result = client.post('/api/scenarios/credential-lateral-movement/run').json()
    assert result['adversary_playbook']['id'] == 'credential-lateral-movement'
    assert ['T1552.001', 'T1078', 'T1021.004'] == [t for t in result['adversary_playbook']['technique_sequence'] if t in {'T1552.001', 'T1078', 'T1021.004'}]
