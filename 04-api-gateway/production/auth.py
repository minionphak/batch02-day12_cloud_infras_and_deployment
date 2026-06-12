"""
JWT Authentication Module

JWT (JSON Web Token) = stateless auth.
Token chứa: user_id, role, expiry → không cần check DB mỗi request.

Flow:
    POST /auth/token  → trả về JWT
    GET  /ask         → gửi JWT trong header Authorization: Bearer <token>
    Server verify signature → extract user info → process request
"""
import os
import jwt
import time
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# ─────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────
SECRET_KEY = os.getenv("JWT_SECRET", "super-secret-change-in-production-please")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

# Demo users (trong thực tế lưu trong database)
DEMO_USERS = {
    "student": {"password": "demo123", "role": "user", "daily_limit": 50},
    "teacher": {"password": "teach456", "role": "admin", "daily_limit": 1000},
}

security = HTTPBearer(auto_error=False)


def create_token(username: str, role: str) -> str:
    """Tạo JWT token với expiry."""
    payload = {
        "sub": username,           # subject (user identifier)
        "role": role,
        "iat": datetime.now(timezone.utc),  # issued at
        "exp": datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)) -> dict:
    """
    Dependency: verify JWT token từ Authorization header.
    Raise HTTPException nếu token invalid hoặc expired.
    """
    if not credentials:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Include: Authorization: Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        return {
            "username": payload["sub"],
            "role": payload["role"],
        }
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired. Please login again.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=403, detail="Invalid token.")


def authenticate_user(username: str, password: str) -> dict:
    """Kiểm tra username/password, trả về user info nếu hợp lệ."""
    user = DEMO_USERS.get(username)
    if not user or user["password"] != password:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"username": username, "role": user["role"]}
