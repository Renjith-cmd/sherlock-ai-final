"""SQLite Database management and schema migrations."""

import sqlite3
import json
from pathlib import Path
from typing import Optional, List, Dict, Any
from src.core.models import Investigation, Entity, Relationship, EntityType, Provenance

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "investigator.db"


def get_connection(db_file: Optional[Path] = None) -> sqlite3.Connection:
    target = db_file or DB_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(target))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn


def init_db(db_file: Optional[Path] = None):
    conn = get_connection(db_file)
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS investigations (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT,
                tags TEXT NOT NULL DEFAULT '[]',
                is_archived INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS entities (
                id TEXT PRIMARY KEY,
                investigation_id TEXT NOT NULL,
                type TEXT NOT NULL,
                label TEXT NOT NULL,
                properties TEXT NOT NULL DEFAULT '{}',
                provenance TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (investigation_id) REFERENCES investigations(id) ON DELETE CASCADE
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS relationships (
                id TEXT PRIMARY KEY,
                investigation_id TEXT NOT NULL,
                source_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                type TEXT NOT NULL DEFAULT 'ASSOCIATED_WITH',
                properties TEXT NOT NULL DEFAULT '{}',
                provenance TEXT NOT NULL DEFAULT '{}',
                FOREIGN KEY (investigation_id) REFERENCES investigations(id) ON DELETE CASCADE,
                FOREIGN KEY (source_id) REFERENCES entities(id) ON DELETE CASCADE,
                FOREIGN KEY (target_id) REFERENCES entities(id) ON DELETE CASCADE
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS evidence (
                id TEXT PRIMARY KEY,
                investigation_id TEXT NOT NULL,
                entity_id TEXT,
                relationship_id TEXT,
                source_url TEXT,
                source_identifier TEXT NOT NULL,
                content_hash TEXT,
                user_notes TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (investigation_id) REFERENCES investigations(id) ON DELETE CASCADE,
                FOREIGN KEY (entity_id) REFERENCES entities(id) ON DELETE CASCADE,
                FOREIGN KEY (relationship_id) REFERENCES relationships(id) ON DELETE CASCADE
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id TEXT PRIMARY KEY,
                investigation_id TEXT NOT NULL,
                action TEXT NOT NULL,
                details TEXT NOT NULL DEFAULT '{}',
                timestamp TEXT NOT NULL,
                FOREIGN KEY (investigation_id) REFERENCES investigations(id) ON DELETE CASCADE
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                investigation_id TEXT NOT NULL,
                filename TEXT NOT NULL,
                extension TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                sha256 TEXT NOT NULL,
                extracted_text TEXT NOT NULL DEFAULT '',
                metadata TEXT NOT NULL DEFAULT '{}',
                processing_status TEXT NOT NULL DEFAULT 'uploaded',
                error_message TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (investigation_id) REFERENCES investigations(id) ON DELETE CASCADE
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS extracted_intelligence (
                id TEXT PRIMARY KEY,
                investigation_id TEXT NOT NULL,
                document_id TEXT NOT NULL,
                extracted_entities TEXT NOT NULL DEFAULT '[]',
                extracted_relationships TEXT NOT NULL DEFAULT '[]',
                cross_document_matches TEXT NOT NULL DEFAULT '[]',
                status TEXT NOT NULL DEFAULT 'completed',
                updated_at TEXT NOT NULL,
                FOREIGN KEY (investigation_id) REFERENCES investigations(id) ON DELETE CASCADE,
                FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
            );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_entities_inv ON entities(investigation_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_rel_inv ON relationships(investigation_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_rel_source ON relationships(source_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_rel_target ON relationships(target_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_evidence_inv ON evidence(investigation_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_evidence_ent ON evidence(entity_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_inv ON audit_logs(investigation_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_docs_inv ON documents(investigation_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_intel_inv ON extracted_intelligence(investigation_id);")
    conn.close()


class DatabaseRepository:
    def __init__(self, db_file: Optional[Path] = None):
        self.db_file = db_file
        init_db(self.db_file)

    def create_investigation(self, inv: Investigation) -> Investigation:
        conn = get_connection(self.db_file)
        with conn:
            conn.execute(
                "INSERT INTO investigations (id, title, description, tags, is_archived, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (inv.id, inv.title, inv.description, json.dumps(inv.tags), int(inv.is_archived), inv.created_at, inv.updated_at)
            )
        conn.close()
        return inv

    def list_investigations(self) -> List[Investigation]:
        conn = get_connection(self.db_file)
        cur = conn.execute("SELECT * FROM investigations WHERE is_archived = 0 ORDER BY updated_at DESC")
        rows = cur.fetchall()
        conn.close()
        return [
            Investigation(
                id=r["id"],
                title=r["title"],
                description=r["description"],
                tags=json.loads(r["tags"]),
                is_archived=bool(r["is_archived"]),
                created_at=r["created_at"],
                updated_at=r["updated_at"]
            )
            for r in rows
        ]

    def get_investigation(self, inv_id: str) -> Optional[Investigation]:
        conn = get_connection(self.db_file)
        cur = conn.execute("SELECT * FROM investigations WHERE id = ?", (inv_id,))
        r = cur.fetchone()
        conn.close()
        if not r:
            return None
        return Investigation(
            id=r["id"],
            title=r["title"],
            description=r["description"],
            tags=json.loads(r["tags"]),
            is_archived=bool(r["is_archived"]),
            created_at=r["created_at"],
            updated_at=r["updated_at"]
        )

    def update_investigation(self, inv_id: str, title: Optional[str] = None, description: Optional[str] = None, tags: Optional[List[str]] = None) -> Optional[Investigation]:
        conn = get_connection(self.db_file)
        with conn:
            cur = conn.execute("SELECT * FROM investigations WHERE id = ?", (inv_id,))
            row = cur.fetchone()
            if not row:
                conn.close()
                return None
            new_title = title if title is not None else row["title"]
            new_desc = description if description is not None else row["description"]
            new_tags = tags if tags is not None else json.loads(row["tags"])
            from datetime import datetime, timezone
            updated_at = datetime.now(timezone.utc).isoformat()
            conn.execute(
                "UPDATE investigations SET title = ?, description = ?, tags = ?, updated_at = ? WHERE id = ?",
                (new_title, new_desc, json.dumps(new_tags), updated_at, inv_id)
            )
            cur = conn.execute("SELECT * FROM investigations WHERE id = ?", (inv_id,))
            r = cur.fetchone()
        conn.close()
        return Investigation(
            id=r["id"],
            title=r["title"],
            description=r["description"],
            tags=json.loads(r["tags"]),
            is_archived=bool(r["is_archived"]),
            created_at=r["created_at"],
            updated_at=r["updated_at"]
        )

    def delete_investigation(self, inv_id: str) -> bool:
        conn = get_connection(self.db_file)
        with conn:
            cur = conn.execute("DELETE FROM investigations WHERE id = ?", (inv_id,))
            deleted = cur.rowcount > 0
        conn.close()
        return deleted

    def duplicate_investigation(self, inv_id: str, new_title: Optional[str] = None) -> Optional[Investigation]:
        source = self.get_investigation(inv_id)
        if not source:
            return None
        import uuid
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        new_inv_id = str(uuid.uuid4())
        title = new_title or f"{source.title} (Copy)"
        new_inv = Investigation(
            id=new_inv_id,
            title=title,
            description=source.description,
            tags=source.tags,
            created_at=now,
            updated_at=now
        )
        self.create_investigation(new_inv)

        # Clone all entities & map old IDs to new IDs
        old_entities = self.get_entities_for_investigation(inv_id)
        id_map: Dict[str, str] = {}
        for ent in old_entities:
            new_ent_id = str(uuid.uuid4())
            id_map[ent.id] = new_ent_id
            cloned_ent = Entity(
                id=new_ent_id,
                investigation_id=new_inv_id,
                type=ent.type,
                label=ent.label,
                properties=ent.properties,
                provenance=ent.provenance,
                created_at=now,
                updated_at=now
            )
            self.create_entity(cloned_ent)

        # Clone all relationships
        old_rels = self.get_relationships_for_investigation(inv_id)
        for rel in old_rels:
            if rel.source_id in id_map and rel.target_id in id_map:
                cloned_rel = Relationship(
                    id=str(uuid.uuid4()),
                    investigation_id=new_inv_id,
                    source_id=id_map[rel.source_id],
                    target_id=id_map[rel.target_id],
                    type=rel.type,
                    properties=rel.properties,
                    provenance=rel.provenance,
                    created_at=now
                )
                self.create_relationship(cloned_rel)

        return new_inv

    def create_entity(self, entity: Entity) -> Entity:
        conn = get_connection(self.db_file)
        with conn:
            conn.execute(
                "INSERT INTO entities (id, investigation_id, type, label, properties, provenance, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    entity.id,
                    entity.investigation_id,
                    entity.type.value if hasattr(entity.type, "value") else str(entity.type),
                    entity.label,
                    json.dumps(entity.properties),
                    json.dumps(entity.provenance.model_dump()),
                    entity.created_at,
                    entity.updated_at,
                )
            )
            conn.execute("UPDATE investigations SET updated_at = ? WHERE id = ?", (entity.updated_at, entity.investigation_id))
        conn.close()
        return entity

    def get_entities_for_investigation(self, inv_id: str) -> List[Entity]:
        conn = get_connection(self.db_file)
        cur = conn.execute("SELECT * FROM entities WHERE investigation_id = ?", (inv_id,))
        rows = cur.fetchall()
        conn.close()
        return [
            Entity(
                id=r["id"],
                investigation_id=r["investigation_id"],
                type=EntityType(r["type"]),
                label=r["label"],
                properties=json.loads(r["properties"]),
                provenance=Provenance(**json.loads(r["provenance"])),
                created_at=r["created_at"],
                updated_at=r["updated_at"]
            )
            for r in rows
        ]

    def create_relationship(self, rel: Relationship) -> Relationship:
        conn = get_connection(self.db_file)
        with conn:
            conn.execute(
                "INSERT INTO relationships (id, investigation_id, source_id, target_id, type, properties, provenance, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    rel.id,
                    rel.investigation_id,
                    rel.source_id,
                    rel.target_id,
                    rel.type,
                    json.dumps(rel.properties),
                    json.dumps(rel.provenance.model_dump()),
                    rel.created_at
                )
            )
        conn.close()
        return rel

    def get_relationships_for_investigation(self, inv_id: str) -> List[Relationship]:
        conn = get_connection(self.db_file)
        cur = conn.execute("SELECT * FROM relationships WHERE investigation_id = ?", (inv_id,))
        rows = cur.fetchall()
        conn.close()
        return [
            Relationship(
                id=r["id"],
                investigation_id=r["investigation_id"],
                source_id=r["source_id"],
                target_id=r["target_id"],
                type=r["type"],
                properties=json.loads(r["properties"]),
                provenance=Provenance(**json.loads(r["provenance"])),
                created_at=r["created_at"]
            )
            for r in rows
        ]

    def update_entity(self, entity_id: str, label: Optional[str] = None, properties: Optional[Dict[str, Any]] = None) -> Optional[Entity]:
        conn = get_connection(self.db_file)
        with conn:
            cur = conn.execute("SELECT * FROM entities WHERE id = ?", (entity_id,))
            row = cur.fetchone()
            if not row:
                conn.close()
                return None
            new_label = label if label is not None else row["label"]
            existing_props = json.loads(row["properties"])
            if properties is not None:
                existing_props.update(properties)
            from datetime import datetime, timezone
            updated_at = datetime.now(timezone.utc).isoformat()
            conn.execute(
                "UPDATE entities SET label = ?, properties = ?, updated_at = ? WHERE id = ?",
                (new_label, json.dumps(existing_props), updated_at, entity_id)
            )
            cur = conn.execute("SELECT * FROM entities WHERE id = ?", (entity_id,))
            r = cur.fetchone()
        conn.close()
        return Entity(
            id=r["id"],
            investigation_id=r["investigation_id"],
            type=EntityType(r["type"]),
            label=r["label"],
            properties=json.loads(r["properties"]),
            provenance=Provenance(**json.loads(r["provenance"])),
            created_at=r["created_at"],
            updated_at=r["updated_at"]
        )

    def delete_entity(self, entity_id: str) -> bool:
        conn = get_connection(self.db_file)
        with conn:
            cur = conn.execute("DELETE FROM entities WHERE id = ?", (entity_id,))
            deleted = cur.rowcount > 0
        conn.close()
        return deleted

    def delete_relationship(self, rel_id: str) -> bool:
        conn = get_connection(self.db_file)
        with conn:
            cur = conn.execute("DELETE FROM relationships WHERE id = ?", (rel_id,))
            deleted = cur.rowcount > 0
        conn.close()
        return deleted

    def create_evidence(self, inv_id: str, source_identifier: str, entity_id: Optional[str] = None,
                        relationship_id: Optional[str] = None, source_url: Optional[str] = None,
                        content_hash: Optional[str] = None, user_notes: Optional[str] = None) -> Dict[str, Any]:
        import uuid
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        ev_id = str(uuid.uuid4())
        conn = get_connection(self.db_file)
        with conn:
            conn.execute(
                "INSERT INTO evidence (id, investigation_id, entity_id, relationship_id, source_url, source_identifier, content_hash, user_notes, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (ev_id, inv_id, entity_id, relationship_id, source_url, source_identifier, content_hash, user_notes, now)
            )
        conn.close()
        return {
            "id": ev_id,
            "investigation_id": inv_id,
            "entity_id": entity_id,
            "relationship_id": relationship_id,
            "source_url": source_url,
            "source_identifier": source_identifier,
            "content_hash": content_hash,
            "user_notes": user_notes,
            "created_at": now
        }

    def get_evidence_for_entity(self, entity_id: str) -> List[Dict[str, Any]]:
        conn = get_connection(self.db_file)
        cur = conn.execute("SELECT * FROM evidence WHERE entity_id = ? ORDER BY created_at DESC", (entity_id,))
        rows = cur.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def log_audit(self, inv_id: str, action: str, details: Dict[str, Any]) -> None:
        import uuid
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        conn = get_connection(self.db_file)
        with conn:
            conn.execute(
                "INSERT INTO audit_logs (id, investigation_id, action, details, timestamp) VALUES (?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), inv_id, action, json.dumps(details), now)
            )
        conn.close()

    def get_audit_logs(self, inv_id: str) -> List[Dict[str, Any]]:
        conn = get_connection(self.db_file)
        cur = conn.execute("SELECT * FROM audit_logs WHERE investigation_id = ? ORDER BY timestamp DESC", (inv_id,))
        rows = cur.fetchall()
        conn.close()
        return [{"id": r["id"], "investigation_id": r["investigation_id"], "action": r["action"], "details": json.loads(r["details"]), "timestamp": r["timestamp"]} for r in rows]

    # --- Document & Intelligence Operations ---

    def create_document(self, inv_id: str, filename: str, extension: str, size_bytes: int,
                        sha256: str, extracted_text: str = "", metadata: Dict[str, Any] = None,
                        status: str = "completed", error_message: str = None) -> Dict[str, Any]:
        import uuid
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        doc_id = str(uuid.uuid4())
        meta_json = json.dumps(metadata or {})
        conn = get_connection(self.db_file)
        with conn:
            conn.execute(
                "INSERT INTO documents (id, investigation_id, filename, extension, size_bytes, sha256, extracted_text, metadata, processing_status, error_message, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (doc_id, inv_id, filename, extension, size_bytes, sha256, extracted_text, meta_json, status, error_message, now)
            )
        conn.close()
        return {
            "id": doc_id,
            "investigation_id": inv_id,
            "filename": filename,
            "extension": extension,
            "size_bytes": size_bytes,
            "sha256": sha256,
            "extracted_text": extracted_text,
            "metadata": metadata or {},
            "processing_status": status,
            "error_message": error_message,
            "created_at": now
        }

    def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        conn = get_connection(self.db_file)
        cur = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,))
        r = cur.fetchone()
        conn.close()
        if not r:
            return None
        d = dict(r)
        d["metadata"] = json.loads(d["metadata"])
        return d

    def list_documents(self, inv_id: str) -> List[Dict[str, Any]]:
        conn = get_connection(self.db_file)
        cur = conn.execute("SELECT id, investigation_id, filename, extension, size_bytes, sha256, metadata, processing_status, error_message, created_at FROM documents WHERE investigation_id = ? ORDER BY created_at DESC", (inv_id,))
        rows = cur.fetchall()
        conn.close()
        res = []
        for r in rows:
            d = dict(r)
            d["metadata"] = json.loads(d["metadata"])
            res.append(d)
        return res

    def delete_document(self, doc_id: str) -> bool:
        conn = get_connection(self.db_file)
        with conn:
            cur = conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
            deleted = cur.rowcount > 0
        conn.close()
        return deleted

    def save_intelligence(self, inv_id: str, doc_id: str, entities: List[Dict[str, Any]],
                          relationships: List[Dict[str, Any]], matches: List[Dict[str, Any]]) -> Dict[str, Any]:
        import uuid
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        intel_id = str(uuid.uuid4())
        conn = get_connection(self.db_file)
        with conn:
            conn.execute(
                "INSERT INTO extracted_intelligence (id, investigation_id, document_id, extracted_entities, extracted_relationships, cross_document_matches, status, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (intel_id, inv_id, doc_id, json.dumps(entities), json.dumps(relationships), json.dumps(matches), "completed", now)
            )
        conn.close()
        return {
            "id": intel_id,
            "investigation_id": inv_id,
            "document_id": doc_id,
            "extracted_entities": entities,
            "extracted_relationships": relationships,
            "cross_document_matches": matches,
            "updated_at": now
        }

    def get_intelligence(self, inv_id: str) -> Dict[str, Any]:
        conn = get_connection(self.db_file)
        cur = conn.execute("SELECT * FROM extracted_intelligence WHERE investigation_id = ? ORDER BY updated_at DESC", (inv_id,))
        rows = cur.fetchall()
        conn.close()
        all_entities: List[Dict[str, Any]] = []
        all_relationships: List[Dict[str, Any]] = []
        all_matches: List[Dict[str, Any]] = []

        for r in rows:
            ents = json.loads(r["extracted_entities"])
            rels = json.loads(r["extracted_relationships"])
            mats = json.loads(r["cross_document_matches"])
            all_entities.extend(ents)
            all_relationships.extend(rels)
            all_matches.extend(mats)

        return {
            "entities": all_entities,
            "relationships": all_relationships,
            "matches": all_matches
        }

