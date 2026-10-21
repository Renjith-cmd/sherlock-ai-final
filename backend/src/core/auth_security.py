"""User authentication models, JWT session tokens, and Argon2id password security."""

import os
import re
import uuid
import time
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, EmailStr
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
import jwt

# Password hashing configuration
_ph = PasswordHasher(
    time_cost=3,
    memory_cost=65536,  # 64 MiB
    parallelism=4,
    hash_len=32,
    salt_len=16
)

# JWT Secret Configuration
JWT_SECRET = os.getenv("SHERLOCK_AI_JWT_SECRET", "sherlock-ai-dev-token-9f8e7d6c5b4a3120")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours


class User(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    username: str
    email: str
    full_name: Optional[str] = ""
    is_active: bool = True
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class UserInDB(User):
    password_hash: str


class AuthResponse(BaseModel):
    user: User
    token: str


def hash_password(password: str) -> str:
    """Hash password using Argon2id."""
    return _ph.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against Argon2id hash with timing attack resistance."""
    try:
        return _ph.verify(hashed_password, plain_password)
    except (VerifyMismatchError, Exception):
        return False


def create_access_token(user: User, expires_delta: Optional[timedelta] = None) -> str:
    """Generate signed JWT access token."""
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    payload = {
        "sub": user.id,
        "username": user.username,
        "email": user.email,
        "exp": expire,
        "iat": datetime.now(timezone.utc)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode and validate signed JWT access token."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except (jwt.PyJWTError, Exception):
        return None


# Rate limiter for login endpoint (in-memory per IP/user)
_login_attempts: Dict[str, list] = {}

def check_login_rate_limit(identifier: str, max_attempts: int = 5, window_seconds: int = 60) -> bool:
    """Return True if under rate limit, False if rate limited."""
    now = time.time()
    attempts = _login_attempts.get(identifier, [])
    # Keep only attempts within window
    attempts = [t for t in attempts if now - t < window_seconds]
    _login_attempts[identifier] = attempts

    if len(attempts) >= max_attempts:
        return False
    return True

def record_failed_attempt(identifier: str):
    attempts = _login_attempts.get(identifier, [])
    attempts.append(time.time())
    _login_attempts[identifier] = attempts

def clear_failed_attempts(identifier: str):
    if identifier in _login_attempts:
        del _login_attempts[identifier]


def normalize_email(email: str) -> str:
    """Normalize email address to lowercase and strip whitespace."""
    return email.strip().lower()


def validate_username(username: str) -> bool:
    """Username must be 3-30 chars, alphanumeric with underscore/hyphen."""
    return bool(re.match(r"^[a-zA-Z0-9_-]{3,30}$", username))
