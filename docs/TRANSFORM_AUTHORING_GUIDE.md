# Arkana Investigator: Extensibility & Transform Authoring Guide

## Overview
Arkana Investigator provides an asynchronous, modular transformation architecture designed for deterministic graph pivoting and evidence discovery.

---

## 1. Creating a Custom Transform

To create a new transform, inherit from `BaseTransform` and specify its metadata:

```python
from typing import List, Dict, Any
from src.core.models import Entity, EntityType, TransformResultCandidate
from src.core.transforms import BaseTransform, TransformMetadata, registry

class MyCustomLookupTransform(BaseTransform):
    metadata = TransformMetadata(
        id="custom_whois_lookup",
        name="Lookup Organization Info",
        description="Queries custom registry to find corporate ownership.",
        category="Corporate Intelligence",
        accepted_types=[EntityType.DOMAIN, EntityType.ORGANIZATION],
        output_types=[EntityType.PERSON, EntityType.LOCATION],
        requires_credentials=False,
        is_local=True
    )

    async def execute(self, entity: Entity, config: Dict[str, Any] = None) -> List[TransformResultCandidate]:
        # Perform asynchronous computation, API query, or local parsing
        results: List[TransformResultCandidate] = []
        
        # Example discovery
        results.append(
            TransformResultCandidate(
                entity_type=EntityType.PERSON,
                label="Jane Doe",
                properties={"role": "Director"},
                relationship_type="OFFICER_OF",
                confidence=0.9,
                evidence={"source": "Public Registry", "query": entity.label}
            )
        )
        return results

# Register into the global transform hub
registry.register(MyCustomLookupTransform())
```

---

## 2. Supported Entity Types
- `domain`: Web and network domain names.
- `ip`: IPv4 or IPv6 network addresses.
- `email`: Electronic mail addresses.
- `url`: Fully qualified resource locators.
- `person`: Individual identity names.
- `organization`: Companies, agencies, or groups.
- `document`: Uploaded files or textual notes.
- `file_hash`: MD5, SHA-1, SHA-256, or SHA-512 fingerprints.
- `phone`: Telephone numbers.
- `location`: Physical or geographic points.
- `custom`: Extensible custom indicator.

---

## 3. Provenance & Chain of Custody
Every transform result candidate must specify an `evidence` dictionary. When committed to the active graph, Arkana automatically pins immutable provenance records containing:
- Origin tool / API identifier.
- Timestamp in ISO 8601 UTC.
- Analyst or automated acquisition method.
- Numeric confidence value between 0.0 and 1.0.
