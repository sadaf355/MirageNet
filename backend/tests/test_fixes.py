def test_burning_decoy_rotates_to_fresh_deployed_token(client):
    # Keep this test independent of database state left by other tests.
    client.post('/api/forge/run', json={'count': 1})
    client.post('/api/deploy')
    decoys = client.get('/api/decoys').json()
    assert decoys
    old = next(d for d in decoys if d['status'] == 'deployed')
    response = client.post(f"/api/decoys/{old['id']}/burn")
    assert response.status_code == 200
    body = response.json()
    assert body['status'] == 'burned'
    replacement = body['replacement']
    assert replacement['status'] == 'deployed'
    assert replacement['token'] != old['token']
    assert replacement['id'] != old['id']


def test_incident_reconstruction_includes_topology_valid_graph_edges(client):
    run = client.post('/api/scenarios/credential-lateral-movement/run').json()
    incident = client.post('/api/incidents/reconstruct', json={'event_ids': run['event_ids']})
    assert incident.status_code == 200
    evidence = incident.json()['evidence']
    assert 'graph_edges' in evidence
    assert evidence['graph_note']
    allowed = {tuple(sorted(pair)) for pair in [
        ('WEB-01', 'WS-01'), ('WS-01', 'FS-01'), ('WS-01', 'JMP-01'),
        ('JMP-01', 'DB-01'), ('JMP-01', 'GIT-01'), ('JMP-01', 'BKP-01'), ('FS-01', 'BKP-01')
    ]}
    assert all(tuple(sorted((edge['source'], edge['target']))) in allowed for edge in evidence['graph_edges'])


def test_scenario_latency_is_measured_and_not_hardcoded_zero(client):
    result = client.post('/api/scenarios/insider-data-theft/run').json()
    assert result['time_to_first_alert_seconds'] is not None
    assert result['time_to_first_alert_seconds'] >= 0
    assert 'timeline_step_f1' in result
