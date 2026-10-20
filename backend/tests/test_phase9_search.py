"""Tests for Phase 9 Search, Filtering, and Query Matching."""

from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)


def test_search_and_filter_entities():
    # 1. Create Investigation
    inv_res = client.post("/api/investigations", json={"title": "Search & Filter Investigation"})
    inv_id = inv_res.json()["id"]

    # 2. Add Entities
    client.post(f"/api/investigations/{inv_id}/entities", json={"type": "domain", "label": "malware-delivery.net", "properties": {"threat_level": "critical"}})
    client.post(f"/api/investigations/{inv_id}/entities", json={"type": "ip", "label": "192.0.2.1", "properties": {"asn": "AS1234"}})
    client.post(f"/api/investigations/{inv_id}/entities", json={"type": "email", "label": "operator@darkweb.org", "properties": {"alias": "phantom"}})
    client.post(f"/api/investigations/{inv_id}/entities", json={"type": "domain", "label": "benign-service.org"})

    # 3. Test Type Filter: domain only
    res_type = client.get(f"/api/investigations/{inv_id}/search?entity_type=domain").json()
    assert len(res_type) == 2
    assert all(e["type"] == "domain" for e in res_type)

    # 4. Test Text Search by Label Substring
    res_q = client.get(f"/api/investigations/{inv_id}/search?q=malware").json()
    assert len(res_q) == 1
    assert res_q[0]["label"] == "malware-delivery.net"

    # 5. Test Text Search by Property Content
    res_prop = client.get(f"/api/investigations/{inv_id}/search?q=phantom").json()
    assert len(res_prop) == 1
    assert res_prop[0]["label"] == "operator@darkweb.org"

    # 6. Test Combined Query + Type Filter
    res_comb = client.get(f"/api/investigations/{inv_id}/search?q=delivery&entity_type=domain").json()
    assert len(res_comb) == 1

    # 7. Test Mismatch Returns Empty List
    res_none = client.get(f"/api/investigations/{inv_id}/search?q=nonexistent").json()
    assert len(res_none) == 0
