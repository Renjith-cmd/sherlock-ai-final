"""Tests for Phase 11 & 12 Security path traversal validation and system diagnostics."""

import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from src.main import app
from src.core.security import validate_safe_file_path

client = TestClient(app)


def test_path_traversal_protection():
    base = Path("/home/renjith-cmd/Documents/maltego-inspired-investigator/data")
    
    # 1. Safe file path resolves cleanly
    safe_file = validate_safe_file_path(base, "report.pdf")
    assert safe_file.name == "report.pdf"
    assert safe_file.parent.resolve() == base.resolve()

    # 2. Directory traversal attempt is sanitized to basename
    escaped_file = validate_safe_file_path(base, "../../../etc/passwd")
    assert escaped_file.name == "passwd"
    assert escaped_file.parent.resolve() == base.resolve()


def test_system_diagnostics_endpoint():
    res = client.get("/api/diagnostics")
    assert res.status_code == 200
    diag = res.json()
    assert diag["status"] == "healthy"
    assert "platform" in diag
    assert "python_version" in diag
    assert "sqlite_version" in diag
    assert diag["database"]["wal_mode"] is True
    assert diag["transform_engine"]["registered_count"] >= 8
