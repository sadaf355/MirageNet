def test_scenario_catalog_lists_safe_scenarios(client):
    response = client.get('/api/scenarios')
    assert response.status_code == 200
    names = {row['name'] for row in response.json()}
    assert {'insider-data-theft', 'credential-lateral-movement', 'slow-scan-theft',
            'benign-backup-noise', 'noisy-partial-intrusion', 'benign-scanner',
            'benign-health-check', 'benign-admin-login', 'imperfect-missed-step',
            'imperfect-extra-benign-step', 'imperfect-reordered-step'} <= names

def test_scenario_run_emits_persisted_synthetic_events(client):
    response = client.post('/api/scenarios/insider-data-theft/run')
    assert response.status_code == 200
    result = response.json()
    assert result['status'] == 'completed'
    assert result['safe_mode'] is True
    assert result['events_emitted'] == 3
    assert len(result['event_ids']) == 3
    assert result['run_id'].startswith('run-')

def test_benign_scenario_has_no_high_severity_alerts(client):
    response = client.post('/api/scenarios/benign-backup-noise/run')
    assert response.status_code == 200
    result = response.json()
    assert result['ground_truth'] == 'benign'
    assert result['alerts_emitted'] == 0
    assert result['benign_high_severity_alerts'] == 0
    assert result['timeline_step_f1'] is None

def test_evaluation_reports_targets_separately_from_measurements(client):
    response = client.get('/api/eval')
    assert response.status_code == 200
    body = response.json()
    assert 'targets' in body and 'measured' in body
    assert 'timeline_step_f1' in body['measured']
    assert 'enticement_top10_pass_rate' in body['measured']

def test_play_filesystem_only_returns_deployed_synthetic_entries(client):
    response = client.get('/api/play/filesystem')
    assert response.status_code == 200
    assert response.json()['mode'] == 'fictional-read-only-filesystem'
    assert 'No shell commands' in response.json()['restrictions']

def test_eval_values_after_attack_scenarios_match_prd_targets(client):
    for scenario in ('insider-data-theft', 'credential-lateral-movement', 'slow-scan-theft'):
        response = client.post(f'/api/scenarios/{scenario}/run')
        assert response.status_code == 200
    client.post('/api/scenarios/benign-backup-noise/run')
    body = client.get('/api/eval').json()
    attack_runs = [row for row in body['runs'] if row['scenario'] in {
        'insider-data-theft', 'credential-lateral-movement', 'slow-scan-theft'
    }]
    assert len(attack_runs) >= 3
    assert all(row['observed_detection_rate'] == 1.0 for row in attack_runs)
    assert all(row['timeline_step_f1'] is not None and row['timeline_step_f1'] >= 0.90 for row in attack_runs)
    benign_runs = [row for row in body['runs'] if row['ground_truth'] == 'benign']
    assert all(row['timeline_step_f1'] is None for row in benign_runs)
    assert body['measured']['benign_high_severity_alerts'] == 0

def test_siem_export_returns_normalized_alert_payload(client):
    run = client.post('/api/scenarios/insider-data-theft/run').json()
    assert run['alert_ids'], 'scenario must produce at least one alert for SIEM export test'
    response = client.get(f"/api/alerts/{run['alert_ids'][0]}/siem")
    assert response.status_code == 200
    payload = response.json()
    assert payload['event_kind'] == 'miragenet.alert'
    assert payload['detection']['mode'] == 'sandbox-only'
    assert payload['alert']['id'] == run['alert_ids'][0]

def test_reset_clears_history_and_seeds_deployed_demo_decoys(client):
    client.post('/api/scenarios/insider-data-theft/run')
    response = client.post('/api/reset')
    assert response.status_code == 200
    assert response.json()['decoys_deployed'] == 60
    assert client.get('/api/events').json() == []
    assert client.get('/api/alerts').json() == []
    decoys = client.get('/api/decoys').json()
    assert len(decoys) == 60
    assert all(d['status'] == 'deployed' for d in decoys)
    assert decoys[0]['name']
