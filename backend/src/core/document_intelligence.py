"""Comprehensive Document Entity and Relationship Extraction Engine."""

import re
from typing import List, Dict, Any, Tuple
from src.core.models import EntityType


# Common Title Honorifics and Corporate suffixes for deterministic grammar parsing
TITLES = r"\b(?:Mr\.?|Mrs\.?|Ms\.?|Dr\.?|Prof\.?|Director|Officer|Analyst|Agent|Commander|Chairman|CEO|CTO|CFO|Special Agent)\b"
CORP_SUFFIXES = r"\b(?:Inc\.?|Corp\.?|LLC|Ltd\.?|Holdings|GmbH|PLC|Group|Enterprises|Technologies|Solutions|Laboratories|Foundation)\b"


class DocumentIntelligenceEngine:
    @classmethod
    def extract_all(cls, text: str, doc_id: str) -> Dict[str, Any]:
        """
        Runs full deterministic entity extraction, offset tracking, and relationship detection.
        Returns: {
            "entities": List[Dict],
            "relationships": List[Dict]
        }
        """
        entities: List[Dict[str, Any]] = []

        # 1. Emails
        for m in re.finditer(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,7}\b", text):
            entities.append({
                "type": EntityType.EMAIL.value,
                "label": m.group(0).lower(),
                "start_offset": m.start(),
                "end_offset": m.end(),
                "context": cls._get_context(text, m.start(), m.end()),
                "confidence": 0.99,
                "method": "regex_rfc5322"
            })

        # 2. IPv4
        for m in re.finditer(r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b", text):
            parts = [int(p) for p in m.group(0).split(".")]
            if all(0 <= p <= 255 for p in parts):
                entities.append({
                    "type": EntityType.IP.value,
                    "label": m.group(0),
                    "start_offset": m.start(),
                    "end_offset": m.end(),
                    "context": cls._get_context(text, m.start(), m.end()),
                    "confidence": 0.99,
                    "method": "regex_ipv4"
                })

        # 3. URLs
        for m in re.finditer(r"\bhttps?://[A-Za-z0-9.-]+(?::\d+)?(?:/[^\s]*)?\b", text):
            entities.append({
                "type": EntityType.URL.value,
                "label": m.group(0),
                "start_offset": m.start(),
                "end_offset": m.end(),
                "context": cls._get_context(text, m.start(), m.end()),
                "confidence": 0.98,
                "method": "regex_url"
            })

        # 4. Domains (standalone)
        for m in re.finditer(r"\b(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+(?:com|org|net|gov|edu|io|ai|co|uk|de|ch|in|ru|info)\b", text, re.IGNORECASE):
            val = m.group(0).lower()
            # Avoid matching emails already caught
            if "@" not in val and not any(e["label"] == val for e in entities if e["type"] == EntityType.EMAIL.value):
                entities.append({
                    "type": EntityType.DOMAIN.value,
                    "label": val,
                    "start_offset": m.start(),
                    "end_offset": m.end(),
                    "context": cls._get_context(text, m.start(), m.end()),
                    "confidence": 0.95,
                    "method": "regex_tld"
                })

        # 5. Organizations (Pattern with corporate indicators or Capitalized Organization phrases)
        org_pattern = rf"\b[A-Z][a-zA-Z0-9&]+(?:\s+[A-Z][a-zA-Z0-9&]+)*\s+{CORP_SUFFIXES}"
        for m in re.finditer(org_pattern, text):
            entities.append({
                "type": EntityType.ORGANIZATION.value,
                "label": m.group(0).strip(),
                "start_offset": m.start(),
                "end_offset": m.end(),
                "context": cls._get_context(text, m.start(), m.end()),
                "confidence": 0.92,
                "method": "grammar_corp_suffix"
            })

        # 6. People (Titles + Proper Names OR capitalized 2-3 word sequences not matching organizations)
        person_pattern = rf"{TITLES}\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){{1,2}})"
        for m in re.finditer(person_pattern, text):
            name = m.group(1).strip()
            entities.append({
                "type": EntityType.PERSON.value,
                "label": name,
                "start_offset": m.start(),
                "end_offset": m.end(),
                "context": cls._get_context(text, m.start(), m.end()),
                "confidence": 0.90,
                "method": "grammar_title_name"
            })

        # Deduplicate mentions into aggregated entities with multiple occurrences
        aggregated_entities = cls._aggregate_mentions(entities, doc_id)

        # 7. Relationship Extraction (sentence-level co-occurrence and explicit association verbs)
        relationships = cls._extract_relationships(text, aggregated_entities, doc_id)

        return {
            "entities": aggregated_entities,
            "relationships": relationships
        }

    @staticmethod
    def _get_context(text: str, start: int, end: int, window: int = 60) -> str:
        s = max(0, start - window)
        e = min(len(text), end + window)
        return "..." + text[s:e].replace("\n", " ").strip() + "..."

    @classmethod
    def _aggregate_mentions(cls, raw_mentions: List[Dict[str, Any]], doc_id: str) -> List[Dict[str, Any]]:
        grouped: Dict[Tuple[str, str], Dict[str, Any]] = {}
        for m in raw_mentions:
            key = (m["type"], m["label"])
            if key not in grouped:
                grouped[key] = {
                    "type": m["type"],
                    "label": m["label"],
                    "mention_count": 0,
                    "confidence": m["confidence"],
                    "method": m["method"],
                    "source_doc_id": doc_id,
                    "mentions": []
                }
            grouped[key]["mention_count"] += 1
            grouped[key]["mentions"].append({
                "start_offset": m["start_offset"],
                "end_offset": m["end_offset"],
                "context": m["context"]
            })
        return list(grouped.values())

    @classmethod
    def _extract_relationships(cls, text: str, entities: List[Dict[str, Any]], doc_id: str) -> List[Dict[str, Any]]:
        relationships: List[Dict[str, Any]] = []
        sentences = re.split(r"(?<=[.!?])\s+", text)

        for sentence in sentences:
            sent_lower = sentence.lower()
            present_entities = [e for e in entities if e["label"].lower() in sent_lower]

            if len(present_entities) >= 2:
                # Pairwise relationships
                for i in range(len(present_entities)):
                    for j in range(i + 1, len(present_entities)):
                        e1 = present_entities[i]
                        e2 = present_entities[j]

                        rel_type = "CO_OCCURS_WITH"
                        conf = 0.60

                        # Check for employment / association verbs
                        if (e1["type"] == EntityType.PERSON.value and e2["type"] == EntityType.ORGANIZATION.value) or \
                           (e2["type"] == EntityType.PERSON.value and e1["type"] == EntityType.ORGANIZATION.value):
                            if any(w in sent_lower for w in ["works at", "employed by", "director of", "ceo of", "managed by", "officer"]):
                                rel_type = "ASSOCIATED_WITH"
                                conf = 0.85

                        # Check for domain/url hosting or ownership
                        if (e1["type"] in [EntityType.DOMAIN.value, EntityType.URL.value] and e2["type"] == EntityType.ORGANIZATION.value) or \
                           (e2["type"] in [EntityType.DOMAIN.value, EntityType.URL.value] and e1["type"] == EntityType.ORGANIZATION.value):
                            if any(w in sent_lower for w in ["operated by", "registered to", "hosted by", "belongs to"]):
                                rel_type = "OPERATED_BY"
                                conf = 0.88

                        relationships.append({
                            "source_label": e1["label"],
                            "source_type": e1["type"],
                            "target_label": e2["label"],
                            "target_type": e2["type"],
                            "type": rel_type,
                            "confidence": conf,
                            "evidence_excerpt": sentence.strip().replace("\n", " ")[:200],
                            "source_doc_id": doc_id,
                            "status": "pending_review"
                        })

        return relationships
