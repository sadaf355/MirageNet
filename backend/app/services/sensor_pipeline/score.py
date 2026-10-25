from app.services.scoring import confidence_score, severity_for

def score_event(decoy, decoy_sensitive, is_new_actor, credential_used, auth_event, breadcrumb_step, prior_chain_steps, chain_id, benign):
    d = float(decoy.enticement_score) if decoy and decoy_sensitive else (0.35 if decoy_sensitive else 0.0)
    n = 0.9 if is_new_actor else 0.45
    u = 1.0 if (credential_used or auth_event) else 0.0
    p = min(1.0, max(breadcrumb_step, min(3, len(prior_chain_steps) + 1) if chain_id else breadcrumb_step) / 3.0) if decoy else 0.0
    confidence = confidence_score(d, n, u, p, benign_allowlisted=benign)
    return {"D": round(d,4), "N": round(n,4), "U": round(u,4), "P": round(p,4),
            "benign_adjustment": -0.40 if benign else 0.0,
            "raw_weighted_score": round(.35*d+.25*n+.20*u+.20*p,4),
            "confidence": confidence, "severity": severity_for(confidence)}
