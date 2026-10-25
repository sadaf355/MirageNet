from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_credential_scenario_groups_one_incident_three_host_path_and_markdown_report():
    result = client.post('/api/scenarios/credential-lateral-movement/run')
    assert result.status_code == 200, result.text
    run_id = result.json()['run_id']
    rows = client.get('/api/incidents').json()
    matching = [row for row in rows if row['id'] and row['event_count'] >= 3]
    detail = None
    for row in matching:
        candidate = client.get(f"/api/incidents/{row['id']}").json()
        if candidate.get('evidence', {}).get('run_id') == run_id:
            detail = candidate
            break
    assert detail is not None
    evidence = detail['evidence']
    assert evidence['event_count'] == 3
    assert len(evidence['host_path']) == 3
    assert evidence['attack_techniques']
    report = client.get(f"/api/incidents/{detail['id']}/report?format=md")
    assert report.status_code == 200
    assert '# Session investigation' in report.text
    assert 'MITRE ATT&CK mappings' in report.text

def test_fake_web_lures_are_inert_and_emit_telemetry():
    admin = client.get('/admin?actor_id=phase3-test-admin')
    backup = client.get('/backup.zip?actor_id=phase3-test-backup')
    assert admin.status_code == 200 and admin.json()['mode'] == 'synthetic-sandbox-only'
    assert backup.status_code == 200 and backup.json()['artifact']['bytes'] == 0
    assert 'telemetry' in admin.json() and 'telemetry' in backup.json()
