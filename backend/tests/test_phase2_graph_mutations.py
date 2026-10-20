"""Tests for Phase 2 graph mutation endpoints."""

from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)


def test_entity_update_and_delete_lifecycle():
    # 1. Create investigation
    inv_res = client.post("/api/investigations", json={"title": "Mutation Test"})
    assert inv_res.status_code == 200
    inv_id = inv_res.json()["id"]

    # 2. Create entities
    node_a = client.post(
        f"/api/investigations/{inv_id}/entities",
        json={"type": "domain", "label": "old-domain.com"}
    ).json()

    node_b = client.post(
        f"/api/investigations/{inv_id}/entities",
        json={"type": "ip", "label": "192.168.1.1"}
    ).json()

    # 3. Create relationship
    rel = client.post(
        f"/api/investigations/{inv_id}/relationships",
        json={"source_id": node_a["id"], "target_id": node_b["id"], "type": "POINTS_TO"}
    ).json()

    # 4. Update entity label & properties
    upd = client.patch(
        f"/api/entities/{node_a['id']}",
        json={"label": "new-domain.com", "properties": {"status": "active"}}
    )
    assert upd.status_code == 200
    assert upd.json()["label"] == "new-domain.com"
    assert upd.json()["properties"]["status"] == "active"

    # 5. Delete relationship
    del_rel = client.delete(f"/api/relationships/{rel['id']}")
    assert del_rel.status_code == 200

    # 6. Delete entity
    del_ent = client.delete(f"/api/entities/{node_a['id']}")
    assert del_ent.status_code == 200

    # Verify graph now only has node_b
    graph = client.get(f"/api/investigations/{inv_id}/graph").json()
    assert len(graph["nodes"]) == 1
    assert graph["nodes"][0]["id"] == node_b["id"]
    assert len(graph["edges"]) == 0
