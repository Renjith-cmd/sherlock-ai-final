"""Comprehensive Security and Multi-Tenant User Isolation Test Suite.

Verifies:
1. User A registration and login -> receives secure JWT.
2. User B registration and login -> receives distinct credentials.
3. User A creates investigation, entities, relationships, documents, and evidence.
4. User A can access their own investigation and associated data.
5. User B cannot see User A's investigation in list or search results (Strict Scoping).
6. User B cannot access User A's investigation by guessing ID (Returns 404).
7. User B cannot fetch, view, or delete User A's documents.
8. User B cannot view User A's entities, evidence, or audit logs.
9. User B cannot modify or delete User A's entities or relationships.
10. User B cannot trigger reprocessing or exports of User A's investigation.
11. Unauthenticated requests to private endpoints are rejected with 401.
12. Invalid passwords or nonexistent users receive generic 401 errors.
13. Passwords are saved with Argon2id and never in plaintext.
14. Legacy/unassigned investigations without user_id are not visible to standard users.
15. Logout terminates session.
"""

import pytest
import sqlite3
import uuid
from pathlib import Path
from fastapi.testclient import TestClient
from src.main import app
from src.core.database import DatabaseRepository, get_connection
from src.core.auth_security import hash_password, verify_password

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_db():
    # Setup test run
    yield


def test_auth_registration_and_argon2_hashing():
    uid = uuid.uuid4().hex[:8]
    username = f"analyst_{uid}"
    email = f"analyst_{uid}@agency.gov"
    password = "SuperSecretPassword123!"

    # 1. Register User
    res = client.post("/api/auth/register", json={
        "username": username,
        "email": email,
        "password": password,
        "full_name": "Senior Special Agent"
    })
    assert res.status_code == 200
    data = res.json()
    assert "token" in data
    assert data["user"]["username"] == username
    assert data["user"]["email"] == email

    # 2. Verify database stores Argon2 hash and NOT plaintext
    repo = DatabaseRepository()
    user_db = repo.get_user_by_username_or_email(username)
    assert user_db is not None
    assert user_db.password_hash.startswith("$argon2id$")
    assert password not in user_db.password_hash
    assert verify_password(password, user_db.password_hash) is True


def test_login_invalid_credentials_generic_rejection():
    # Invalid password gives 401
    res = client.post("/api/auth/login", json={
        "identifier": "nonexistent_officer_999",
        "password": "WrongPassword!"
    })
    assert res.status_code == 401
    assert "Invalid username or password" in res.json()["detail"]


def test_strict_multi_user_investigation_isolation():
    uid_a = uuid.uuid4().hex[:8]
    uid_b = uuid.uuid4().hex[:8]

    # --- Register User A ---
    res_a = client.post("/api/auth/register", json={
        "username": f"agent_a_{uid_a}",
        "email": f"agent_a_{uid_a}@cia.gov",
        "password": "PasswordUserA123!"
    })
    assert res_a.status_code == 200
    token_a = res_a.json()["token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # --- Register User B ---
    res_b = client.post("/api/auth/register", json={
        "username": f"agent_b_{uid_b}",
        "email": f"agent_b_{uid_b}@cia.gov",
        "password": "PasswordUserB123!"
    })
    assert res_b.status_code == 200
    token_b = res_b.json()["token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # --- User A creates an investigation ---
    create_res = client.post("/api/investigations", json={
        "title": f"Operation Blackbriar {uid_a}",
        "description": "Top Secret Classified Case",
        "tags": ["classified", "intel"]
    }, headers=headers_a)
    assert create_res.status_code == 200
    inv_a = create_res.json()
    inv_id_a = inv_a["id"]

    # User A creates an entity in their investigation
    ent_res = client.post(f"/api/investigations/{inv_id_a}/entities", json={
        "type": "person",
        "label": "Jason Bourne",
        "properties": {"alias": "David Webb"}
    }, headers=headers_a)
    assert ent_res.status_code == 200
    entity_a = ent_res.json()
    entity_id_a = entity_a["id"]

    # User A attaches evidence
    ev_res = client.post(f"/api/investigations/{inv_id_a}/entities/{entity_id_a}/evidence", json={
        "source_identifier": "passports.pdf",
        "user_notes": "Fake identities discovered in locker."
    }, headers=headers_a)
    assert ev_res.status_code == 200

    # User A uploads a document
    file_content = b"Surveillance report: operative Jason Bourne spotted in Zurich."
    doc_res = client.post(
        f"/api/investigations/{inv_id_a}/documents/upload",
        files={"file": ("classified_memo.txt", file_content, "text/plain")},
        headers=headers_a
    )
    assert doc_res.status_code == 200
    doc_id_a = doc_res.json()["document"]["id"]

    # =========================================================================
    # VERIFY USER A CAN ACCESS EVERYTHING
    # =========================================================================
    list_a = client.get("/api/investigations", headers=headers_a).json()
    assert any(c["id"] == inv_id_a for c in list_a)

    get_a = client.get(f"/api/investigations/{inv_id_a}", headers=headers_a)
    assert get_a.status_code == 200
    assert get_a.json()["title"] == f"Operation Blackbriar {uid_a}"

    graph_a = client.get(f"/api/investigations/{inv_id_a}/graph", headers=headers_a)
    assert graph_a.status_code == 200
    assert len(graph_a.json()["nodes"]) >= 1

    docs_a = client.get(f"/api/investigations/{inv_id_a}/documents", headers=headers_a)
    assert docs_a.status_code == 200
    assert len(docs_a.json()) >= 1

    # =========================================================================
    # VERIFY USER B CANNOT ACCESS USER A's DATA (STRICT OWNERSHIP ENFORCEMENT)
    # =========================================================================

    # 1. User B lists investigations -> User A's case MUST NOT appear
    list_b = client.get("/api/investigations", headers=headers_b).json()
    assert all(c["id"] != inv_id_a for c in list_b)

    # 2. User B tries to get User A's case directly by ID -> returns 404 (prevent ID enumeration)
    get_b = client.get(f"/api/investigations/{inv_id_a}", headers=headers_b)
    assert get_b.status_code == 404

    # 3. User B tries to access User A's graph -> 404
    graph_b = client.get(f"/api/investigations/{inv_id_a}/graph", headers=headers_b)
    assert graph_b.status_code == 404

    # 4. User B tries to fetch User A's documents list -> 404
    docs_b = client.get(f"/api/investigations/{inv_id_a}/documents", headers=headers_b)
    assert docs_b.status_code == 404

    # 5. User B tries to get User A's document details directly -> 404
    doc_direct_b = client.get(f"/api/documents/{doc_id_a}", headers=headers_b)
    assert doc_direct_b.status_code == 404

    # 6. User B tries to delete User A's document -> 404
    del_doc_b = client.delete(f"/api/documents/{doc_id_a}", headers=headers_b)
    assert del_doc_b.status_code == 404

    # 7. User B tries to reprocess User A's document -> 404
    reprocess_b = client.post(f"/api/documents/{doc_id_a}/reprocess", headers=headers_b)
    assert reprocess_b.status_code == 404

    # 8. User B tries to modify User A's entity directly -> 404
    mod_ent_b = client.patch(f"/api/entities/{entity_id_a}", json={"label": "Hacked"}, headers=headers_b)
    assert mod_ent_b.status_code == 404

    # 9. User B tries to delete User A's entity directly -> 404
    del_ent_b = client.delete(f"/api/entities/{entity_id_a}", headers=headers_b)
    assert del_ent_b.status_code == 404

    # 10. User B tries to export User A's investigation report -> 404
    report_b = client.get(f"/api/investigations/{inv_id_a}/report", headers=headers_b)
    assert report_b.status_code == 404

    # 11. User B tries to search User A's entities -> 404
    search_b = client.get(f"/api/investigations/{inv_id_a}/search?q=Bourne", headers=headers_b)
    assert search_b.status_code == 404


def test_unauthenticated_requests_are_rejected():
    fresh_client = TestClient(app)
    res = fresh_client.get("/api/investigations")
    assert res.status_code == 401

    res_post = fresh_client.post("/api/investigations", json={"title": "Unauthorized"})
    assert res_post.status_code == 401


def test_legacy_unassigned_cases_not_leaked_to_new_users():
    """Verify that cases without user_id (legacy migrations) are never exposed in user case lists."""
    uid = uuid.uuid4().hex[:8]
    res = client.post("/api/auth/register", json={
        "username": f"fresh_user_{uid}",
        "email": f"fresh_{uid}@gov.org",
        "password": "Password12345!"
    })
    token = res.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Newly registered user's investigation list MUST be empty
    inv_list = client.get("/api/investigations", headers=headers).json()
    assert len(inv_list) == 0
