# System Architecture: Sherlock AI Platform

## 1. Architectural Principles
1. **Clean-Room Design**: No dependencies, code, or data structures copied from prior projects.
2. **Separation of Concerns**: Strict decoupling between presentation, REST APIs, service orchestration, transformation workers, and storage adapters.
3. **Graph-First Presentation**: The primary view is an interactive, low-latency node-and-link canvas backed by a structured relational/graph model.
4. **Verifiable Provenance**: Every entity and relationship carries an immutable provenance record with source identification, method, timestamp, and confidence.
5. **Fail-Safe & Idempotent Transforms**: All transform execution is bounded by timeouts, validated by schemas, and deduplicated before committing to graph memory.

---

## 2. System Architecture Diagram

```
+-----------------------------------------------------------------------------------+
|                             Sherlock AI Frontend (React + TS)                     |
|  +--------------------+  +--------------------------------+  +-----------------+  |
|  | Investigation Nav  |  |   Cytoscape Graph Canvas       |  | Inspector Panel |  |
|  | - Case Explorer    |  |   - Pan / Zoom / Drag          |  | - Properties    |  |
|  | - Entity Palette   |  |   - Contextual Transforms Menu |  | - Provenance    |  |
|  | - Transform Hub    |  |   - Layout Engine (Cose/Grid)  |  | - Raw Evidence  |  |
|  +--------------------+  +--------------------------------+  +-----------------+  |
|  +-----------------------------------------------------------------------------+  |
|  | Bottom Panel: Transform Results Preview | Activity Log | Search & Filters   |  |
|  +-----------------------------------------------------------------------------+  |
+-----------------------------------------------------------------------------------+
                                         | HTTP / JSON REST
                                         v
+-----------------------------------------------------------------------------------+
|                             FastAPI Backend Service                               |
|  +-----------------------------------------------------------------------------+  |
|  | Routers: /investigations | /entities | /relationships | /transforms | /health|  |
|  +-----------------------------------------------------------------------------+  |
|  +--------------------------- Service Layer -----------------------------------+  |
|  |  [InvestigationService]   [GraphService]   [TransformEngine]   [ExportSvc]   |  |
|  +-----------------------------------------------------------------------------+  |
|  +----------------------- Transformation Registry -----------------------------+  |
|  |  DNS Lookup | Reverse DNS | RDAP Whois | IP Geolocation | URL Extractor     |  |
|  |  File Hasher | Email Syntax Check | CSV Extractor | Text Entity Finder     |  |
|  +-----------------------------------------------------------------------------+  |
|  +----------------------- Data Access Layer (Repository) -----------------------+  |
|  |  SQLite3 WAL Store (schema-migrated, ACID transactions, relational index)   |  |
|  +-----------------------------------------------------------------------------+  |
+-----------------------------------------------------------------------------------+
```

---

## 3. Data Model & Schema Design

### Entities Table (`entities`)
- `id`: TEXT PRIMARY KEY (UUIDv4)
- `investigation_id`: TEXT NOT NULL (FK -> `investigations.id` ON DELETE CASCADE)
- `type`: TEXT NOT NULL (e.g. `domain`, `ip`, `person`, `organization`, `email`, `hash`)
- `label`: TEXT NOT NULL
- `properties`: TEXT NOT NULL (JSON-serialized key-value map)
- `provenance`: TEXT NOT NULL (JSON-serialized provenance object)
- `created_at`: TEXT NOT NULL (ISO 8601 UTC)
- `updated_at`: TEXT NOT NULL (ISO 8601 UTC)

### Relationships Table (`relationships`)
- `id`: TEXT PRIMARY KEY (UUIDv4)
- `investigation_id`: TEXT NOT NULL (FK -> `investigations.id` ON DELETE CASCADE)
- `source_id`: TEXT NOT NULL (FK -> `entities.id` ON DELETE CASCADE)
- `target_id`: TEXT NOT NULL (FK -> `entities.id` ON DELETE CASCADE)
- `type`: TEXT NOT NULL (e.g. `RESOLVES_TO`, `OWNS`, `OPERATES`, `ASSOCIATED_WITH`)
- `properties`: TEXT NOT NULL (JSON map)
- `provenance`: TEXT NOT NULL (JSON map)
- `created_at`: TEXT NOT NULL

### Investigations Table (`investigations`)
- `id`: TEXT PRIMARY KEY (UUIDv4)
- `title`: TEXT NOT NULL
- `description`: TEXT
- `tags`: TEXT (JSON array)
- `is_archived`: INTEGER NOT NULL DEFAULT 0
- `created_at`: TEXT NOT NULL
- `updated_at`: TEXT NOT NULL
