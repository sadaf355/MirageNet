import secrets
import uuid
import os
import json
import urllib.request
import urllib.error
import re
from sqlalchemy.orm import Session
from app.models import Decoy
from app.services.placement import choose_host

# All artifact content is fictional and inert; provenance records whether it came from Adaption, cache, or local fallback.
ARTIFACT_TEMPLATES = [
    {
        "type": "finance_hr",
        "names": ["Q4 Finance Forecast", "Payroll Reconciliation Notes", "Vendor Payment Schedule", "HR Compensation Review"],
        "content": {"department": "Finance Operations", "classification": "INTERNAL-SIMULATED",
                    "period": "Q4-FY26", "note": "Synthetic planning artifact. Values are illustrative only.",
                    "reference": "FIN-DEMO-2048"}
    },
    {
        "type": "credential_note",
        "names": ["Legacy Service Access Notes", "Operations Vault Migration Memo", "Staging Account Inventory", "Admin Handoff Checklist"],
        "content": {"owner": "simulation-operator", "environment": "training-lab",
                    "username": "demo_operator", "password": "NOT-A-REAL-PASSWORD",
                    "note": "Fictional placeholder. This is not a valid credential."}
    },
    {
        "type": "config",
        "names": ["Internal Service Configuration", "SSH Client Migration Config", "Build Runner Settings", "Application Environment Notes"],
        "content": {"service": "mirage-demo-service", "endpoint": "service.invalid",
                    "port": 8443, "auth_mode": "SIMULATED", "private_key": "REDACTED-SYNTHETIC-PLACEHOLDER"}
    },
    {
        "type": "database",
        "names": ["Customer Export Snapshot", "Billing Records Sample", "CRM Backup Index", "Account Directory Extract"],
        "content": {"dataset": "synthetic_customer_records", "record_count": 128,
                    "fields": ["customer_ref", "region", "plan_tier", "created_at"],
                    "sample_record": {"customer_ref": "CUST-DEMO-0042", "region": "WEST", "plan_tier": "STANDARD"},
                    "contains_real_personal_data": False}
    },
    {
        "type": "api_artifact",
        "names": ["Partner API Integration Notes", "Internal API Key Rotation Memo", "Webhook Delivery Configuration", "Service Endpoint Inventory"],
        "content": {"service": "partner-api-simulator", "base_url": "https://api.example.invalid/v1",
                    "api_key": "SIMULATED_TOKEN_DO_NOT_USE", "webhook": "https://hooks.example.invalid/demo",
                    "note": "Nonfunctional synthetic values for the MirageNet lab."}
    },
]

ATTACKER_QUERIES = [
    "administrator credentials password vault access notes", "finance payroll vendor payment forecast",
    "customer database export backup records", "SSH configuration jump host private key",
    "API token webhook endpoint integration", "HR compensation employee records",
    "backup archive database dump recovery", "service account staging login migration",
]

def _score_artifact(template: dict, index: int) -> tuple[float, float]:
    """Fallback single-artifact score; batch forge replaces enticement with corpus scores."""
    type_bonus = {"credential_note": .12, "database": .10, "finance_hr": .08, "config": .06, "api_artifact": .09}
    richness = min(len(template["content"]) / 8, 1.0)
    quality = min(.98, .68 + richness * .18 + type_bonus.get(template["type"], 0) + (index % 4) * .015)
    enticement = min(.98, .55 + type_bonus.get(template["type"], 0) + richness * .12 + ((index * 7) % 5) * .018)
    return round(quality, 2), round(enticement, 2)


def _score_artifact_set(templates: list[dict]) -> list[tuple[float, float]]:
    """Fit one TF-IDF vocabulary across the entire batch and eight attacker queries."""
    type_bonus = {"credential_note": .12, "database": .10, "finance_hr": .08, "config": .06, "api_artifact": .09}
    texts = [" ".join([t["type"], " ".join(t["names"]), json.dumps(t["content"], sort_keys=True)]) for t in templates]
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        import numpy as np
        vectorizer = TfidfVectorizer(ngram_range=(1, 2), stop_words="english")
        matrix = vectorizer.fit_transform(texts + ATTACKER_QUERIES)
        artifact_vectors = matrix[:len(texts)]
        query_vectors = matrix[len(texts):]
        similarities = (artifact_vectors @ query_vectors.T).toarray()
        results = []
        for i, template in enumerate(templates):
            richness = min(len(template["content"]) / 8, 1.0)
            quality = min(.98, .68 + richness * .18 + type_bonus.get(template["type"], 0) + (i % 4) * .015)
            best = float(np.max(similarities[i])) if similarities.shape[1] else 0.0
            enticement = min(.98, .35 + best * .63 + type_bonus.get(template["type"], 0) * .2)
            results.append((round(quality, 2), round(enticement, 2)))
        return results
    except Exception:
        return [_score_artifact(template, i) for i, template in enumerate(templates)]

def _cached_templates(count: int) -> list[dict] | None:
    """Load quality-filtered decoy rows. Provenance is preserved per row."""
    from pathlib import Path
    cache_path = Path(__file__).resolve().parents[3] / "data" / "decoys.jsonl"
    if not cache_path.exists():
        return None
    rows = []
    for line in cache_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if row.get("decoy_type") not in {t["type"] for t in ARTIFACT_TEMPLATES}:
            continue
        body = row.get("content", "")
        rows.append({"type": row["decoy_type"], "names": [str(row.get("filename") or "Synthetic artifact")],
            "content": {"path": row.get("path", "/simulation/"), "filename": row.get("filename", "artifact.txt"),
                "body": body if isinstance(body, str) else json.dumps(body, ensure_ascii=False),
                "lure_theme": row.get("lure_theme", "Synthetic defensive lure"), "synthetic": True},
            "quality_score": float(row.get("quality_score", 0.0)),
            "quality_source": row.get("quality_source", "cache_rubric"),
            "source_mode": row.get("source_mode", "cache")})
    return rows[:count] if rows else None


def forge_decoys(db: Session, count: int = 60, company_profile: str | None = None) -> dict:
    if count < 1 or count > 200:
        raise ValueError("count must be between 1 and 200")
    created = []
    cached_templates = _cached_templates(count)
    source_mode = cached_templates[0].get("source_mode", "cache") if cached_templates else "local_synthetic_fallback"
    selected_templates = []
    for i in range(count):
        if cached_templates:
            selected_templates.append(cached_templates[i % len(cached_templates)])
        else:
            template = ARTIFACT_TEMPLATES[i % len(ARTIFACT_TEMPLATES)]
            selected_templates.append({**template, "quality_score": None, "quality_source": "local_rubric", "source_mode": "local_synthetic_fallback"})
    batch_scores = _score_artifact_set(selected_templates)
    chain_id = f"crumb-{uuid.uuid4().hex[:10]}"
    for i, template in enumerate(selected_templates):
        name = template["names"][(i // max(1, len(ARTIFACT_TEMPLATES))) % len(template["names"])]
        host_id, placement_score = choose_host(db, i, template["type"])
        chain_hosts = {0: ("ws-01", "credential_note"), 1: ("jmp-01", "config"), 2: ("db-01", "database")}
        if i in chain_hosts and not cached_templates:
            host_id, required_type = chain_hosts[i]
            template = next(t for t in ARTIFACT_TEMPLATES if t["type"] == required_type)
            placement_score = __import__("app.services.placement", fromlist=["placement_scores"]).placement_scores(db).get(host_id, placement_score)
        token = f"mrg-{secrets.token_urlsafe(18)}"
        heuristic_quality, enticement = batch_scores[i]
        quality = template.get("quality_score")
        quality = float(quality) if isinstance(quality, (int, float)) else heuristic_quality
        quality_source = template.get("quality_source") or "local_rubric"
        chain_step = (i % 3) + 1 if i < 3 else None
        content = {
            **template["content"], "synthetic": True,
            "company_profile": company_profile or "Northwind Logistics (fictional)",
            "source": {"mode": source_mode, "generator": "adaption-sdk" if source_mode == "adaption_generated" else ("decoy-cache" if cached_templates else "miragenet-template-forge"),
                       "quality_source": quality_source, "version": "2.0"},
            "tracking_token": token, "placement_score": placement_score,
            "breadcrumb": ({"chain_id": chain_id, "step": chain_step, "steps_total": 3} if chain_step else None),
        }
        if not content.get("body"):
            content["body"] = json.dumps({k: v for k, v in content.items() if k != "body"}, indent=2, ensure_ascii=False)
        else:
            content["metadata_json"] = json.dumps({k: v for k, v in content.items() if k not in {"body", "metadata_json"}}, indent=2, ensure_ascii=False)
        row = Decoy(id=f"decoy-{uuid.uuid4().hex[:12]}", name=f"{name} #{i + 1:02d}",
            decoy_type=template["type"], host_id=host_id, token=token,
            quality_score=round(max(0.0, min(1.0, quality)), 4), enticement_score=enticement,
            status="staged", content=content)
        db.add(row)
        created.append(row)
    db.commit()
    return {"created": len(created), "status": "forged", "source_mode": source_mode,
        "company_profile": company_profile or "Northwind Logistics (fictional)",
        "message": ("Artifacts loaded from the local filtered cache; no live AI generation occurred." if source_mode == "cache" else
                    "Artifacts generated by the authenticated Adaption SDK." if source_mode == "adaption_generated" else
                    "Local synthetic fallback templates used; no live AI generation occurred."),
        "breadcrumb_chain": {"chain_id": chain_id, "steps": [
            {"decoy_id": created[i].id, "name": created[i].name, "host_id": created[i].host_id, "step": i + 1}
            for i in range(min(3, len(created)))]},
        "decoys": [serialize_decoy(d) for d in created]}

def serialize_decoy(d: Decoy) -> dict:
    breadcrumb = (d.content or {}).get("breadcrumb")
    return {
        "id": d.id, "name": d.name, "type": d.decoy_type, "host_id": d.host_id,
        "token": d.token, "quality_score": d.quality_score,
        "enticement_score": d.enticement_score, "status": d.status,
        "source_mode": ((d.content or {}).get("source") or {}).get("mode", "unknown"),
        "quality_source": ((d.content or {}).get("source") or {}).get("quality_source", "unknown"),
        "placement_score": (d.content or {}).get("placement_score", 0),
        "breadcrumb": breadcrumb,
    }


def rotate_decoy(db: Session, decoy: Decoy, commit: bool = True) -> Decoy:
    """Burn a decoy and deploy a replacement while retaining audit history. Set commit=False inside a sensor transaction."""
    decoy.status = "burned"
    old_content = dict(decoy.content or {})
    token = f"mrg-{secrets.token_urlsafe(18)}"
    old_content["tracking_token"] = token
    old_content["rotation"] = {"replaces": decoy.id, "rotated_from_token": decoy.token, "synthetic": True}
    replacement = Decoy(id=f"decoy-{uuid.uuid4().hex[:12]}", name=f"{decoy.name} · rotated",
        decoy_type=decoy.decoy_type, host_id=decoy.host_id, token=token,
        quality_score=decoy.quality_score, enticement_score=decoy.enticement_score,
        status="deployed", content=old_content)
    db.add(replacement)
    if commit:
        db.commit()
        db.refresh(replacement)
    else:
        db.flush()
    return replacement
