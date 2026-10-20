"""FastAPI REST routes for investigations, entities, graphs, and transforms."""

from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any, Optional, Tuple
from pydantic import BaseModel
from src.core.models import Investigation, Entity, EntityType, Relationship, Provenance, TransformResultCandidate
from src.core.validation import normalize_and_validate_entity, ValidationError
from src.core.database import DatabaseRepository
from src.core.transforms import registry, TransformMetadata
from src.api.schemas import (
    CreateInvestigationRequest,
    CreateEntityRequest,
    CreateRelationshipRequest,
    ExecuteTransformRequest,
    MergeCandidatesRequest,
)

router = APIRouter()
repo = DatabaseRepository()


from src.core.security import get_system_diagnostics

@router.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "arkana-investigator",
        "transforms_loaded": len(registry.list_transforms())
    }


@router.get("/diagnostics")
def system_diagnostics():
    return get_system_diagnostics()



# --- Investigations ---

@router.post("/investigations", response_model=Investigation)
def create_investigation(req: CreateInvestigationRequest):
    inv = Investigation(title=req.title, description=req.description, tags=req.tags)
    return repo.create_investigation(inv)


@router.get("/investigations", response_model=List[Investigation])
def list_investigations():
    return repo.list_investigations()


@router.get("/investigations/{inv_id}", response_model=Investigation)
def get_investigation(inv_id: str):
    inv = repo.get_investigation(inv_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Investigation not found")
    return inv


@router.patch("/investigations/{inv_id}", response_model=Investigation)
def update_investigation(inv_id: str, payload: Dict[str, Any]):
    title = payload.get("title")
    description = payload.get("description")
    tags = payload.get("tags")
    inv = repo.update_investigation(inv_id, title=title, description=description, tags=tags)
    if not inv:
        raise HTTPException(status_code=404, detail="Investigation not found")
    return inv


@router.delete("/investigations/{inv_id}")
def delete_investigation(inv_id: str):
    success = repo.delete_investigation(inv_id)
    if not success:
        raise HTTPException(status_code=404, detail="Investigation not found")
    return {"status": "deleted", "id": inv_id}


class DuplicateRequest(BaseModel):
    title: Optional[str] = None


@router.post("/investigations/{inv_id}/duplicate", response_model=Investigation)
def duplicate_investigation(inv_id: str, payload: Optional[DuplicateRequest] = None):
    new_title = payload.title if payload else None
    new_inv = repo.duplicate_investigation(inv_id, new_title=new_title)
    if not new_inv:
        raise HTTPException(status_code=404, detail="Source investigation not found")
    return new_inv


from src.core.graph_analysis import GraphAnalyzer
from src.core.export_service import ExportService
from fastapi.responses import PlainTextResponse

# --- Graph & Entities ---

@router.get("/investigations/{inv_id}/graph")
def get_graph(inv_id: str):
    inv = repo.get_investigation(inv_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Investigation not found")
    entities = repo.get_entities_for_investigation(inv_id)
    relationships = repo.get_relationships_for_investigation(inv_id)
    return {
        "investigation": inv,
        "nodes": entities,
        "edges": relationships
    }


@router.get("/investigations/{inv_id}/export/json")
def export_investigation_json(inv_id: str):
    inv = repo.get_investigation(inv_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Investigation not found")
    entities = repo.get_entities_for_investigation(inv_id)
    relationships = repo.get_relationships_for_investigation(inv_id)
    return ExportService.export_graph_json(inv, entities, relationships)


@router.get("/investigations/{inv_id}/export/entities.csv", response_class=PlainTextResponse)
def export_investigation_entities_csv(inv_id: str):
    inv = repo.get_investigation(inv_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Investigation not found")
    entities = repo.get_entities_for_investigation(inv_id)
    csv_str = ExportService.export_entities_csv(entities)
    return PlainTextResponse(content=csv_str, media_type="text/csv")


@router.get("/investigations/{inv_id}/export/relationships.csv", response_class=PlainTextResponse)
def export_investigation_relationships_csv(inv_id: str):
    inv = repo.get_investigation(inv_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Investigation not found")
    relationships = repo.get_relationships_for_investigation(inv_id)
    csv_str = ExportService.export_relationships_csv(relationships)
    return PlainTextResponse(content=csv_str, media_type="text/csv")


@router.get("/investigations/{inv_id}/report", response_class=PlainTextResponse)
def get_investigation_report(inv_id: str):
    inv = repo.get_investigation(inv_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Investigation not found")
    entities = repo.get_entities_for_investigation(inv_id)
    relationships = repo.get_relationships_for_investigation(inv_id)
    report_md = ExportService.generate_investigation_report(inv, entities, relationships)
    return PlainTextResponse(content=report_md, media_type="text/markdown")


@router.get("/investigations/{inv_id}/analytics")
def get_graph_analytics(inv_id: str):
    inv = repo.get_investigation(inv_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Investigation not found")
    entities = repo.get_entities_for_investigation(inv_id)
    relationships = repo.get_relationships_for_investigation(inv_id)
    analyzer = GraphAnalyzer(entities, relationships)
    return analyzer.compute_metrics()


@router.get("/investigations/{inv_id}/path")
def find_shortest_path(inv_id: str, start_id: str, end_id: str):
    inv = repo.get_investigation(inv_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Investigation not found")
    entities = repo.get_entities_for_investigation(inv_id)
    relationships = repo.get_relationships_for_investigation(inv_id)
    analyzer = GraphAnalyzer(entities, relationships)
    path = analyzer.shortest_path(start_id, end_id)
    if path is None:
        raise HTTPException(status_code=404, detail="No path found between selected entities")
    return {"start_id": start_id, "end_id": end_id, "path": path, "length": len(path) - 1}


@router.get("/investigations/{inv_id}/search", response_model=List[Entity])
def search_entities(inv_id: str, q: Optional[str] = None, entity_type: Optional[str] = None, limit: int = 50):
    inv = repo.get_investigation(inv_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Investigation not found")
    all_entities = repo.get_entities_for_investigation(inv_id)
    results: List[Entity] = []

    query = (q or "").lower().strip()
    target_type = (entity_type or "").lower().strip()

    for ent in all_entities:
        # Filter by type if provided
        if target_type and target_type != "all" and ent.type.value.lower() != target_type:
            continue
        # Filter by query if provided (match label, properties, or provenance source)
        if query:
            label_match = query in ent.label.lower()
            prop_match = any(query in str(v).lower() for v in ent.properties.values())
            prov_match = query in ent.provenance.source.lower()
            if not (label_match or prop_match or prov_match):
                continue
        results.append(ent)
        if len(results) >= limit:
            break

    return results


@router.post("/investigations/{inv_id}/entities", response_model=Entity)
def add_entity(inv_id: str, req: CreateEntityRequest):
    inv = repo.get_investigation(inv_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Investigation not found")
    
    try:
        norm_label, norm_props = normalize_and_validate_entity(req.type, req.label, req.properties)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))

    provenance = req.provenance or Provenance(source="user_input", method="manual")
    entity = Entity(
        investigation_id=inv_id,
        type=req.type,
        label=norm_label,
        properties=norm_props,
        provenance=provenance
    )
    return repo.create_entity(entity)


class CreateEvidenceRequest(BaseModel):
    source_identifier: str
    source_url: Optional[str] = None
    content_hash: Optional[str] = None
    user_notes: Optional[str] = None


@router.post("/investigations/{inv_id}/entities/{entity_id}/evidence")
def add_entity_evidence(inv_id: str, entity_id: str, req: CreateEvidenceRequest):
    inv = repo.get_investigation(inv_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Investigation not found")
    ev = repo.create_evidence(
        inv_id=inv_id,
        entity_id=entity_id,
        source_identifier=req.source_identifier,
        source_url=req.source_url,
        content_hash=req.content_hash,
        user_notes=req.user_notes
    )
    repo.log_audit(inv_id, "ATTACH_EVIDENCE", {"entity_id": entity_id, "evidence_id": ev["id"]})
    return ev


@router.get("/entities/{entity_id}/evidence")
def list_entity_evidence(entity_id: str):
    return repo.get_evidence_for_entity(entity_id)


@router.get("/investigations/{inv_id}/audit-logs")
def get_audit_trail(inv_id: str):
    return repo.get_audit_logs(inv_id)


@router.patch("/entities/{entity_id}", response_model=Entity)
def update_entity_endpoint(entity_id: str, payload: Dict[str, Any]):
    label = payload.get("label")
    properties = payload.get("properties")
    ent = repo.update_entity(entity_id, label=label, properties=properties)
    if not ent:
        raise HTTPException(status_code=404, detail="Entity not found")
    return ent


@router.delete("/entities/{entity_id}")
def delete_entity_endpoint(entity_id: str):
    success = repo.delete_entity(entity_id)
    if not success:
        raise HTTPException(status_code=404, detail="Entity not found")
    return {"status": "deleted", "id": entity_id}


@router.delete("/relationships/{rel_id}")
def delete_relationship_endpoint(rel_id: str):
    success = repo.delete_relationship(rel_id)
    if not success:
        raise HTTPException(status_code=404, detail="Relationship not found")
    return {"status": "deleted", "id": rel_id}


@router.post("/investigations/{inv_id}/relationships", response_model=Relationship)
def add_relationship(inv_id: str, req: CreateRelationshipRequest):
    inv = repo.get_investigation(inv_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Investigation not found")
    provenance = Provenance(source="user_action", method="manual_link")
    rel = Relationship(
        investigation_id=inv_id,
        source_id=req.source_id,
        target_id=req.target_id,
        type=req.type,
        properties=req.properties,
        provenance=provenance
    )
    return repo.create_relationship(rel)


# --- Transformations ---

@router.get("/transforms", response_model=List[TransformMetadata])
def list_transforms():
    return registry.list_transforms()


@router.get("/transforms/compatible/{entity_type}", response_model=List[TransformMetadata])
def get_compatible_transforms(entity_type: str):
    return registry.get_compatible_transforms(entity_type)


@router.post("/investigations/{inv_id}/transforms/execute", response_model=List[TransformResultCandidate])
async def execute_transform(inv_id: str, req: ExecuteTransformRequest):
    entities = repo.get_entities_for_investigation(inv_id)
    entity = next((e for e in entities if e.id == req.entity_id), None)
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found in this investigation")
    transform = registry.get(req.transform_id)
    if not transform:
        raise HTTPException(status_code=404, detail=f"Transform '{req.transform_id}' not found")
    results = await transform.execute(entity, req.config)
    return results


@router.post("/investigations/{inv_id}/transforms/merge")
def merge_transform_results(inv_id: str, req: MergeCandidatesRequest):
    entities = repo.get_entities_for_investigation(inv_id)
    source_entity = next((e for e in entities if e.id == req.entity_id), None)
    if not source_entity:
        raise HTTPException(status_code=404, detail="Source entity not found")

    created_nodes: List[Entity] = []
    created_edges: List[Relationship] = []

    # Map existing labels by type to avoid duplicate nodes
    existing_map = {(e.type, e.label.lower()): e for e in entities}

    for cand in req.candidates:
        key = (cand.entity_type, cand.label.lower())
        target_node = existing_map.get(key)
        if not target_node:
            target_node = Entity(
                investigation_id=inv_id,
                type=cand.entity_type,
                label=cand.label,
                properties=cand.properties,
                provenance=Provenance(
                    source="transform_execution",
                    method="automated",
                    confidence=cand.confidence,
                    details=cand.evidence
                )
            )
            target_node = repo.create_entity(target_node)
            existing_map[key] = target_node
            created_nodes.append(target_node)

        # Create relationship
        rel = Relationship(
            investigation_id=inv_id,
            source_id=source_entity.id,
            target_id=target_node.id,
            type=cand.relationship_type,
            properties={},
            provenance=Provenance(
                source="transform_execution",
                method="automated",
                confidence=cand.confidence,
                details=cand.evidence
            )
        )
        created_edges.append(repo.create_relationship(rel))

    return {
        "created_nodes": created_nodes,
        "created_edges": created_edges
    }


# =========================================================================
# DOCUMENT INTELLIGENCE, ENTITY RESOLUTION & AUTO-GRAPH BUILDING
# =========================================================================

from fastapi import UploadFile, File
from src.core.document_extractor import DocumentExtractor
from src.core.document_intelligence import DocumentIntelligenceEngine
from src.core.entity_resolution import EntityResolutionEngine


@router.post("/investigations/{inv_id}/documents/upload")
async def upload_document(inv_id: str, file: UploadFile = File(...)):
    inv = repo.get_investigation(inv_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Investigation not found")

    content = await file.read()
    if len(content) > 25 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large. Maximum supported size is 25MB.")

    try:
        extracted_text, metadata = DocumentExtractor.extract_text(file.filename, content)
        doc = repo.create_document(
            inv_id=inv_id,
            filename=file.filename,
            extension=metadata["extension"],
            size_bytes=metadata["size_bytes"],
            sha256=metadata["sha256"],
            extracted_text=extracted_text,
            metadata=metadata,
            status="completed"
        )
        repo.log_audit(inv_id, "UPLOAD_DOCUMENT", {"document_id": doc["id"], "filename": file.filename})

        # Run extraction pipeline automatically
        intel = DocumentIntelligenceEngine.extract_all(extracted_text, doc["id"])

        # Compare against existing entities across all documents for cross-doc resolution
        existing_intel = repo.get_intelligence(inv_id)
        all_entities = existing_intel["entities"] + intel["entities"]
        cross_doc_matches = EntityResolutionEngine.match_entities_across_documents(all_entities)

        # Save intelligence records
        repo.save_intelligence(
            inv_id=inv_id,
            doc_id=doc["id"],
            entities=intel["entities"],
            relationships=intel["relationships"],
            matches=cross_doc_matches
        )

        return {
            "document": doc,
            "extracted_entities_count": len(intel["entities"]),
            "extracted_relationships_count": len(intel["relationships"]),
            "cross_document_matches_count": len(cross_doc_matches),
            "ocr_recommended": metadata.get("ocr_recommended", False)
        }
    except Exception as e:
        doc = repo.create_document(
            inv_id=inv_id,
            filename=file.filename,
            extension=os.path.splitext(file.filename)[1].lower() if file.filename else "",
            size_bytes=len(content),
            sha256=hashlib.sha256(content).hexdigest(),
            extracted_text="",
            metadata={},
            status="failed",
            error_message=str(e)
        )
        raise HTTPException(status_code=422, detail=f"Document parsing error: {str(e)}")


@router.get("/investigations/{inv_id}/documents")
def list_investigation_documents(inv_id: str):
    inv = repo.get_investigation(inv_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Investigation not found")
    return repo.list_documents(inv_id)


@router.get("/documents/{doc_id}")
def get_document_details(doc_id: str):
    doc = repo.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.delete("/documents/{doc_id}")
def delete_document_endpoint(doc_id: str):
    success = repo.delete_document(doc_id)
    if not success:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"status": "deleted", "id": doc_id}


@router.get("/investigations/{inv_id}/intelligence")
def get_investigation_intelligence(inv_id: str):
    inv = repo.get_investigation(inv_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Investigation not found")
    return repo.get_intelligence(inv_id)


class BuildGraphFromIntelRequest(BaseModel):
    selected_entities: List[Dict[str, Any]]
    selected_relationships: List[Dict[str, Any]]
    include_document_node: bool = True
    document_id: Optional[str] = None


@router.post("/investigations/{inv_id}/intelligence/build-graph")
def build_graph_from_intelligence(inv_id: str, req: BuildGraphFromIntelRequest):
    inv = repo.get_investigation(inv_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Investigation not found")

    existing_entities = repo.get_entities_for_investigation(inv_id)
    node_map: Dict[Tuple[str, str], Entity] = {(e.type.value if hasattr(e.type, 'value') else str(e.type), e.label.lower()): e for e in existing_entities}
    created_nodes: List[Entity] = []
    created_edges: List[Relationship] = []

    # Optional Document Node
    doc_node: Optional[Entity] = None
    if req.include_document_node and req.document_id:
        doc = repo.get_document(req.document_id)
        if doc:
            key = ("document", doc["filename"].lower())
            if key in node_map:
                doc_node = node_map[key]
            else:
                doc_node = Entity(
                    investigation_id=inv_id,
                    type=EntityType.DOCUMENT,
                    label=doc["filename"],
                    properties={"sha256": doc["sha256"], "size_bytes": doc["size_bytes"]},
                    provenance=Provenance(source=f"upload:{doc['filename']}", method="file_upload", confidence=1.0)
                )
                doc_node = repo.create_entity(doc_node)
                node_map[key] = doc_node
                created_nodes.append(doc_node)

    # 1. Add Accepted Entities
    for item in req.selected_entities:
        ent_type_str = item["type"]
        label = item["label"]
        key = (ent_type_str, label.lower())

        if key in node_map:
            target_node = node_map[key]
        else:
            try:
                norm_label, norm_props = normalize_and_validate_entity(EntityType(ent_type_str), label, {})
            except Exception:
                norm_label, norm_props = label, {}

            target_node = Entity(
                investigation_id=inv_id,
                type=EntityType(ent_type_str),
                label=norm_label,
                properties=norm_props,
                provenance=Provenance(
                    source="document_intelligence",
                    method=item.get("method", "nlp_regex"),
                    confidence=float(item.get("confidence", 0.9)),
                    details={"mentions": item.get("mentions", [])}
                )
            )
            target_node = repo.create_entity(target_node)
            node_map[key] = target_node
            created_nodes.append(target_node)

        # Connect entity to document if doc node exists
        if doc_node and target_node.id != doc_node.id:
            rel = Relationship(
                investigation_id=inv_id,
                source_id=doc_node.id,
                target_id=target_node.id,
                type="MENTIONS",
                properties={},
                provenance=Provenance(source="document_extraction", method="direct", confidence=1.0)
            )
            created_edges.append(repo.create_relationship(rel))

    # 2. Add Accepted Relationships
    for r_item in req.selected_relationships:
        src_key = (r_item["source_type"], r_item["source_label"].lower())
        tgt_key = (r_item["target_type"], r_item["target_label"].lower())

        src_node = node_map.get(src_key)
        tgt_node = node_map.get(tgt_key)

        if src_node and tgt_node and src_node.id != tgt_node.id:
            rel = Relationship(
                investigation_id=inv_id,
                source_id=src_node.id,
                target_id=tgt_node.id,
                type=r_item["type"],
                properties={"evidence": r_item.get("evidence_excerpt", "")},
                provenance=Provenance(
                    source="document_intelligence",
                    method="co_occurrence_extraction",
                    confidence=float(r_item.get("confidence", 0.85)),
                    details={"evidence_excerpt": r_item.get("evidence_excerpt", "")}
                )
            )
            created_edges.append(repo.create_relationship(rel))

    repo.log_audit(inv_id, "BUILD_GRAPH_FROM_DOCUMENTS", {"nodes_added": len(created_nodes), "edges_added": len(created_edges)})

    return {
        "status": "success",
        "nodes_added": len(created_nodes),
        "edges_added": len(created_edges),
        "total_nodes": len(node_map)
    }

