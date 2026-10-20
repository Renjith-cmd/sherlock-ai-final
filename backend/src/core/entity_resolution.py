"""Cross-document entity matching and resolution engine."""

from typing import List, Dict, Any, Tuple
from difflib import SequenceMatcher
from src.core.models import EntityType


class EntityResolutionEngine:
    @staticmethod
    def calculate_string_similarity(a: str, b: str) -> float:
        """Normalized Gestalt pattern matching ratio between two strings (0.0 to 1.0)."""
        return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()

    @classmethod
    def compare_entities(cls, e1: Dict[str, Any], e2: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compare two extracted entities across documents.
        Returns match evaluation with documented rationale.
        """
        t1, t2 = e1["type"], e2["type"]
        l1, l2 = e1["label"], e2["label"]

        # Different types are incompatible unless one is generic or custom
        if t1 != t2 and "custom" not in (t1, t2):
            return {
                "match_score": 0.0,
                "suggestion": "distinct",
                "supporting_evidence": [],
                "contradictory_evidence": [f"Conflicting entity types: '{t1}' vs '{t2}'"]
            }

        # 1. Exact canonical match
        if l1.lower().strip() == l2.lower().strip():
            # For people, same name is strong signal but could be different people -> suggest review
            if t1 == EntityType.PERSON.value:
                return {
                    "match_score": 0.88,
                    "suggestion": "likely_match",
                    "supporting_evidence": [f"Identical full name '{l1}' across documents."],
                    "contradictory_evidence": ["Name collision possible without verified DOB/Gov ID."]
                }
            # For deterministic identifiers (Email, IP, Domain, Hash), exact match is virtually certain
            elif t1 in [EntityType.EMAIL.value, EntityType.IP.value, EntityType.DOMAIN.value, EntityType.FILE_HASH.value]:
                return {
                    "match_score": 0.99,
                    "suggestion": "exact_match",
                    "supporting_evidence": [f"Exact matching unique identifier '{l1}'."],
                    "contradictory_evidence": []
                }
            else:
                return {
                    "match_score": 0.92,
                    "suggestion": "likely_match",
                    "supporting_evidence": [f"Exact match on {t1} label '{l1}'."],
                    "contradictory_evidence": []
                }

        # 2. Fuzzy Token / Substring matching
        sim = cls.calculate_string_similarity(l1, l2)

        # Organization prefix/suffix alias matching (e.g. "Acme Corp" vs "Acme")
        if t1 == EntityType.ORGANIZATION.value:
            words1 = set(l1.lower().split())
            words2 = set(l2.lower().split())
            overlap = words1.intersection(words2)
            if len(overlap) >= 1 and (l1.lower().startswith(l2.lower()) or l2.lower().startswith(l1.lower())):
                return {
                    "match_score": max(sim, 0.82),
                    "suggestion": "possible_match",
                    "supporting_evidence": [f"Shared organizational root token: {overlap}."],
                    "contradictory_evidence": [f"Different corporate legal designation: '{l1}' vs '{l2}'"]
                }

        # People name token similarity (e.g. "Johnathan Smith" vs "John Smith")
        if t1 == EntityType.PERSON.value and sim >= 0.78:
            return {
                "match_score": sim,
                "suggestion": "possible_match",
                "supporting_evidence": [f"High lexical similarity ({sim:.2f}) between person names."],
                "contradictory_evidence": ["Requires analyst review to confirm identity."]
            }

        if sim >= 0.85:
            return {
                "match_score": sim,
                "suggestion": "possible_match",
                "supporting_evidence": [f"High string similarity score: {sim:.2f}."],
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
        """
        Runs pairwise cross-document comparison and generates a reviewable matching queue.
        """
        candidates: List[Dict[str, Any]] = []
        n = len(entities)

        for i in range(n):
            for j in range(i + 1, n):
                e1 = entities[i]
                e2 = entities[j]

                # Only match entities from DIFFERENT documents or distinct entries
                if e1.get("source_doc_id") == e2.get("source_doc_id") and e1["label"] == e2["label"]:
                    continue

                comparison = cls.compare_entities(e1, e2)
                if comparison["match_score"] >= 0.75:
                    candidates.append({
                        "entity_a": e1,
                        "entity_b": e2,
                        "match_score": round(comparison["match_score"], 2),
                        "suggestion": comparison["suggestion"],
                        "supporting_evidence": comparison["supporting_evidence"],
                        "contradictory_evidence": comparison["contradictory_evidence"],
                        "status": "pending_review"
                    })

        # Sort highest confidence first
        candidates.sort(key=lambda c: c["match_score"], reverse=True)
        return candidates
