"""Comprehensive tests for Document Intelligence, Extraction, Cross-Doc Matching, and Auto-Graph Building."""

import io
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)


def test_document_intelligence_and_extraction_workflow():
    # 1. Create Investigation
    inv = client.post("/api/investigations", json={"title": "Document Intelligence Case"}).json()
    inv_id = inv["id"]

    # 2. Upload Document 1 (Incident briefing text)
    doc1_content = """
    Incident Report 2026-A:
    Special Agent John Smith investigated unauthorized server access at Acme Corp.
    The attacker leveraged domain malware-host.org and connected to IP 198.51.100.77.
    Employee contact alert was sent to security@acme-corp.com.
    """
    files1 = {"file": ("incident_2026_a.txt", io.BytesIO(doc1_content.encode("utf-8")), "text/plain")}
    res1 = client.post(f"/api/investigations/{inv_id}/documents/upload", files=files1)
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["extracted_entities_count"] >= 4
    assert data1["document"]["filename"] == "incident_2026_a.txt"

    # 3. Upload Document 2 (Cross-document correlation text)
    doc2_content = """
    Foreign Advisory Memo:
    Officer John Smith was identified in connection with Acme Corp international branch.
    Primary communication channel observed: security@acme-corp.com.
    """
    files2 = {"file": ("advisory_memo.txt", io.BytesIO(doc2_content.encode("utf-8")), "text/plain")}
    res2 = client.post(f"/api/investigations/{inv_id}/documents/upload", files=files2)
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["cross_document_matches_count"] >= 1

    # 4. Fetch Aggregated Investigation Intelligence
    intel_res = client.get(f"/api/investigations/{inv_id}/intelligence")
    assert intel_res.status_code == 200
    intel = intel_res.json()
    
    entities = intel["entities"]
    matches = intel["matches"]
    relationships = intel["relationships"]

    # Verify extracted entities contains Person, Org, Email, IP, Domain
    labels = {e["label"] for e in entities}
    assert "John Smith" in labels
    assert "Acme Corp" in labels
    assert "security@acme-corp.com" in labels
    assert "198.51.100.77" in labels

    # Verify Cross-Document Match was detected for John Smith / Acme Corp / email
    assert len(matches) >= 1
    top_match = matches[0]
    assert top_match["match_score"] >= 0.75
    assert "supporting_evidence" in top_match

    # 5. Build Graph from Intelligence
    build_payload = {
        "selected_entities": entities[:4],
        "selected_relationships": relationships[:2],
        "include_document_node": True,
        "document_id": data1["document"]["id"]
    }
    build_res = client.post(f"/api/investigations/{inv_id}/intelligence/build-graph", json=build_payload)
    assert build_res.status_code == 200
    build_data = build_res.json()
    assert build_data["status"] == "success"
    assert build_data["nodes_added"] >= 4

    # 6. Verify Investigation Graph now contains document node and linked entities
    graph_res = client.get(f"/api/investigations/{inv_id}/graph").json()
    graph_node_labels = {n["label"] for n in graph_res["nodes"]}
    assert "incident_2026_a.txt" in graph_node_labels
    assert "John Smith" in graph_node_labels
