"""Import, export, and investigative reporting generators (JSON, CSV, Markdown)."""

import csv
import io
import json
from typing import Dict, Any, List
from src.core.models import Investigation, Entity, Relationship


class ExportService:
    @staticmethod
    def export_graph_json(investigation: Investigation, entities: List[Entity], relationships: List[Relationship]) -> Dict[str, Any]:
        """Produce portable, validated JSON graph bundle."""
        return {
            "format_version": "1.0.0",
            "platform": "Sherlock AI",
            "investigation": investigation.model_dump(),
            "nodes": [e.model_dump() for e in entities],
            "edges": [r.model_dump() for r in relationships],
        }

    @staticmethod
    def export_entities_csv(entities: List[Entity]) -> str:
        """Export entities as CSV string."""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["id", "type", "label", "properties", "source", "confidence", "created_at"])
        for e in entities:
            writer.writerow([
                e.id,
                e.type.value if hasattr(e.type, "value") else str(e.type),
                e.label,
                json.dumps(e.properties),
                e.provenance.source,
                e.provenance.confidence,
                e.created_at
            ])
        return output.getvalue()

    @staticmethod
    def export_relationships_csv(relationships: List[Relationship]) -> str:
        """Export relationships as CSV string."""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["id", "source_id", "target_id", "type", "source", "created_at"])
        for r in relationships:
            writer.writerow([
                r.id,
                r.source_id,
                r.target_id,
                r.type,
                r.provenance.source,
                r.created_at
            ])
        return output.getvalue()

    @staticmethod
    def generate_investigation_report(investigation: Investigation, entities: List[Entity], relationships: List[Relationship]) -> str:
        """Generate structured forensic Markdown executive summary report."""
        lines = [
            f"# 🔍 Investigation Case Report: {investigation.title}",
            "",
            f"**Case ID**: `{investigation.id}`  ",
            f"**Generated**: `{investigation.updated_at}`  ",
            f"**Description**: {investigation.description or 'N/A'}  ",
            f"**Tags**: {', '.join(investigation.tags) if investigation.tags else 'None'}",
            "",
            "---",
            "",
            "## 1. Executive Summary & Graph Topology",
            f"- **Total Discovered Entities**: {len(entities)}",
            f"- **Total Identified Relationships**: {len(relationships)}",
            "",
            "### Breakdown by Entity Type",
        ]

        # Group count by type
        type_counts: Dict[str, int] = {}
        for e in entities:
            t = e.type.value if hasattr(e.type, "value") else str(e.type)
            type_counts[t] = type_counts.get(t, 0) + 1

        for t, cnt in sorted(type_counts.items()):
            lines.append(f"- **{t.title()}**: {cnt}")

        lines.extend([
            "",
            "## 2. Key Target Entities",
            "| Label | Type | Acquisition Method | Confidence | Observed |",
            "| :--- | :--- | :--- | :--- | :--- |"
        ])

        for e in entities[:25]:  # Top 25
            t = e.type.value if hasattr(e.type, "value") else str(e.type)
            lines.append(f"| `{e.label}` | {t} | {e.provenance.source} | {e.provenance.confidence:.2f} | {e.created_at[:19]} |")

        lines.extend([
            "",
            "## 3. Discovered Relationships & Pivot Links",
            "| Source Entity | Relationship | Target Entity | Source Provenance |",
            "| :--- | :--- | :--- | :--- |"
        ])

        ent_map = {e.id: e.label for e in entities}
        for r in relationships[:25]:
            src = ent_map.get(r.source_id, r.source_id[:8])
            tgt = ent_map.get(r.target_id, r.target_id[:8])
            lines.append(f"| `{src}` | **{r.type}** | `{tgt}` | {r.provenance.source} |")

        lines.extend([
            "",
            "---",
            "*Report compiled automatically by Sherlock AI Forensic Link Engine.*"
        ])

        return "\n".join(lines)
