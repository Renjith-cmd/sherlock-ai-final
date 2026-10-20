"""Unit and integration tests for the Arkana Investigator backend."""

import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from src.main import app
from src.core.models import Entity, EntityType, Provenance
from src.transforms.builtin import DnsToIpTransform, UrlToDomainTransform, EmailToDomainTransform

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["transforms_loaded"] >= 4


def test_create_and_fetch_investigation():
    res = client.post("/api/investigations", json={"title": "Test Operation", "description": "Verification test"})
    assert res.status_code == 200
    inv = res.json()
    assert inv["title"] == "Test Operation"
    inv_id = inv["id"]

    res_get = client.get(f"/api/investigations/{inv_id}")
    assert res_get.status_code == 200
    assert res_get.json()["id"] == inv_id


def test_add_entity_and_graph():
    # 1. Create Investigation
    inv_res = client.post("/api/investigations", json={"title": "Graph Test Case"})
    inv_id = inv_res.json()["id"]

    # 2. Add Domain Entity
    ent_res = client.post(
        f"/api/investigations/{inv_id}/entities",
        json={"type": "domain", "label": "example.com", "properties": {"registrar": "Test"}}
    )
    assert ent_res.status_code == 200
    entity = ent_res.json()
    assert entity["label"] == "example.com"
    assert entity["type"] == "domain"

    # 3. Retrieve Graph
    graph_res = client.get(f"/api/investigations/{inv_id}/graph")
    assert graph_res.status_code == 200
    graph = graph_res.json()
    assert len(graph["nodes"]) == 1
    assert graph["nodes"][0]["label"] == "example.com"


@pytest.mark.asyncio
async def test_url_to_domain_transform():
    t = UrlToDomainTransform()
    entity = Entity(
        investigation_id="dummy",
        type=EntityType.URL,
        label="https://sub.portal.org/login",
        provenance=Provenance(source="test", method="unit")
    )
    candidates = await t.execute(entity)
    assert len(candidates) == 1
    assert candidates[0].label == "sub.portal.org"
    assert candidates[0].entity_type == EntityType.DOMAIN
    assert candidates[0].relationship_type == "HOSTED_ON"


@pytest.mark.asyncio
async def test_email_to_domain_transform():
    t = EmailToDomainTransform()
    entity = Entity(
        investigation_id="dummy",
        type=EntityType.EMAIL,
        label="analyst@cyberdefense.org",
        provenance=Provenance(source="test", method="unit")
    )
    candidates = await t.execute(entity)
    assert len(candidates) == 1
    assert candidates[0].label == "cyberdefense.org"
    assert candidates[0].entity_type == EntityType.DOMAIN
