"""Tests for Phase 7 Graph Analysis tools: shortest path, degrees, and connected components."""

from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)


def test_graph_analytics_and_shortest_path():
    # 1. Create Investigation
    inv_res = client.post("/api/investigations", json={"title": "Topology Analysis Case"})
    inv_id = inv_res.json()["id"]

    # 2. Create chain A -> B -> C and isolated node D
    node_a = client.post(f"/api/investigations/{inv_id}/entities", json={"type": "domain", "label": "node-a.com"}).json()
    node_b = client.post(f"/api/investigations/{inv_id}/entities", json={"type": "ip", "label": "10.0.0.1"}).json()
    node_c = client.post(f"/api/investigations/{inv_id}/entities", json={"type": "domain", "label": "node-c.com"}).json()
    node_d = client.post(f"/api/investigations/{inv_id}/entities", json={"type": "domain", "label": "isolated-node.com"}).json()

    # Link A -> B and B -> C
    client.post(f"/api/investigations/{inv_id}/relationships", json={"source_id": node_a["id"], "target_id": node_b["id"], "type": "LINK"})
    client.post(f"/api/investigations/{inv_id}/relationships", json={"source_id": node_b["id"], "target_id": node_c["id"], "type": "LINK"})

    # 3. Test Analytics
    analytics_res = client.get(f"/api/investigations/{inv_id}/analytics")
    assert analytics_res.status_code == 200
    metrics = analytics_res.json()

    assert metrics["node_count"] == 4
    assert metrics["edge_count"] == 2
    assert metrics["connected_components_count"] == 2  # {A,B,C} and {D}
    assert metrics["top_hubs"][0]["id"] == node_b["id"]  # Node B has degree 2

    # 4. Test Shortest Path (A to C)
    path_res = client.get(f"/api/investigations/{inv_id}/path?start_id={node_a['id']}&end_id={node_c['id']}")
    assert path_res.status_code == 200
    path_data = path_res.json()
    assert path_data["length"] == 2
    assert path_data["path"] == [node_a["id"], node_b["id"], node_c["id"]]

    # 5. Test Shortest Path to Disconnected Node (A to D) -> 404
    no_path = client.get(f"/api/investigations/{inv_id}/path?start_id={node_a['id']}&end_id={node_d['id']}")
    assert no_path.status_code == 404
