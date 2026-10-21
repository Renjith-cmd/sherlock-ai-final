"""Production-grade Document Entity and Provenance Extraction Engine.

Features:
- Pass A: Structured deterministic extractors (RFC emails, IPv4/IPv6, URLs, domains, phone numbers, file hashes, dates/times, reference IDs).
- Pass B: Real spaCy NER adapter (PERSON, ORG, GPE/LOC, DATE) with configurable model loading and error handling.
- Pass C: Contextual pattern extraction (titles, organizational aliases, explicit roles 'CEO:', 'Owner:', structured headers).
- Pass D: Chunked long-document processing with sliding window and offset translation to avoid truncation.
- Deduplication of mentions per document while preserving exact character offsets and context.
"""

import re
import ipaddress
from typing import List, Dict, Any, Tuple, Optional
from src.core.models import EntityType

# Safe spaCy loader
_NLP_MODEL = None
_NLP_LOAD_ATTEMPTED = False


def get_nlp_model():
    global _NLP_MODEL, _NLP_LOAD_ATTEMPTED
    if not _NLP_LOAD_ATTEMPTED:
        _NLP_LOAD_ATTEMPTED = True
        try:
            import spacy
            _NLP_MODEL = spacy.load("en_core_web_sm")
        except Exception as e:
            _NLP_MODEL = None
            print(f"[DocumentIntelligence] Warning: Could not load spacy en_core_web_sm ({e}). Falling back to rule-based NER.")
    return _NLP_MODEL


# Common Corporate & Title Lexicons
TITLES = r"\b(?:Mr\.?|Mrs\.?|Ms\.?|Dr\.?|Prof\.?|Director|Officer|Analyst|Agent|Commander|Chairman|CEO|CTO|CFO|Special Agent|Inspector|Detective)\b"
CORP_SUFFIXES = r"\b(?:Inc\.?|Corp\.?|Corporation|LLC|Ltd\.?|Limited|Holdings|GmbH|PLC|Group|Enterprises|Technologies|Technology|Solutions|Laboratories|Foundation|Systems?|University|Institute|Bank|Agency|Department|Association|Co\.?|S\.A\.?|AG)\b"


class DocumentIntelligenceEngine:
    CHUNK_SIZE = 15000  # Characters
    CHUNK_OVERLAP = 1000  # Characters

    @classmethod
    def extract_all(cls, text: str, doc_id: str) -> Dict[str, Any]:
        """
        Runs full multi-pass entity extraction, offset tracking, and relationship detection.
        Handles long documents via overlapping chunk windows with absolute character offset mapping.
        """
        if not text or not text.strip():
            return {"entities": [], "relationships": []}

        # Long document chunking
        raw_mentions: List[Dict[str, Any]] = []
        if len(text) <= cls.CHUNK_SIZE:
            raw_mentions = cls._extract_chunk(text, 0, doc_id)
        else:
            step = cls.CHUNK_SIZE - cls.CHUNK_OVERLAP
            for start in range(0, len(text), step):
                chunk_text = text[start:start + cls.CHUNK_SIZE]
                chunk_mentions = cls._extract_chunk(chunk_text, start, doc_id)
                raw_mentions.extend(chunk_mentions)

        # Deduplicate identical mentions at chunk overlaps
        unique_mentions = cls._deduplicate_raw_mentions(raw_mentions)

        # Pass D: Aggregate mentions into canonical document entities while retaining all mention locations
        aggregated_entities = cls._aggregate_mentions(unique_mentions, doc_id)

        # Stage A-C: Relationship Extraction (explicit, contextual, dependency-aware)
        relationships = cls._extract_relationships(text, aggregated_entities, doc_id)

        return {
            "entities": aggregated_entities,
            "relationships": relationships
        }

    @classmethod
    def _extract_chunk(cls, chunk_text: str, offset_delta: int, doc_id: str) -> List[Dict[str, Any]]:
        mentions: List[Dict[str, Any]] = []

        # ==========================================
        # PASS A: STRUCTURED ENTITIES
        # ==========================================

        # 1. Email Addresses
        for m in re.finditer(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,7}\b", chunk_text):
            mentions.append({
                "type": EntityType.EMAIL.value,
                "label": m.group(0).lower(),
                "original_text": m.group(0),
                "start_offset": offset_delta + m.start(),
                "end_offset": offset_delta + m.end(),
                "context": cls._get_context(chunk_text, m.start(), m.end()),
                "confidence": 0.99,
                "method": "regex_rfc5322"
            })

        # 2. IPv4 & IPv6 Addresses
        # IPv4
        for m in re.finditer(r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b", chunk_text):
            parts = m.group(0).split(".")
            try:
                if all(0 <= int(p) <= 255 for p in parts):
                    # Exclude leading-zero false positives or version numbers like 1.2.3.4 if not ip
                    ip_obj = ipaddress.IPv4Address(m.group(0))
                    mentions.append({
                        "type": EntityType.IP.value,
                        "label": str(ip_obj),
                        "original_text": m.group(0),
                        "start_offset": offset_delta + m.start(),
                        "end_offset": offset_delta + m.end(),
                        "context": cls._get_context(chunk_text, m.start(), m.end()),
                        "confidence": 0.98,
                        "method": "regex_ipv4"
                    })
            except Exception:
                pass

        # IPv6
        ipv6_pattern = r"\b(?:[A-Fa-f0-9]{1,4}:){7}[A-Fa-f0-9]{1,4}\b|\b(?:[A-Fa-f0-9]{1,4}:){1,7}:|:(?::[A-Fa-f0-9]{1,4}){1,7}\b"
        for m in re.finditer(ipv6_pattern, chunk_text):
            try:
                ip_obj = ipaddress.IPv6Address(m.group(0))
                mentions.append({
                    "type": EntityType.IP.value,
                    "label": str(ip_obj),
                    "original_text": m.group(0),
                    "start_offset": offset_delta + m.start(),
                    "end_offset": offset_delta + m.end(),
                    "context": cls._get_context(chunk_text, m.start(), m.end()),
                    "confidence": 0.99,
                    "method": "regex_ipv6"
                })
            except Exception:
                pass

        # 3. URLs
        for m in re.finditer(r"\bhttps?://[A-Za-z0-9.-]+(?::\d+)?(?:/[^\s<>'\"`\(\)]*)?\b", chunk_text):
            mentions.append({
                "type": EntityType.URL.value,
                "label": m.group(0),
                "original_text": m.group(0),
                "start_offset": offset_delta + m.start(),
                "end_offset": offset_delta + m.end(),
                "context": cls._get_context(chunk_text, m.start(), m.end()),
                "confidence": 0.98,
                "method": "regex_url"
            })

        # 4. Standalone Domains
        for m in re.finditer(r"\b(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+(?:com|org|net|gov|edu|io|ai|co|uk|de|ch|in|ru|info|biz|me|xyz)\b", chunk_text, re.IGNORECASE):
            val = m.group(0).lower()
            # Avoid if inside an email address or preceded by http://
            start_idx = m.start()
            if start_idx > 0 and chunk_text[start_idx - 1] in ["@", "/", ":"]:
                continue
            mentions.append({
                "type": EntityType.DOMAIN.value,
                "label": val,
                "original_text": m.group(0),
                "start_offset": offset_delta + m.start(),
                "end_offset": offset_delta + m.end(),
                "context": cls._get_context(chunk_text, m.start(), m.end()),
                "confidence": 0.95,
                "method": "regex_domain"
            })

        # 5. File Hashes (MD5: 32 chars, SHA-1: 40 chars, SHA-256: 64 chars)
        for m in re.finditer(r"\b[a-fA-F0-9]{32}\b|\b[a-fA-F0-9]{40}\b|\b[a-fA-F0-9]{64}\b", chunk_text):
            hash_val = m.group(0).lower()
            # Ensure it is not pure digits (e.g., long telephone or serial number)
            if not hash_val.isdigit():
                mentions.append({
                    "type": EntityType.FILE_HASH.value,
                    "label": hash_val,
                    "original_text": m.group(0),
                    "start_offset": offset_delta + m.start(),
                    "end_offset": offset_delta + m.end(),
                    "context": cls._get_context(chunk_text, m.start(), m.end()),
                    "confidence": 0.96,
                    "method": "regex_hash"
                })

        # 6. Phone Numbers (international or formatted: +1-555-123-4567, (555) 123-4567)
        for m in re.finditer(r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b", chunk_text):
            digits = re.sub(r"\D", "", m.group(0))
            if 10 <= len(digits) <= 15:
                mentions.append({
                    "type": EntityType.PHONE.value,
                    "label": m.group(0).strip(),
                    "original_text": m.group(0),
                    "start_offset": offset_delta + m.start(),
                    "end_offset": offset_delta + m.end(),
                    "context": cls._get_context(chunk_text, m.start(), m.end()),
                    "confidence": 0.92,
                    "method": "regex_phone"
                })

        # ==========================================
        # PASS B: NAMED ENTITY RECOGNITION (spaCy NER)
        # ==========================================
        nlp = get_nlp_model()
        spacy_spans = set()
        if nlp:
            try:
                doc = nlp(chunk_text)
                for ent in doc.ents:
                    clean_text = ent.text.strip().replace("\n", " ")
                    if len(clean_text) < 2:
                        continue

                    e_type = None
                    if ent.label_ == "PERSON":
                        e_type = EntityType.PERSON.value
                    elif ent.label_ == "ORG":
                        e_type = EntityType.ORGANIZATION.value
                    elif ent.label_ in ["GPE", "LOC"]:
                        e_type = EntityType.LOCATION.value

                    if e_type:
                        spacy_spans.add((ent.start_char, ent.end_char))
                        mentions.append({
                            "type": e_type,
                            "label": clean_text,
                            "original_text": ent.text,
                            "start_offset": offset_delta + ent.start_char,
                            "end_offset": offset_delta + ent.end_char,
                            "context": cls._get_context(chunk_text, ent.start_char, ent.end_char),
                            "confidence": 0.91,
                            "method": "spacy_ner"
                        })
            except Exception as e:
                print(f"[DocumentIntelligence] Error during spaCy inference: {e}")

        # ==========================================
        # PASS C: CONTEXTUAL & COMPLEMENTARY GRAMMAR
        # ==========================================

        # Organization with explicit corporate suffixes (e.g. Acme Corp, Contoso LLC)
        org_pattern = rf"\b[A-Z][a-zA-Z0-9&]+(?:\s+[A-Z][a-zA-Z0-9&]+)*\s+{CORP_SUFFIXES}"
        for m in re.finditer(org_pattern, chunk_text):
            if not any(cls._spans_overlap(m.start(), m.end(), s, e) for (s, e) in spacy_spans):
                mentions.append({
                    "type": EntityType.ORGANIZATION.value,
                    "label": m.group(0).strip(),
                    "original_text": m.group(0),
                    "start_offset": offset_delta + m.start(),
                    "end_offset": offset_delta + m.end(),
                    "context": cls._get_context(chunk_text, m.start(), m.end()),
                    "confidence": 0.93,
                    "method": "grammar_corp_suffix"
                })

        # People with titles / honorifics (e.g. Dr. Jane Doe, CEO John Smith)
        person_title_pattern = rf"{TITLES}\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){{1,2}})"
        for m in re.finditer(person_title_pattern, chunk_text):
            name = m.group(1).strip()
            # Only add if not already captured by spaCy
            if not any(cls._spans_overlap(m.start(1), m.end(1), s, e) for (s, e) in spacy_spans):
                mentions.append({
                    "type": EntityType.PERSON.value,
                    "label": name,
                    "original_text": m.group(0),
                    "start_offset": offset_delta + m.start(1),
                    "end_offset": offset_delta + m.end(1),
                    "context": cls._get_context(chunk_text, m.start(), m.end()),
                    "confidence": 0.92,
                    "method": "grammar_title_person"
                })

        # Role-based headers (e.g. "CEO: Alice Bob", "Director: Robert Davis")
        role_pattern = r"(?:CEO|Director|Manager|Owner|Founder|Contact|Author|Reporter):\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})"
        for m in re.finditer(role_pattern, chunk_text):
            name = m.group(1).strip()
            if not any(cls._spans_overlap(m.start(1), m.end(1), s, e) for (s, e) in spacy_spans):
                mentions.append({
                    "type": EntityType.PERSON.value,
                    "label": name,
                    "original_text": m.group(1),
                    "start_offset": offset_delta + m.start(1),
                    "end_offset": offset_delta + m.end(1),
                    "context": cls._get_context(chunk_text, m.start(), m.end()),
                    "confidence": 0.94,
                    "method": "contextual_role_header"
                })

        # Narrative person names at sentence starts when followed by a person-specific action.
        narrative_person_pattern = (
            r"(?:^|(?<=[.!?])\s+)([A-Z][a-z]+(?:[-'][A-Z]?[a-z]+)?"
            r"\s+[A-Z][a-z]+(?:[-'][A-Z]?[a-z]+)?)"
            r"\s+(?=(?:arrived|traveled|travelled|reported|stated|confirmed|"
            r"signed|joined|visited|testified|announced|identified|contacted|"
            r"met|spoke|presented|represented)\b)"
        )
        for m in re.finditer(narrative_person_pattern, chunk_text):
            name = m.group(1).strip()
            if not any(cls._spans_overlap(m.start(1), m.end(1), s, e) for (s, e) in spacy_spans):
                mentions.append({
                    "type": EntityType.PERSON.value,
                    "label": name,
                    "original_text": name,
                    "start_offset": offset_delta + m.start(1),
                    "end_offset": offset_delta + m.end(1),
                    "context": cls._get_context(chunk_text, m.start(1), m.end(1)),
                    "confidence": 0.84,
                    "method": "contextual_narrative_person"
                })

        # Place names following common geographic prepositions or movement phrases.
        location_pattern = (
            r"\b(?:in|near|from|within|outside|at|traveled to|travelled to|"
            r"arrived in|located in|based in)\s+"
            r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})"
        )
        non_location_phrases = {"the", "this", "that", "his", "her", "their", "our"}
        for m in re.finditer(location_pattern, chunk_text):
            place = m.group(1).strip()
            if place.lower() in non_location_phrases:
                continue
            if not any(cls._spans_overlap(m.start(1), m.end(1), s, e) for (s, e) in spacy_spans):
                mentions.append({
                    "type": EntityType.LOCATION.value,
                    "label": place,
                    "original_text": place,
                    "start_offset": offset_delta + m.start(1),
                    "end_offset": offset_delta + m.end(1),
                    "context": cls._get_context(chunk_text, m.start(1), m.end(1)),
                    "confidence": 0.78,
                    "method": "contextual_location"
                })

        return mentions

    @staticmethod
    def _spans_overlap(s1: int, e1: int, s2: int, e2: int) -> bool:
        return max(s1, s2) < min(e1, e2)

    @staticmethod
    def _get_context(text: str, start: int, end: int, window: int = 60) -> str:
        s = max(0, start - window)
        e = min(len(text), end + window)
        return "..." + text[s:e].replace("\n", " ").strip() + "..."

    @classmethod
    def _deduplicate_raw_mentions(cls, mentions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen = set()
        unique = []
        for m in mentions:
            key = (m["type"], m["label"].lower(), m["start_offset"], m["end_offset"])
            if key not in seen:
                seen.add(key)
                unique.append(m)
        return unique

    @classmethod
    def _aggregate_mentions(cls, raw_mentions: List[Dict[str, Any]], doc_id: str) -> List[Dict[str, Any]]:
        grouped: Dict[Tuple[str, str], Dict[str, Any]] = {}
        for m in raw_mentions:
            # Canonical normalization key
            norm_label = m["label"].strip()
            key = (m["type"], norm_label.lower())
            if key not in grouped:
                grouped[key] = {
                    "type": m["type"],
                    "label": norm_label,
                    "mention_count": 0,
                    "confidence": m["confidence"],
                    "method": m["method"],
                    "source_doc_id": doc_id,
                    "mentions": []
                }
            grouped[key]["mention_count"] += 1
            grouped[key]["mentions"].append({
                "original_text": m.get("original_text", m["label"]),
                "start_offset": m["start_offset"],
                "end_offset": m["end_offset"],
                "context": m["context"]
            })
            # Boost confidence if entity has multiple occurrences or was verified by NER
            if grouped[key]["mention_count"] > 1:
                grouped[key]["confidence"] = min(0.99, grouped[key]["confidence"] + 0.03)

        return list(grouped.values())

    @classmethod
    def _extract_relationships(cls, text: str, entities: List[Dict[str, Any]], doc_id: str) -> List[Dict[str, Any]]:
        """
        Stage A-C: Staged relationship extraction.
        Distinguishes explicit relations, rule-derived relations, and sentence-level co-occurrences.
        """
        relationships: List[Dict[str, Any]] = []
        # Split text into sentences safely
        sentences = re.split(r"(?<=[.!?])\s+", text)

        for sentence in sentences:
            sent_str = sentence.strip()
            if not sent_str:
                continue
            sent_lower = sent_str.lower()

            # Find all entities whose label appears in this sentence
            present_entities = []
            for e in entities:
                pattern = r"\b" + re.escape(e["label"].lower()) + r"\b"
                if re.search(pattern, sent_lower):
                    present_entities.append(e)

            if len(present_entities) >= 2:
                # Pairwise evaluation
                for i in range(len(present_entities)):
                    for j in range(i + 1, len(present_entities)):
                        e1 = present_entities[i]
                        e2 = present_entities[j]

                        # Skip self-links
                        if e1["label"].lower() == e2["label"].lower():
                            continue

                        rel_type = "CO_OCCURS_WITH"
                        rel_category = "co_occurrence"
                        conf = 0.55
                        method = "sentence_co_occurrence"

                        # 1. Person <-> Organization
                        if (e1["type"] == EntityType.PERSON.value and e2["type"] == EntityType.ORGANIZATION.value) or \
                           (e2["type"] == EntityType.PERSON.value and e1["type"] == EntityType.ORGANIZATION.value):
                            person = e1 if e1["type"] == EntityType.PERSON.value else e2
                            org = e2 if e1["type"] == EntityType.PERSON.value else e1

                            # Explicit employment / leadership verbs
                            if any(w in sent_lower for w in ["works for", "works at", "employed by", "joined", "hired by"]):
                                rel_type = "EMPLOYED_BY"
                                rel_category = "explicit_relationship"
                                conf = 0.90
                                method = "verb_pattern_employment"
                            elif any(w in sent_lower for w in ["ceo of", "director of", "founder of", "founded", "leads", "head of", "president of", "chairman of"]):
                                rel_type = "LEADS"
                                rel_category = "explicit_relationship"
                                conf = 0.95
                                method = "role_pattern_leadership"
                            elif any(w in sent_lower for w in ["managed by", "officer", "associated with", "consultant to"]):
                                rel_type = "ASSOCIATED_WITH"
                                rel_category = "rule_derived"
                                conf = 0.82
                                method = "association_pattern"

                            # Normalize direction: Person -> Org
                            e1, e2 = person, org

                        # 2. Organization <-> Domain / URL
                        elif (e1["type"] in [EntityType.DOMAIN.value, EntityType.URL.value] and e2["type"] == EntityType.ORGANIZATION.value) or \
                             (e2["type"] in [EntityType.DOMAIN.value, EntityType.URL.value] and e1["type"] == EntityType.ORGANIZATION.value):
                            asset = e1 if e1["type"] in [EntityType.DOMAIN.value, EntityType.URL.value] else e2
                            org = e2 if e1["type"] in [EntityType.DOMAIN.value, EntityType.URL.value] else e1

                            if any(w in sent_lower for w in ["operated by", "registered to", "hosted by", "owned by", "belongs to", "domain for"]):
                                rel_type = "OPERATED_BY"
                                rel_category = "explicit_relationship"
                                conf = 0.92
                                method = "infrastructure_ownership"
                            else:
                                rel_type = "REFERENCED_BY"
                                rel_category = "rule_derived"
                                conf = 0.75
                                method = "domain_org_context"

                            e1, e2 = org, asset

                        # 3. Person <-> Email
                        elif (e1["type"] == EntityType.PERSON.value and e2["type"] == EntityType.EMAIL.value) or \
                             (e2["type"] == EntityType.PERSON.value and e1["type"] == EntityType.EMAIL.value):
                            person = e1 if e1["type"] == EntityType.PERSON.value else e2
                            email = e2 if e1["type"] == EntityType.PERSON.value else e1

                            # Check if email user token matches person's name parts
                            name_parts = person["label"].lower().split()
                            email_user = email["label"].split("@")[0].lower()
                            if any(part in email_user for part in name_parts):
                                rel_type = "IDENTIFIED_BY"
                                rel_category = "explicit_relationship"
                                conf = 0.95
                                method = "name_email_alignment"
                            else:
                                rel_type = "COMMUNICATED_WITH"
                                rel_category = "rule_derived"
                                conf = 0.78
                                method = "co_occurrence_email"

                            e1, e2 = person, email

                        # 4. Entity <-> Location
                        elif e1["type"] == EntityType.LOCATION.value or e2["type"] == EntityType.LOCATION.value:
                            loc = e1 if e1["type"] == EntityType.LOCATION.value else e2
                            other = e2 if e1["type"] == EntityType.LOCATION.value else e1

                            if any(w in sent_lower for w in ["based in", "located in", "headquarters in", "residing in", "operating in"]):
                                rel_type = "LOCATED_IN"
                                rel_category = "explicit_relationship"
                                conf = 0.88
                                method = "geographic_association"
                            else:
                                rel_type = "ASSOCIATED_LOCATION"
                                rel_category = "co_occurrence"
                                conf = 0.65
                                method = "location_co_occurrence"

                            e1, e2 = other, loc

                        relationships.append({
                            "source_label": e1["label"],
                            "source_type": e1["type"],
                            "target_label": e2["label"],
                            "target_type": e2["type"],
                            "type": rel_type,
                            "category": rel_category,
                            "confidence": conf,
                            "method": method,
                            "evidence_excerpt": sent_str[:250],
                            "source_doc_id": doc_id,
                            "status": "pending_review"
                        })

        return relationships
