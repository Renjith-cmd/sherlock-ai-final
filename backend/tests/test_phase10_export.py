"""Tests for Phase 10 Graph Export (JSON/CSV) and Investigation Executive Reporting."""

from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)


def test_export_and_report_generation():
    # 1. Create Investigation
    inv_res = client.post("/api/investigations", json={"title": "Operation Cerberus", "tags": ["apt", "malware"]})
    inv_id = inv_res.json()["id"]

    # 2. Add entities & link
    e1 = client.post(f"/api/investigations/{inv_id}/entities", json={"type": "domain", "label": "c2-domain.com"}).json()
    e2 = client.post(f"/api/investigations/{inv_id}/entities", json={"type": "ip", "label": "198.51.100.2"}).json()
    client.post(
        f"/api/investigations/{inv_id}/relationships",
        json={"source_id": e1["id"], "target_id": e2["id"], "type": "RESOLVES_TO"}
    )

    # 3. Test JSON Export
    json_res = client.get(f"/api/investigations/{inv_id}/export/json")
    assert json_res.status_code == 200
    bundle = json_res.json()
    assert bundle["format_version"] == "1.0.0"
    assert len(bundle["nodes"]) == 2
    assert len(bundle["edges"]) == 1
    assert bundle["investigation"]["title"] == "Operation Cerberus"

    # 4. Test Entities CSV Export
    csv_ent_res = client.get(f"/api/investigations/{inv_id}/export/entities.csv")
    assert csv_ent_res.status_code == 200
    assert "c2-domain.com" in csv_ent_res.text
    assert "198.51.100.2" in csv_ent_res.text
    assert "label" in csv_ent_res.text.split("\n")[0]

    # 5. Test Relationships CSV Export
    csv_rel_res = client.get(f"/api/investigations/{inv_id}/export/relationships.csv")
    assert csv_rel_res.status_code == 200
    assert "RESOLVES_TO" in csv_rel_res.text

    # 6. Test Markdown Investigation Report
    report_res = client.get(f"/api/investigations/{inv_id}/report")
    assert report_res.status_code == 200
    report_text = report_res.text
    assert "# 🔍 Investigation Case Report: Operation Cerberus" in report_text
    assert "Total Discovered Entities**: 2" in report_text
    assert "`c2-domain.com`" in report_text
    assert "**RESOLVES_TO**" in report_text
