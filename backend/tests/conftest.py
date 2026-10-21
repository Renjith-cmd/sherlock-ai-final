"""Pytest test configuration and fixtures for authenticated testing."""

import pytest
import uuid
from src.core.database import DatabaseRepository
from src.core.auth_security import User, hash_password, create_access_token


@pytest.fixture(scope="session")
def default_test_user():
    repo = DatabaseRepository()
    uid = uuid.uuid4().hex[:8]
    user = User(
        id=f"test-user-{uid}",
        username=f"tester_{uid}",
        email=f"tester_{uid}@agency.local",
        full_name="Automated Test Analyst"
    )
    repo.create_user(user, hash_password("ValidTestPassword123!"))
    return user


@pytest.fixture(scope="session")
def default_auth_token(default_test_user):
    return create_access_token(default_test_user)


@pytest.fixture(autouse=True)
def setup_legacy_test_clients(request, default_auth_token):
    """
    Sets default Authorization header on module-level `client` in the current test module
    unless it is test_user_isolation (which explicitly tests unauthenticated and multi-user behavior).
    """
    if "test_user_isolation" in request.module.__name__:
        return

    mod = request.module
    if hasattr(mod, "client"):
        mod.client.headers["Authorization"] = f"Bearer {default_auth_token}"
