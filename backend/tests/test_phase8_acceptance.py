"""PRD acceptance regression tests for synthetic scenario evaluation."""
def test_prd_attack_scenario_targets_and_benign_control(client):
    attack_names = ["insider-data-theft", "credential-lateral-movement", "slow-scan-theft"]
    for name in attack_names:
        response = client.post(f"/api/scenarios/{name}/run")
        assert response.status_code == 200
        result = response.json()
        assert result["observed_detection_rate"] == 1.0, f"{name} missed a simulated target"
        assert result["timeline_step_f1"] >= 0.90, f"{name} timeline F1 below PRD target"
    benign = client.post("/api/scenarios/benign-backup-noise/run")
    assert benign.status_code == 200
    assert benign.json()["benign_high_severity_alerts"] == 0


def test_sensor_http_response_exposes_measured_latency(client):
    response = client.post("/api/sensor/endpoint", json={
        "actor_id": "latency-test-actor", "host_id": "web-01",
        "action": "health_check", "metadata": {"synthetic_test": True}
    })
    assert response.status_code == 200
    assert float(response.headers["x-sensor-latency-seconds"]) >= 0.0


def test_evaluation_maps_ground_truth_label_and_benign_f1_is_null(client):
    client.post("/api/scenarios/insider-data-theft/run")
    client.post("/api/scenarios/benign-backup-noise/run")
    summary = client.get("/api/eval")
    assert summary.status_code == 200
    runs = summary.json()["runs"]
    assert any(r["ground_truth"] == "malicious" for r in runs)
    benign = [r for r in runs if r["ground_truth"] == "benign"]
    assert benign
    assert all(r["timeline_step_f1"] is None for r in benign)
