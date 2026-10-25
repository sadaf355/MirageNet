"""Explainable adversary-playbook labels derived from ordered synthetic evidence."""

PLAYBOOKS = [
    {"id": "credential-lateral-movement", "label": "credential discovery → valid accounts → SSH lateral movement",
     "techniques": ["T1552.001", "T1078", "T1021.004"],
     "explanation": "The path contains credential-file evidence, credential use, and a simulated SSH hop."},
    {"id": "slow-scan-then-theft", "label": "slow scan then theft",
     "techniques": ["T1083", "T1005", "T1074"],
     "explanation": "Discovery is followed by local data access and staging evidence."},
    {"id": "insider-data-staging", "label": "insider access → data staging",
     "techniques": ["T1005", "T1074"],
     "explanation": "The observed sequence includes data access followed by staging."},
]

def classify_playbook(techniques: list[dict], timeline: list[dict]) -> dict:
    ordered = []
    for item in timeline:
        ev = item.get("evidence") or {}
        kind, action = item.get("event_type", ""), ev.get("action", item.get("action", ""))
        if kind == "file_enumeration" or action in {"enumerate", "banner_probe"}: tid = "T1083"
        elif "credential" in str(ev.get("decoy_type", "")).lower() or "credential" in str(ev.get("decoy_name", "")).lower(): tid = "T1552.001"
        elif kind == "auth_attempt" or ev.get("credential_evidence"): tid = "T1078"
        elif kind == "simulated_ssh" or action == "simulated_ssh": tid = "T1021.004"
        elif kind == "bulk_copy" or action in {"copy", "stage"}: tid = "T1074"
        elif kind == "file_read": tid = "T1005"
        else: continue
        if not ordered or ordered[-1] != tid: ordered.append(tid)
    known = {t.get("technique_id") for t in techniques} | set(ordered)
    # Credential scenario can map the initial file access to credential discovery when
    # the subsequent persisted sequence proves valid-account use followed by SSH.
    if "T1078" in ordered and "T1021.004" in ordered and ordered.index("T1078") < ordered.index("T1021.004"):
        if "T1552.001" not in ordered and "T1005" in ordered and ordered.index("T1005") < ordered.index("T1078"):
            ordered.insert(ordered.index("T1078"), "T1552.001")
            known = set(known) | {"T1552.001"}
    for playbook in PLAYBOOKS:
        sequence = playbook["techniques"]
        if all(t in known for t in sequence) or (playbook["id"] == "insider-data-staging" and {"T1005", "T1074"} <= known):
            # Score by ordered technique coverage; keep the strongest explainable match.
            score = sum(1 for tid in sequence if tid in ordered) / len(sequence)
            if score >= (0.66 if playbook["id"] == "insider-data-staging" else 0.5):
                return {"id": playbook["id"], "label": playbook["label"], "confidence": round(score, 2),
                        "technique_sequence": ordered, "matched_techniques": [t for t in sequence if t in known],
                        "explanation": playbook["explanation"], "source": "ordered synthetic ATT&CK evidence"}
    return {"id": "unclassified", "label": "unclassified observed path", "confidence": 0.0,
            "technique_sequence": ordered, "matched_techniques": sorted(known),
            "explanation": "The current path did not match a supported playbook pattern; no label was forced.",
            "source": "ordered synthetic ATT&CK evidence"}
