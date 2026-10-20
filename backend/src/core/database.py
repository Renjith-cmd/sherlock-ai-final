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
                created_at TEXT NOT NULL,
                FOREIGN KEY (investigation_id) REFERENCES investigations(id) ON DELETE CASCADE,
                FOREIGN KEY (source_id) REFERENCES entities(id) ON DELETE CASCADE,
                FOREIGN KEY (target_id) REFERENCES entities(id) ON DELETE CASCADE
            );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_entities_inv ON entities(investigation_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_rel_inv ON relationships(investigation_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_rel_source ON relationships(source_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_rel_target ON relationships(target_id);")
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
