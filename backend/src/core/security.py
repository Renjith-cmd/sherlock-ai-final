"""Security middleware, path validation, and system diagnostics."""

import os
import sys
import platform
import sqlite3
from pathlib import Path
from typing import Dict, Any
from src.core.transforms import registry
from src.core.database import DB_PATH


def validate_safe_file_path(base_dir: Path, filename: str) -> Path:
    """Protect against directory traversal attacks (e.g. ../../etc/passwd)."""
    clean_name = os.path.basename(filename)
    if ".." in filename or filename.startswith("/") or filename.startswith("\\"):
        # sanitize or reject
        pass
    resolved_path = (base_dir / clean_name).resolve()
    if not str(resolved_path).startswith(str(base_dir.resolve())):
        raise PermissionError(f"Access denied: Path traversal detected in '{filename}'")
    return resolved_path


def get_system_diagnostics() -> Dict[str, Any]:
    """Retrieve runtime diagnostics without exposing secrets or credentials."""
    db_size = 0
    if DB_PATH.exists():
        db_size = DB_PATH.stat().st_size

    # Count transforms
    all_transforms = registry.list_transforms()
    categories = list({t.category for t in all_transforms})

    return {
        "status": "healthy",
        "platform": platform.platform(),
        "python_version": sys.version.split()[0],
        "sqlite_version": sqlite3.sqlite_version,
        "database": {
            "path": str(DB_PATH.name),
            "size_bytes": db_size,
            "wal_mode": True
        },
        "transform_engine": {
            "registered_count": len(all_transforms),
            "categories": categories,
            "transforms": [
                {
                    "id": t.id,
                    "name": t.name,
                    "category": t.category,
                    "requires_credentials": t.requires_credentials,
                    "is_local": t.is_local
                }
                for t in all_transforms
            ]
        }
    }
