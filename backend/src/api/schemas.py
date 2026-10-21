"""Pydantic schemas for API request and response validation."""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from src.core.models import EntityType, Provenance, TransformResultCandidate


class CreateInvestigationRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = ""
    tags: List[str] = Field(default_factory=list)


class CreateEntityRequest(BaseModel):
    type: EntityType
    label: str = Field(..., min_length=1)
    properties: Dict[str, Any] = Field(default_factory=dict)
    provenance: Optional[Provenance] = None


class CreateRelationshipRequest(BaseModel):
    source_id: str
    target_id: str
    type: str = "ASSOCIATED_WITH"
    properties: Dict[str, Any] = Field(default_factory=dict)
    provenance: Optional[Provenance] = None


class ExecuteTransformRequest(BaseModel):
    transform_id: str
    entity_id: str
    config: Dict[str, Any] = Field(default_factory=dict)


class MergeCandidatesRequest(BaseModel):
    entity_id: str
    candidates: List[TransformResultCandidate]
