# Implementation Plan: Graph-First Investigation Workbench (Arkana Investigator)

## Executive Summary
This document outlines the systematic, clean-room implementation of an independent graph-first link analysis and OSINT investigation platform. Designed with clean architectural separation, robust provenance modeling, real transformation pipelines, and native interactive graph manipulation.

---

## 1. Project Identity & Architecture
- **Application Name**: Arkana Investigator (or Maltego-Inspired Open Link Analysis Workbench)
- **Directory**: `/home/renjith-cmd/Documents/maltego-inspired-investigator`
- **Repository**: Isolated Git repository with no upstream remotes.
- **Frontend Stack**: React 18/19, TypeScript, Vite, Cytoscape.js (or @xyflow/react / D3-force), Lucide icons, Vanilla CSS tokens.
- **Backend Stack**: Python 3.14, FastAPI, Pydantic v2, Uvicorn, SQLite3 WAL mode.
- **Storage Model**: Relational metadata + graph entity/relationship records with foreign-key constraints and transactional atomicity.

---

## 2. Phase-by-Phase Roadmap & Acceptance Criteria

### Phase 1 — Application Foundation
- **Goal**: Functional backend API, SQLite database with schema migrations, health checks, environment configuration, frontend build tooling, and automated smoke test.
- **Complexity**: Moderate
- **Dependencies**: `fastapi`, `uvicorn`, `pydantic`, `pytest`, `httpx`, `vite`, `react`, `typescript`
- **Status**: IN PROGRESS
- **Acceptance Criteria**: Backend serves `/api/health` with DB connection status; frontend loads cleanly; tests pass.

### Phase 2 — Interactive Graph Workbench
- **Goal**: Full-featured graph canvas supporting pan, zoom, drag, multi-selection, node creation, edge creation, context menus, layout algorithms (cose, breadthfirst, circle, grid), fit-to-view, undo/redo state stack.
- **Complexity**: High
- **Dependencies**: Cytoscape.js or @xyflow/react
- **Status**: PENDING
- **Acceptance Criteria**: Canvas renders typed nodes with icons/badges; users can drag, connect, delete, and inspect nodes in real time.

### Phase 3 — Investigation and Case Management
- **Goal**: Create, list, open, rename, duplicate, archive, and delete investigations. Automatic snapshotting and graph persistence in SQLite.
- **Complexity**: Moderate
- **Dependencies**: SQLite relational tables (`investigations`, `graph_snapshots`)
- **Status**: PENDING
- **Acceptance Criteria**: Graph nodes/edges automatically save and restore accurately when switching between investigations.

### Phase 4 — Entity System
- **Goal**: Extensible typed entity registry (Person, Organization, Domain, IP, URL, Email, Phone, Document, File Hash, etc.) with schema validation, normalization, and confidence metrics.
- **Complexity**: Moderate
- **Dependencies**: Pydantic models, SQLite `entities` and `relationships` tables
- **Status**: PENDING
- **Acceptance Criteria**: Entities have unique IDs, typed properties, timestamps, and verifiable provenance tracking.

### Phase 5 — Real Transformation Engine
- **Goal**: Modular transformation framework with registry, input/output validation, execution progress, result preview, selective graph merge, and cancellation.
- **Complexity**: High
- **Dependencies**: Custom TransformRegistry and async execution workers
- **Status**: PENDING
- **Acceptance Criteria**: User selects an entity -> sees compatible transforms -> executes -> previews returned candidate entities -> selectively merges into active graph.

### Phase 6 — Legitimate Data-Source Integrations
- **Goal**: Concrete working transforms using standard network tools, legitimate public APIs, and local parsers (DNS resolution, RDAP/WHOIS, URL extraction, file hashing, CSV/JSON ingest).
- **Complexity**: Moderate
- **Dependencies**: `dnspython`, `urllib`, standard library cryptography
- **Status**: PENDING
- **Acceptance Criteria**: Real DNS/IP/Hash lookups yield factual, verifiable output records with exact timestamps.

### Phase 7 — Graph Analysis & Investigation Tools
- **Goal**: Shortest path detection, degree/centrality analysis, neighbor expansion, node filtering by type/confidence, cluster detection, and isolated node pruning.
- **Complexity**: Moderate
- **Dependencies**: Graph algorithmic routines
- **Status**: PENDING
- **Acceptance Criteria**: Analysts can query paths between two nodes, calculate node degrees, and highlight connected subgraphs.

### Phase 8 — Evidence and Provenance
- **Goal**: Explicit provenance records attached to every node and edge (source URL, retrieval timestamp, user notes, raw response hash, extraction confidence).
- **Complexity**: Moderate
- **Status**: PENDING
- **Acceptance Criteria**: Inspector panel shows exact origin of every graph element, distinguishing user inputs from automated lookups.

### Phase 9 — Search, Filter & Inspection
- **Goal**: Global search across investigation entities, type filter pills, property filters, regex matching, and graph auto-focus.
- **Complexity**: Moderate
- **Status**: PENDING
- **Acceptance Criteria**: Typing in search highlights matching nodes in the canvas and filters the tabular inspector.

### Phase 10 — Import, Export & Reporting
- **Goal**: Export graph to JSON, CSV (nodes and edges), GraphML; import JSON/CSV; generate structured investigation summary reports.
- **Complexity**: Moderate
- **Status**: PENDING
- **Acceptance Criteria**: Exported JSON can be re-imported losslessly; reports include timestamped executive summaries and entity lists.

### Phase 11 — Security & Configuration
- **Goal**: Local authorization layer, path traversal prevention for file imports, input sanitization, safe environment variable loading.
- **Complexity**: Moderate
- **Status**: PENDING
- **Acceptance Criteria**: Security tests verify path validation, injection protection, and safe secret handling.

### Phase 12 — Extensibility & Administration
- **Goal**: Transform registry inspector, connector status overview, diagnostics endpoint, and developer documentation for custom transform authoring.
- **Complexity**: Low
- **Status**: PENDING
- **Acceptance Criteria**: Built-in developer guide and diagnostics report system health and registered transform counts.

### Phase 13 — Testing & Quality Assurance
- **Goal**: Automated backend tests (Pytest), frontend tests, integration tests for transforms, and end-to-end verification.
- **Complexity**: Moderate
- **Status**: PENDING
- **Acceptance Criteria**: Complete suite runs cleanly in CI/local environment.
