"""FastAPI REST routes for investigations, entities, graphs, and transforms."""

from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from src.core.models import Investigation, Entity, Relationship, Provenance, TransformResultCandidate
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


@router.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "arkana-investigator",
        "transforms_loaded": len(registry.list_transforms())
    }


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
