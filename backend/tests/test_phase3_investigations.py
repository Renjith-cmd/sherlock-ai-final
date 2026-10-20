"""Tests for Phase 3 Investigation and Case Management lifecycle."""

from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)


def test_investigation_lifecycle_crud_and_duplicate():
    # 1. Create Investigation
    create_res = client.post(
        "/api/investigations",
        json={"title": "Primary Op", "description": "High value target case", "tags": ["osint", "cyber"]}
    )
    assert create_res.status_code == 200
    inv = create_res.json()
    inv_id = inv["id"]
    assert inv["title"] == "Primary Op"
    assert inv["tags"] == ["osint", "cyber"]

    # 2. Add Entities and Relationships
    e1 = client.post(f"/api/investigations/{inv_id}/entities", json={"type": "domain", "label": "seed.org"}).json()
    e2 = client.post(f"/api/investigations/{inv_id}/entities", json={"type": "ip", "label": "8.8.8.8"}).json()
    rel = client.post(
        f"/api/investigations/{inv_id}/relationships",
        json={"source_id": e1["id"], "target_id": e2["id"], "type": "RESOLVES_TO"}
    ).json()

    # 3. Update Investigation title & description
    patch_res = client.patch(
        f"/api/investigations/{inv_id}",
        json={"title": "Primary Op - Escalated", "description": "Updated priority"}
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["title"] == "Primary Op - Escalated"
    assert patch_res.json()["description"] == "Updated priority"

    # 4. Duplicate Investigation
    dup_res = client.post(f"/api/investigations/{inv_id}/duplicate", json={"title": "Primary Op - Branch Copy"})
    assert dup_res.status_code == 200
    dup_inv = dup_res.json()
    dup_id = dup_inv["id"]
    assert dup_id != inv_id
    assert dup_inv["title"] == "Primary Op - Branch Copy"

    # Verify duplicated graph has cloned nodes and edges with distinct IDs
    dup_graph = client.get(f"/api/investigations/{dup_id}/graph").json()
    assert len(dup_graph["nodes"]) == 2
    assert len(dup_graph["edges"]) == 1
    assert dup_graph["nodes"][0]["id"] != e1["id"]
    assert dup_graph["nodes"][1]["id"] != e2["id"]
    assert dup_graph["edges"][0]["id"] != rel["id"]

    # 5. Delete Investigation
    del_res = client.delete(f"/api/investigations/{inv_id}")
    assert del_res.status_code == 200

    # Verify original is gone and dup remains intact
    get_res = client.get(f"/api/investigations/{inv_id}")
    assert get_res.status_code == 404

    dup_check = client.get(f"/api/investigations/{dup_id}")
    assert dup_check.status_code == 200
