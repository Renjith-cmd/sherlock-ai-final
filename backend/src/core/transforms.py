"""Transformation registry and base transform interface."""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Type
from pydantic import BaseModel, Field
from src.core.models import Entity, EntityType, TransformResultCandidate


class TransformMetadata(BaseModel):
    id: str
    name: str
    description: str
    category: str = "General"
    accepted_types: List[EntityType]
    output_types: List[EntityType]
    requires_credentials: bool = False
    is_local: bool = True


class BaseTransform(ABC):
    metadata: TransformMetadata

    @abstractmethod
    async def execute(self, entity: Entity, config: Dict[str, Any] = None) -> List[TransformResultCandidate]:
        """Execute the transform and yield candidate results."""
        pass


class TransformRegistry:
    def __init__(self):
        self._transforms: Dict[str, BaseTransform] = {}

    def register(self, transform: BaseTransform):
        self._transforms[transform.metadata.id] = transform

    def get(self, transform_id: str) -> BaseTransform:
        return self._transforms.get(transform_id)

    def list_transforms(self) -> List[TransformMetadata]:
        return [t.metadata for t in self._transforms.values()]

    def get_compatible_transforms(self, entity_type: EntityType) -> List[TransformMetadata]:
        return [
            t.metadata for t in self._transforms.values()
            if entity_type in t.metadata.accepted_types
        ]


registry = TransformRegistry()
