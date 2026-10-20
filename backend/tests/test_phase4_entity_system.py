"""Tests for Phase 4 Typed Entity validation and normalization."""

import pytest
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)


def test_entity_type_validation_and_normalization():
    inv_res = client.post("/api/investigations", json={"title": "Entity Validation Test"})
    inv_id = inv_res.json()["id"]

    # 1. Test Domain Normalization (lowercase, strip trailing dot and schemes)
    res = client.post(
        f"/api/investigations/{inv_id}/entities",
        json={"type": "domain", "label": "https://Target-CORP.com./"}
    )
    assert res.status_code == 200
    ent = res.json()
    assert ent["label"] == "target-corp.com"
    assert ent["properties"]["canonical_domain"] == "target-corp.com"

    # 2. Test Invalid Domain
    bad_dom = client.post(
        f"/api/investigations/{inv_id}/entities",
        json={"type": "domain", "label": "not a domain!!"}
    )
    assert bad_dom.status_code == 422

    # 3. Test IP Address Validation & Properties
    res_ip = client.post(
        f"/api/investigations/{inv_id}/entities",
        json={"type": "ip", "label": "8.8.8.8:53"}
    )
    assert res_ip.status_code == 200
    ip_ent = res_ip.json()
    assert ip_ent["label"] == "8.8.8.8"
    assert ip_ent["properties"]["version"] == 4
    assert ip_ent["properties"]["is_global"] is True

    # 4. Test Invalid IP
    bad_ip = client.post(
        f"/api/investigations/{inv_id}/entities",
        json={"type": "ip", "label": "999.999.999.999"}
    )
    assert bad_ip.status_code == 422

    # 5. Test Email Normalization
    res_email = client.post(
        f"/api/investigations/{inv_id}/entities",
        json={"type": "email", "label": "SecOps@CyberDefense.ORG"}
    )
    assert res_email.status_code == 200
    email_ent = res_email.json()
    assert email_ent["label"] == "secops@cyberdefense.org"
    assert email_ent["properties"]["domain"] == "cyberdefense.org"

    # 6. Test File Hash Detection (SHA-256)
    sha256_val = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    res_hash = client.post(
        f"/api/investigations/{inv_id}/entities",
        json={"type": "file_hash", "label": sha256_val.upper()}
    )
    assert res_hash.status_code == 200
    hash_ent = res_hash.json()
    assert hash_ent["label"] == sha256_val
    assert hash_ent["properties"]["hash_algorithm"] == "SHA-256"
