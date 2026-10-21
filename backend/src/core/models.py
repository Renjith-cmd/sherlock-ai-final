"""Core domain models for Sherlock AI."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
import uuid


class EntityType(str, Enum):
    PERSON = "person"
    ORGANIZATION = "organization"
    DOMAIN = "domain"
    IP = "ip"
    URL = "url"
    EMAIL = "email"
    PHONE = "phone"
    DOCUMENT = "document"
    FILE_HASH = "file_hash"
    LOCATION = "location"
    CUSTOM = "custom"


class Provenance(BaseModel):
    source: str = Field(..., description="Source name or tool, e.g., 'manual_input', 'dns_resolver', 'rdap_whois'")
    method: str = Field("direct", description="Method of acquisition: 'direct', 'inferred', 'user_provided'")
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    confidence: float = Field(1.0, ge=0.0, le=1.0, description="Confidence score from 0.0 to 1.0")
    details: Dict[str, Any] = Field(default_factory=dict, description="Raw evidence, query parameters, or cryptographic hash")


class Entity(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    investigation_id: str
    type: EntityType
    label: str
    properties: Dict[str, Any] = Field(default_factory=dict)
    provenance: Provenance
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class Relationship(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    investigation_id: str
    source_id: str
    target_id: str
    type: str = Field("ASSOCIATED_WITH", description="Typed semantic relationship")
    properties: Dict[str, Any] = Field(default_factory=dict)
    provenance: Provenance
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class Investigation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: Optional[str] = None
    title: str
    description: Optional[str] = ""
    tags: List[str] = Field(default_factory=list)
    is_archived: bool = False
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class TransformResultCandidate(BaseModel):
    entity_type: EntityType
    label: str
    properties: Dict[str, Any] = Field(default_factory=dict)
    relationship_type: str = "CONNECTED_TO"
    confidence: float = 1.0
    evidence: Dict[str, Any] = Field(default_factory=dict)
