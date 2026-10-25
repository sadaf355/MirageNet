from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_synthetic_sensor_event_and_alert_flow():
    # Use an existing seeded host and forge/deploy one artifact through public API.
    forged = client.post('/api/forge/run', json={'count': 3})
    assert forged.status_code == 200
    decoy_id = forged.json()['decoys'][0]['id']
    deployed = client.post('/api/deploy')
    assert deployed.status_code == 200
    response = client.post('/api/sensor/touch', json={
        'decoy_id': decoy_id, 'actor_id': 'pytest-synthetic-actor',
        'action': 'read', 'credential_used': True, 'breadcrumb_step': 2,
    })
    assert response.status_code == 200
    payload = response.json()
    assert payload['event']['event_type'] == 'file_read'
    assert payload['event']['evidence']['simulated'] is True
    assert payload['alert'] is not None
    assert payload['alert']['severity'] in {'low', 'medium', 'high'}
    assert client.get('/api/events?limit=1').status_code == 200
    assert client.get('/api/alerts?limit=1').status_code == 200

def test_touch_requires_deployed_decoy():
    forged = client.post('/api/forge/run', json={'count': 1})
    decoy_id = forged.json()['decoys'][0]['id']
    response = client.post('/api/sensor/touch', json={'decoy_id': decoy_id})
    assert response.status_code == 409
