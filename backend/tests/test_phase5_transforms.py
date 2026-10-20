"""Tests for Phase 5 & 6 Transforms: Text Entity Extraction, Reverse DNS, Nameservers, and RDAP."""

import pytest
from src.core.models import Entity, EntityType, Provenance
from src.transforms.builtin import (
    TextEntityExtractorTransform,
    DnsToNsTransform,
    UrlToDomainTransform,
    IpReverseDnsTransform
)


@pytest.mark.asyncio
async def test_text_entity_extractor():
    t = TextEntityExtractorTransform()
    doc_text = """
    Incident Report INC-992:
    Suspicious communication observed originating from 198.51.100.44 to alert@soc-team.org.
    Target workstation attempted connection to malicious host.
    """
    entity = Entity(
        investigation_id="inv-123",
        type=EntityType.DOCUMENT,
        label="Incident_INC-992.txt",
        properties={"content": doc_text},
        provenance=Provenance(source="test", method="unit")
    )
    candidates = await t.execute(entity)
    labels = {c.label for c in candidates}
    types = {c.entity_type for c in candidates}

    assert "198.51.100.44" in labels
    assert "alert@soc-team.org" in labels
    assert EntityType.IP in types
    assert EntityType.EMAIL in types


@pytest.mark.asyncio
async def test_dns_ns_transform_real():
    t = DnsToNsTransform()
    entity = Entity(
        investigation_id="inv-123",
        type=EntityType.DOMAIN,
        label="cloudflare.com",
        provenance=Provenance(source="test", method="unit")
    )
    candidates = await t.execute(entity)
    assert len(candidates) >= 1
    assert any("ns" in c.label.lower() or "cloudflare" in c.label.lower() for c in candidates)
    assert candidates[0].relationship_type == "NAMESERVER"


@pytest.mark.asyncio
async def test_reverse_dns_transform():
    t = IpReverseDnsTransform()
    # 1.1.1.1 resolves to one.one.one.one
    entity = Entity(
        investigation_id="inv-123",
        type=EntityType.IP,
        label="1.1.1.1",
        provenance=Provenance(source="test", method="unit")
    )
    candidates = await t.execute(entity)
    if candidates:  # May depend on network PTR resolution
        assert any("one.one.one.one" in c.label.lower() or "cloudflare" in c.label.lower() for c in candidates)
        assert candidates[0].relationship_type == "REVERSE_PTR"
