"""Tests for Phase 8 Evidence, Provenance, and Audit Logging."""

from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)


def test_evidence_attachment_and_audit_trail():
    # 1. Create Investigation
    inv_res = client.post("/api/investigations", json={"title": "Forensic Provenance Case"})
    inv_id = inv_res.json()["id"]

    # 2. Add Target Entity
    ent = client.post(
        f"/api/investigations/{inv_id}/entities",
        json={"type": "domain", "label": "suspicious-target.com"}
    ).json()
    ent_id = ent["id"]

    # 3. Attach Evidence to Entity
    ev_payload = {
        "source_identifier": "CERT-In Advisory 2026-99",
        "source_url": "https://advisory.cert-in.org.in/2026-99.html",
        "content_hash": "a1b2c3d4e5f67890abcdef1234567890abcdef1234567890abcdef1234567890",
        "user_notes": "Observed in active phishing campaign."
    }
    ev_res = client.post(f"/api/investigations/{inv_id}/entities/{ent_id}/evidence", json=ev_payload)
    assert ev_res.status_code == 200
    evidence = ev_res.json()
    assert evidence["source_identifier"] == "CERT-In Advisory 2026-99"
    assert evidence["entity_id"] == ent_id

    # 4. Retrieve Evidence list for Entity
    ev_list = client.get(f"/api/investigations/{inv_id}/entities/{ent_id}/evidence").json()
    assert len(ev_list) == 1
    assert ev_list[0]["source_url"] == "https://advisory.cert-in.org.in/2026-99.html"

    # 5. Retrieve Investigation Audit Trail
    audit_res = client.get(f"/api/investigations/{inv_id}/audit-logs")
    assert audit_res.status_code == 200
    logs = audit_res.json()
    assert len(logs) >= 1
    assert logs[0]["action"] == "ATTACH_EVIDENCE"
    assert logs[0]["details"]["entity_id"] == ent_id
