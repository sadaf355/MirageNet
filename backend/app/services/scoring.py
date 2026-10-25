def confidence_score(decoy_sensitivity: float, actor_novelty: float,
                     credential_evidence: float, breadcrumb_progress: float,
                     benign_allowlisted: bool = False) -> float:
    """PRD baseline: C0=.35D+.25N+.20U+.20P; benign adjustment=.40*Ib."""
    values = [decoy_sensitivity, actor_novelty, credential_evidence, breadcrumb_progress]
    if any(v < 0 or v > 1 for v in values):
        raise ValueError("All score inputs must be between 0 and 1")
    base = .35 * decoy_sensitivity + .25 * actor_novelty + .20 * credential_evidence + .20 * breadcrumb_progress
    return max(0.0, min(1.0, base - (.40 if benign_allowlisted else 0.0)))

def severity_for(confidence: float) -> str:
    if confidence >= .8:
        return "high"
    if confidence >= .5:
        return "medium"
    return "low"
