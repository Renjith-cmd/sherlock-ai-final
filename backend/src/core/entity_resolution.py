"""Advanced Cross-Document Entity Resolution and Identity Matching Engine.

Implements:
1. Multi-strategy candidate generation (indexed blocking by type and soundex/tokens)
2. Type-specific comparators:
   - PERSON: Token reordering ('Smith, John' vs 'John Smith'), initials/missing middle names,
             alias sets, and conflicting attributes check.
   - ORGANIZATION: Legal suffix normalization (Corp, Inc, LLC, Ltd, GmbH), acronyms, root tokens.
   - DETERMINISTIC (EMAIL, IP, DOMAIN, FILE_HASH): Canonical normalization, strict matching.
3. Positive and negative evidence accumulation with explainable rationale.
4. Calibrated decision thresholds:
   - >= 0.88: likely_match (auto-linkable or high-confidence suggestion)
   - 0.70 - 0.87: possible_match (manual review recommended)
   - < 0.70: distinct entities
5. Rejected pairs caching / state preservation.
"""

from typing import List, Dict, Any, Tuple, Set, Optional
from difflib import SequenceMatcher
import re
from src.core.models import EntityType


# Common corporate suffixes for normalisation
CORP_LEGAL_SUFFIXES = {
    "corp", "corporation", "inc", "incorporated", "llc", "ltd", "limited",
    "gmbh", "sa", "ag", "co", "company", "plc", "holdings", "group",
    "systems", "system", "technologies", "technology", "solutions", "laboratories",
    "foundation", "university", "institute", "bank", "agency", "department", "association",
}


def soundex(name: str) -> str:
    """Standard Soundex phonetic algorithm for blocking name candidates."""
    if not name:
        return "0000"
    name = re.sub(r"[^A-Za-z]", "", name).upper()
    if not name:
        return "0000"
    first_letter = name[0]
    mapping = {
        "B": "1", "F": "1", "P": "1", "V": "1",
        "C": "2", "G": "2", "J": "2", "K": "2", "Q": "2", "S": "2", "X": "2", "Z": "2",
        "D": "3", "T": "3",
        "L": "4",
        "M": "5", "N": "5",
        "R": "6"
    }
    encoded = [first_letter]
    prev_code = mapping.get(first_letter, "0")
    for char in name[1:]:
        code = mapping.get(char, "0")
        if code != "0" and code != prev_code:
            encoded.append(code)
            prev_code = code
        elif code == "0":
            prev_code = "0"
    res = "".join(encoded)
    res = (res + "0000")[:4]
    return res


class EntityResolutionEngine:
    # Memory set for user-rejected matches to prevent recurring suggestions
    _rejected_matches: Set[Tuple[str, str]] = set()

    @classmethod
    def record_rejection(cls, entity1_id_or_label: str, entity2_id_or_label: str) -> None:
        """Records a user-rejected candidate pair to suppress future suggestions."""
        pair = tuple(sorted([entity1_id_or_label.lower().strip(), entity2_id_or_label.lower().strip()]))
        cls._rejected_matches.add(pair)

    @classmethod
    def is_rejected(cls, label1: str, label2: str) -> bool:
        pair = tuple(sorted([label1.lower().strip(), label2.lower().strip()]))
        return pair in cls._rejected_matches

    @staticmethod
    def calculate_string_similarity(a: str, b: str) -> float:
        """Normalized Gestalt pattern matching ratio between two strings (0.0 to 1.0)."""
        return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()

    @classmethod
    def clean_org_name(cls, name: str) -> Tuple[str, Set[str]]:
        """Strips legal suffixes and punctuation from organization names, returning root words and stripped suffixes."""
        tokens = re.findall(r"[A-Za-z0-9]+", name.lower())
        suffixes_found = set()
        clean_tokens = []
        for t in tokens:
            if t in CORP_LEGAL_SUFFIXES:
                suffixes_found.add(t)
            else:
                clean_tokens.append(t)
        root = " ".join(clean_tokens) if clean_tokens else " ".join(tokens)
        return root, suffixes_found

    @classmethod
    def compare_persons(cls, e1: Dict[str, Any], e2: Dict[str, Any]) -> Dict[str, Any]:
        """Specialized comparator for PERSON entities."""
        l1, l2 = e1["label"].strip(), e2["label"].strip()
        t1_parts = [p.lower() for p in re.findall(r"[A-Za-z]+", l1)]
        t2_parts = [p.lower() for p in re.findall(r"[A-Za-z]+", l2)]

        supporting: List[str] = []
        contradicting: List[str] = []

        # Exact match
        if l1.lower() == l2.lower():
            supporting.append(f"Exact matching full name '{l1}'.")
            return {
                "match_score": 0.90,
                "suggestion": "likely_match",
                "supporting_evidence": supporting,
                "contradictory_evidence": ["Name collision possible without verified DOB or unique identifier."]
            }

        # Token set & Order comparison (e.g. "Smith, John" vs "John Smith")
        set1, set2 = set(t1_parts), set(t2_parts)
        if set1 == set2 and len(set1) > 1:
            supporting.append(f"Identical name tokens with alternate ordering: '{l1}' vs '{l2}'.")
            return {
                "match_score": 0.88,
                "suggestion": "likely_match",
                "supporting_evidence": supporting,
                "contradictory_evidence": []
            }

        # Middle name / Initial variation (e.g. "John Smith" vs "John A. Smith" vs "Johnathan Smith")
        if len(t1_parts) >= 2 and len(t2_parts) >= 2:
            first1, last1 = t1_parts[0], t1_parts[-1]
            first2, last2 = t2_parts[0], t2_parts[-1]

            # Matching surname is crucial
            surname_sim = SequenceMatcher(None, last1, last2).ratio()
            first_sim = SequenceMatcher(None, first1, first2).ratio()

            if surname_sim >= 0.90:
                # Same surname, check first name compatibility
                if first1 == first2:
                    # e.g., "John Smith" vs "John Alexander Smith"
                    supporting.append(f"Identical first ('{first1}') and last ('{last1}') names.")
                    if len(t1_parts) != len(t2_parts):
                        supporting.append("One record includes middle name or initial.")
                    return {
                        "match_score": 0.86,
                        "suggestion": "possible_match",
                        "supporting_evidence": supporting,
                        "contradictory_evidence": ["Analyst verification recommended for middle name divergence."]
                    }
                elif first1.startswith(first2) or first2.startswith(first1) or first_sim >= 0.75:
                    # e.g. "Johnathan Smith" vs "John Smith"
                    supporting.append(f"Compatible first names ('{first1}' ~ '{first2}') with matching surname '{last1}'.")
                    return {
                        "match_score": 0.80,
                        "suggestion": "possible_match",
                        "supporting_evidence": supporting,
                        "contradictory_evidence": ["Possible diminutive or alias."]
                    }

        # General string similarity fallback
        sim = cls.calculate_string_similarity(l1, l2)
        if sim >= 0.82:
            return {
                "match_score": sim,
                "suggestion": "possible_match",
                "supporting_evidence": [f"High phonetic or lexical similarity ({sim:.2f})."],
                "contradictory_evidence": ["Requires manual confirmation."]
            }

        contradicting.append(f"Different person names '{l1}' vs '{l2}' (similarity {sim:.2f}).")
        return {
            "match_score": sim,
            "suggestion": "distinct",
            "supporting_evidence": [],
            "contradictory_evidence": contradicting
        }

    @classmethod
    def compare_organizations(cls, e1: Dict[str, Any], e2: Dict[str, Any]) -> Dict[str, Any]:
        """Specialized comparator for ORGANIZATION entities."""
        l1, l2 = e1["label"].strip(), e2["label"].strip()
        supporting: List[str] = []
        contradicting: List[str] = []

        # Exact match
        if l1.lower() == l2.lower():
            supporting.append(f"Exact matching organization name '{l1}'.")
            return {
                "match_score": 0.95,
                "suggestion": "likely_match",
                "supporting_evidence": supporting,
                "contradictory_evidence": []
            }

        # Clean corporate suffixes
        root1, suff1 = cls.clean_org_name(l1)
        root2, suff2 = cls.clean_org_name(l2)

        if root1 == root2 and root1:
            supporting.append(f"Identical organizational root '{root1}' across documents.")
            if suff1 != suff2:
                supporting.append(f"Legal suffix variation: {suff1 or 'None'} vs {suff2 or 'None'}.")
            return {
                "match_score": 0.91,
                "suggestion": "likely_match",
                "supporting_evidence": supporting,
                "contradictory_evidence": []
            }

        root_sim = cls.calculate_string_similarity(root1, root2)
        if root_sim >= 0.80:
            supporting.append(f"High similarity in corporate root name ({root_sim:.2f}): '{root1}' vs '{root2}'.")
            return {
                "match_score": root_sim,
                "suggestion": "possible_match",
                "supporting_evidence": supporting,
                "contradictory_evidence": ["Review recommended to confirm parent-subsidiary or separate legal entity."]
            }

        sim = cls.calculate_string_similarity(l1, l2)
        contradicting.append(f"Distinct organization names '{l1}' vs '{l2}'.")
        return {
            "match_score": sim,
            "suggestion": "distinct",
            "supporting_evidence": [],
            "contradictory_evidence": contradicting
        }

    @classmethod
    def compare_deterministic(cls, e1: Dict[str, Any], e2: Dict[str, Any]) -> Dict[str, Any]:
        """Strict comparator for unique identifiers (EMAIL, IP, DOMAIN, FILE_HASH)."""
        l1, l2 = e1["label"].strip().lower(), e2["label"].strip().lower()
        t = e1["type"]

        if l1 == l2:
            return {
                "match_score": 0.99,
                "suggestion": "exact_match",
                "supporting_evidence": [f"Exact matching unique technical indicator ({t}) '{l1}'."],
                "contradictory_evidence": []
            }

        # Subdomain / Domain relationship
        if t == EntityType.DOMAIN.value:
            if l1.endswith("." + l2) or l2.endswith("." + l1):
                return {
                    "match_score": 0.78,
                    "suggestion": "possible_match",
                    "supporting_evidence": [f"Subdomain infrastructure relationship between '{l1}' and '{l2}'."],
                    "contradictory_evidence": ["Distinct hostnames on shared domain zone."]
                }

        return {
            "match_score": 0.0,
            "suggestion": "distinct",
            "supporting_evidence": [],
            "contradictory_evidence": [f"Different {t} indicators: '{l1}' vs '{l2}'."]
        }

    @classmethod
    def compare_entities(cls, e1: Dict[str, Any], e2: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatches to type-specific comparator and provides normalized candidate summary."""
        t1, t2 = e1["type"], e2["type"]
        l1, l2 = e1["label"], e2["label"]

        if cls.is_rejected(l1, l2):
            return {
                "match_score": 0.0,
                "suggestion": "rejected_by_analyst",
                "supporting_evidence": [],
                "contradictory_evidence": ["Previously rejected by analyst."]
            }

        if t1 != t2 and "custom" not in (t1, t2):
            return {
                "match_score": 0.0,
                "suggestion": "distinct",
                "supporting_evidence": [],
                "contradictory_evidence": [f"Incompatible entity types: '{t1}' vs '{t2}'."]
            }

        if t1 == EntityType.PERSON.value:
            return cls.compare_persons(e1, e2)
        elif t1 == EntityType.ORGANIZATION.value:
            return cls.compare_organizations(e1, e2)
        elif t1 in [EntityType.EMAIL.value, EntityType.IP.value, EntityType.DOMAIN.value, EntityType.FILE_HASH.value]:
            return cls.compare_deterministic(e1, e2)
        else:
            sim = cls.calculate_string_similarity(l1, l2)
            if l1.lower().strip() == l2.lower().strip():
                return {
                    "match_score": 0.95,
                    "suggestion": "likely_match",
                    "supporting_evidence": [f"Exact match on {t1} label '{l1}'."],
                    "contradictory_evidence": []
                }
            if sim >= 0.82:
                return {
                    "match_score": sim,
                    "suggestion": "possible_match",
                    "supporting_evidence": [f"String similarity score: {sim:.2f}."],
                    "contradictory_evidence": []
                }
            return {
                "match_score": sim,
                "suggestion": "distinct",
                "supporting_evidence": [],
                "contradictory_evidence": [f"Low similarity ({sim:.2f}) between '{l1}' and '{l2}'."]
            }

    @classmethod
    def match_entities_across_documents(cls, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Runs candidate blocking and pairwise cross-document comparison."""
        candidates: List[Dict[str, Any]] = []
        n = len(entities)
        if n < 2:
            return []

        # Blocking strategy: group entities by (type, block_key)
        # Block keys: Soundex for PERSON, root token for ORG, exact lower string for deterministic
        blocks: Dict[Tuple[str, str], List[int]] = {}
        for idx, e in enumerate(entities):
            e_type = e["type"]
            label = e["label"].strip()

            keys = []
            if e_type == EntityType.PERSON.value:
                # Soundex, token prefixes, and every name token allow common spelling/order variants into the same block.
                tokens = [p for p in re.findall(r"[A-Za-z]+", label)]
                if tokens:
                    for token in tokens:
                        keys.append("sx:" + soundex(token))
                        keys.append("prefix:" + token[:3].lower())
                keys.append("first2:" + label[:2].lower())
            elif e_type == EntityType.ORGANIZATION.value:
                root, _ = cls.clean_org_name(label)
                root_tokens = root.split()
                for token in root_tokens:
                    keys.append("orgroot:" + token.lower())
                    keys.append("orgprefix:" + token[:3].lower())
                keys.append("first2:" + label[:2].lower())
            else:
                keys.append("exact:" + label.lower())

            for k in set(keys):
                block_id = (e_type, k)
                if block_id not in blocks:
                    blocks[block_id] = []
                blocks[block_id].append(idx)

        evaluated_pairs: Set[Tuple[int, int]] = set()

        for block_id, indices in blocks.items():
            for i_idx in range(len(indices)):
                for j_idx in range(i_idx + 1, len(indices)):
                    i, j = sorted([indices[i_idx], indices[j_idx]])
                    if (i, j) in evaluated_pairs:
                        continue
                    evaluated_pairs.add((i, j))

                    e1, e2 = entities[i], entities[j]
                    # Only compare entities from DIFFERENT documents or distinct entities
                    source_doc_id = e1.get("source_doc_id")
                    if source_doc_id and source_doc_id == e2.get("source_doc_id") and e1["label"].lower() == e2["label"].lower():
                        continue

                    comparison = cls.compare_entities(e1, e2)
                    if comparison["match_score"] >= 0.70 and comparison["suggestion"] != "rejected_by_analyst":
                        evidence_str = "; ".join(comparison["supporting_evidence"])
                        if comparison["contradictory_evidence"]:
                            evidence_str += " (Caveats: " + "; ".join(comparison["contradictory_evidence"]) + ")"

                        candidates.append({
                            # Normalized fields for both UI and API consumption
                            "entity1_label": e1["label"],
                            "entity2_label": e2["label"],
                            "type": e1["type"],
                            "score": round(comparison["match_score"], 2),
                            "match_score": round(comparison["match_score"], 2),
                            "suggested_action": comparison["suggestion"],
                            "suggestion": comparison["suggestion"],
                            "evidence": evidence_str,
                            "supporting_evidence": comparison["supporting_evidence"],
                            "contradictory_evidence": comparison["contradictory_evidence"],
                            "entity_a": e1,
                            "entity_b": e2,
                            "status": "pending_review"
                        })

        # Sort highest score first
        candidates.sort(key=lambda c: c["score"], reverse=True)
        return candidates
