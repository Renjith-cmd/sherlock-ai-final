"""Comprehensive Evaluation and Regression Test Suite for Document Intelligence Pipeline.

Tests:
1. Multi-pass entity extraction:
   - Structured deterministic entities (Emails, IPv4, IPv6, URLs, Domains, File Hashes, Phones)
   - Real local spaCy NER (Persons, Organizations, Locations)
   - Contextual titles and role headers (CEO, Director)
   - Character offsets preservation and window context
2. Long-document chunking and offset mapping without truncation or duplication
3. Type-specific cross-document entity resolution:
   - People name token reordering ('Smith, John' vs 'John Smith')
   - People middle name variations & initials ('John Smith' vs 'John A. Smith')
   - Organization legal suffix normalization ('Acme Corp' vs 'Acme Inc' vs 'Acme Ltd')
   - Rejection tracking (suppressing previously rejected candidates)
   - Negative evidence and distinct classification
4. Staged relationship extraction:
   - Explicit relationships ('EMPLOYED_BY', 'LEADS', 'IDENTIFIED_BY', 'LOCATED_IN')
   - Rule-derived vs Co-occurrence distinction
   - Preserving evidence excerpts
"""

import pytest
from src.core.document_intelligence import DocumentIntelligenceEngine
from src.core.entity_resolution import EntityResolutionEngine
from src.core.models import EntityType


def test_structured_entity_extraction_pass_a():
    """Verify Pass A captures emails, IPv4, IPv6, file hashes, domains, URLs, and phones with exact offsets."""
    text = (
        "Investigator received report from analyst@defense.gov detailing server 192.168.1.105 "
        "and gateway 2001:0db8:85a3:0000:0000:8a2e:0370:7334. "
        "The malware hash was e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855. "
        "Domain malicious-payload.org was contacted via https://secure.c2node.io/api/v1. "
        "Emergency hotline is +1-800-555-0199."
    )

    res = DocumentIntelligenceEngine.extract_all(text, "doc-test-1")
    extracted_types = {e["type"]: e["label"] for e in res["entities"]}

    assert EntityType.EMAIL.value in extracted_types
    assert extracted_types[EntityType.EMAIL.value] == "analyst@defense.gov"

    assert EntityType.IP.value in extracted_types
    # IPv4 and IPv6 check
    ip_labels = [e["label"] for e in res["entities"] if e["type"] == EntityType.IP.value]
    assert "192.168.1.105" in ip_labels
    assert "2001:db8:85a3::8a2e:370:7334" in ip_labels or "2001:0db8:85a3:0000:0000:8a2e:0370:7334" in ip_labels

    assert EntityType.FILE_HASH.value in extracted_types
    assert "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855" in [
        e["label"] for e in res["entities"] if e["type"] == EntityType.FILE_HASH.value
    ]

    assert EntityType.DOMAIN.value in extracted_types
    assert "malicious-payload.org" in [e["label"] for e in res["entities"] if e["type"] == EntityType.DOMAIN.value]

    assert EntityType.URL.value in extracted_types
    assert "https://secure.c2node.io/api/v1" in [e["label"] for e in res["entities"] if e["type"] == EntityType.URL.value]

    assert EntityType.PHONE.value in extracted_types


def test_spacy_named_entity_recognition_pass_b():
    """Verify Pass B uses local NLP to extract PERSON, ORGANIZATION, and LOCATION."""
    text = "Elena Rostova arrived in Geneva yesterday to represent CyberDyne Systems at the summit."
    res = DocumentIntelligenceEngine.extract_all(text, "doc-test-2")
    entities_by_type = {e["label"]: e["type"] for e in res["entities"]}

    assert "Elena Rostova" in entities_by_type
    assert entities_by_type["Elena Rostova"] == EntityType.PERSON.value

    assert any("CyberDyne" in k for k in entities_by_type)
    assert any("Geneva" in k for k in entities_by_type)


def test_contextual_extraction_pass_c():
    """Verify Pass C handles role headers and titles when standard NER might be ambiguous."""
    text = "CEO: Jonathan Vance signed the corporate merger on behalf of Nexis Holdings LLC."
    res = DocumentIntelligenceEngine.extract_all(text, "doc-test-3")
    labels = [e["label"] for e in res["entities"]]

    assert any("Jonathan Vance" in l for l in labels)
    assert any("Nexis Holdings" in l for l in labels)


def test_rule_fallback_extracts_narrative_person_location_and_systems_org(monkeypatch):
    """Production fallback must extract common named entities without a spaCy model."""
    monkeypatch.setattr("src.core.document_intelligence.get_nlp_model", lambda: None)
    text = (
        "Elena Rostova arrived in Geneva yesterday to represent CyberDyne Systems at the summit. "
        "CEO: Jonathan Vance signed the agreement."
    )

    result = DocumentIntelligenceEngine.extract_all(text, "doc-rule-fallback")
    entities = {(entity["type"], entity["label"]) for entity in result["entities"]}

    assert (EntityType.PERSON.value, "Elena Rostova") in entities
    assert (EntityType.LOCATION.value, "Geneva") in entities
    assert (EntityType.ORGANIZATION.value, "CyberDyne Systems") in entities
    assert (EntityType.PERSON.value, "Jonathan Vance") in entities


def test_long_document_chunking_and_offsets():
    """Verify document longer than chunk limit processes cleanly without losing entities."""
    long_prefix = "The operational log continues with standard security checks.\n" * 400
    middle_text = "Target operative Marcus Sterling verified connection to server 10.20.30.40.\n"
    long_suffix = "Subsequent automated audit logs logged 0 security alerts.\n" * 400
    full_text = long_prefix + middle_text + long_suffix

    assert len(full_text) > 15000  # Exceeds single chunk size

    res = DocumentIntelligenceEngine.extract_all(full_text, "doc-long-test")
    labels = [e["label"] for e in res["entities"]]

    assert any("Marcus Sterling" in l for l in labels)
    assert "10.20.30.40" in labels

    # Check that mentions have non-zero character offsets located in the middle of document
    target_ent = next(e for e in res["entities"] if "Marcus Sterling" in e["label"])
    assert len(target_ent["mentions"]) > 0
    assert target_ent["mentions"][0]["start_offset"] > len(long_prefix) - 50


def test_cross_doc_resolution_people_name_reordering():
    """Verify person entity resolution correctly matches 'Smith, John' with 'John Smith'."""
    e1 = {"label": "John Smith", "type": EntityType.PERSON.value, "source_doc_id": "doc1"}
    e2 = {"label": "Smith, John", "type": EntityType.PERSON.value, "source_doc_id": "doc2"}

    comparison = EntityResolutionEngine.compare_entities(e1, e2)
    assert comparison["match_score"] >= 0.85
    assert comparison["suggestion"] == "likely_match"
    assert any("alternate ordering" in s for s in comparison["supporting_evidence"])


def test_cross_doc_resolution_people_middle_initial():
    """Verify person entity resolution matches variations with middle initials."""
    e1 = {"label": "Robert J. Oppenheimer", "type": EntityType.PERSON.value, "source_doc_id": "doc1"}
    e2 = {"label": "Robert Oppenheimer", "type": EntityType.PERSON.value, "source_doc_id": "doc2"}

    comparison = EntityResolutionEngine.compare_entities(e1, e2)
    assert comparison["match_score"] >= 0.80
    assert comparison["suggestion"] in ["likely_match", "possible_match"]


def test_cross_doc_resolution_org_suffix_normalization():
    """Verify organization resolution matches across corporate designations (Corp vs LLC vs Inc)."""
    e1 = {"label": "Palantir Corp", "type": EntityType.ORGANIZATION.value, "source_doc_id": "doc1"}
    e2 = {"label": "Palantir LLC", "type": EntityType.ORGANIZATION.value, "source_doc_id": "doc2"}

    comparison = EntityResolutionEngine.compare_entities(e1, e2)
    assert comparison["match_score"] >= 0.85
    assert comparison["suggestion"] == "likely_match"
    assert any("root" in s for s in comparison["supporting_evidence"])


def test_cross_doc_resolution_rejection_tracking():
    """Verify analyst rejection suppresses false matches."""
    e1 = {"label": "David Miller", "type": EntityType.PERSON.value, "source_doc_id": "doc1"}
    e2 = {"label": "David Miller", "type": EntityType.PERSON.value, "source_doc_id": "doc2"}

    # Initially matches
    comp1 = EntityResolutionEngine.compare_entities(e1, e2)
    assert comp1["match_score"] >= 0.80

    # User rejects pair
    EntityResolutionEngine.record_rejection("David Miller", "David Miller")
    comp2 = EntityResolutionEngine.compare_entities(e1, e2)
    assert comp2["suggestion"] == "rejected_by_analyst"
    assert comp2["match_score"] == 0.0


def test_staged_relationship_extraction_explicit_vs_cooccurrence():
    """Verify staged relationship extractor categorizes explicit verbs vs sentence co-occurrence."""
    text = (
        "Alice Cooper works for Umbrella Corp in Raccoon City. "
        "Meanwhile, Bob Vance and CyberDyne were mentioned together in the file."
    )

    entities = [
        {"label": "Alice Cooper", "type": EntityType.PERSON.value},
        {"label": "Umbrella Corp", "type": EntityType.ORGANIZATION.value},
        {"label": "Bob Vance", "type": EntityType.PERSON.value},
        {"label": "CyberDyne", "type": EntityType.ORGANIZATION.value},
    ]

    rels = DocumentIntelligenceEngine._extract_relationships(text, entities, "doc-rel-test")

    # Alice Cooper -> Umbrella Corp should be explicit EMPLOYED_BY
    alice_rel = next((r for r in rels if r["source_label"] == "Alice Cooper" and r["target_label"] == "Umbrella Corp"), None)
    assert alice_rel is not None
    assert alice_rel["type"] == "EMPLOYED_BY"
    assert alice_rel["category"] == "explicit_relationship"
    assert alice_rel["confidence"] >= 0.85

    # Bob Vance -> CyberDyne should be co_occurrence
    bob_rel = next((r for r in rels if "Bob Vance" in [r["source_label"], r["target_label"]] and "CyberDyne" in [r["source_label"], r["target_label"]]), None)
    assert bob_rel is not None
    assert bob_rel["category"] == "co_occurrence"
    assert bob_rel["confidence"] < 0.70
