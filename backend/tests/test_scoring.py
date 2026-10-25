import pytest
from app.services.scoring import confidence_score, severity_for

def test_confidence_formula_baseline():
    assert confidence_score(1, 1, 1, 1) == pytest.approx(1.0)

def test_benign_adjustment_is_point_four():
    assert confidence_score(1, 1, 1, 1, benign_allowlisted=True) == pytest.approx(0.6)

def test_severity_thresholds():
    assert severity_for(.8) == "high"
    assert severity_for(.5) == "medium"
    assert severity_for(.499) == "low"

def test_scores_are_bounded():
    with pytest.raises(ValueError):
        confidence_score(1.1, 0, 0, 0)
