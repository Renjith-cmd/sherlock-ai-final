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


def test_graph_edges_include_endpoint_names_and_provenance():
    inv_id = client.post("/api/investigations", json={"title": "Edge Details Test"}).json()["id"]
    source = client.post(
        f"/api/investigations/{inv_id}/entities",
        json={"type": "domain", "label": "source.example.com"},
    ).json()
    target = client.post(
        f"/api/investigations/{inv_id}/entities",
        json={"type": "ip", "label": "192.0.2.10"},
    ).json()
    client.post(
        f"/api/investigations/{inv_id}/relationships",
        json={"source_id": source["id"], "target_id": target["id"], "type": "RESOLVES_TO"},
    )

    graph = client.get(f"/api/investigations/{inv_id}/graph").json()
    edge = graph["edges"][0]
    assert edge["source_label"] == source["label"]
    assert edge["target_label"] == target["label"]
    assert edge["label"] == "RESOLVES_TO"
    assert edge["provenance"]["source"] == "manual_link"


def test_graph_includes_entity_match_candidates():
    inv_res = client.post("/api/investigations", json={"title": "Graph Match Test"})
    assert inv_res.status_code == 200
    inv_id = inv_res.json()["id"]

    first = client.post(
        f"/api/investigations/{inv_id}/entities",
        json={"type": "organization", "label": "Acme Corporation"},
    ).json()
    second = client.post(
        f"/api/investigations/{inv_id}/entities",
        json={"type": "organization", "label": "Acme Corp"},
    ).json()
    third = client.post(
        f"/api/investigations/{inv_id}/entities",
        json={"type": "email", "label": "analyst@example.com"},
    ).json()
    fourth = client.post(
        f"/api/investigations/{inv_id}/entities",
        json={"type": "email", "label": "analyst@example.com"},
    ).json()

    graph = client.get(f"/api/investigations/{inv_id}/graph")
    assert graph.status_code == 200
    matches = graph.json()["matches"]
    assert any(
        {match["entity_a"]["id"], match["entity_b"]["id"]} == {first["id"], second["id"]}
        for match in matches
    )
    assert any(
        {match["entity_a"]["id"], match["entity_b"]["id"]} == {third["id"], fourth["id"]}
        for match in matches
    )

    confirmed = client.post(
        f"/api/investigations/{inv_id}/relationships",
        json={"source_id": first["id"], "target_id": second["id"], "type": "MATCHES"},
    )
    assert confirmed.status_code == 200

    refreshed_graph = client.get(f"/api/investigations/{inv_id}/graph").json()
    assert any(
        {match["entity_a"]["id"], match["entity_b"]["id"]} == {third["id"], fourth["id"]}
        for match in refreshed_graph["matches"]
    )
    confirmed_exact = client.post(
        f"/api/investigations/{inv_id}/relationships",
        json={"source_id": third["id"], "target_id": fourth["id"], "type": "MATCHES"},
    )
    assert confirmed_exact.status_code == 200

    refreshed_graph = client.get(f"/api/investigations/{inv_id}/graph").json()
    assert refreshed_graph["matches"] == []
    assert sum(edge["label"] == "MATCHES" for edge in refreshed_graph["edges"]) == 2
