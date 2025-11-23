import secrets
from datetime import datetime, timedelta
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, status, Header
from pydantic import BaseModel
import db


router = APIRouter(
    prefix="/auth",
    tags=["auth"],
)


# ============ SCHEMAS ============

class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    user_id: int
    username: str
    role: str


class VerifyResponse(BaseModel):
    user_id: int
    username: str
    role: str


# ============ ENDPOINTS ============


@router.post("/login", response_model=LoginResponse)
async def login_endpoint(request: LoginRequest):
    try:
        result = _login(request.username, request.password)
        return LoginResponse(**result)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )


@router.get("/verify", response_model=VerifyResponse)
async def verify_endpoint(authorization: str = Header(None)):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing or invalid Authorization header")
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")
    try:
        result = _verify_token(token)
        return VerifyResponse(**result)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )


# ============ LOGIC ============

def _generate_token() -> str:
    return secrets.token_urlsafe(64)


def _login(username: str, password: str) -> Dict[str, Any]:
    # Query user by username
    result = db.fetch_all(
        """
        SELECT u.id, u.password_hash, u.is_active, r.name as role
        FROM Users u
        LEFT JOIN Roles r ON u.role_id = r.id
        WHERE u.username = ?
        """,
        params=[username]
    )
    
    if not result:
        raise ValueError("Invalid username or password")
    
    user_id, password_hash, is_active, role = result[0]
    
    if not is_active:
        raise ValueError("User account is inactive")
    
    # Verify password
    if password != password_hash:
        raise ValueError("Invalid username or password")
    
    # Generate session token
    token = _generate_token()
    expires_at = datetime.utcnow() + timedelta(hours=24)
    
    # Store session in database
    db.execute(
        """
        INSERT INTO Sessions (id, user_id, session_token, expires_at)
        VALUES (nextval('seq_session_id'), ?, ?, ?)
        """,
        params=[user_id, token, expires_at]
    )
    
    # Update last_login timestamp
    db.execute(
        "UPDATE Users SET last_login = now() WHERE id = ?",
        params=[user_id]
    )
    
    return {
        "token": token,
        "user_id": user_id,
        "username": username,
        "role": role or "user"
    }


def _verify_token(token: str) -> Dict[str, Any]:
    result = db.fetch_all(
        """
        SELECT s.user_id, u.username, r.name as role, s.expires_at
        FROM Sessions s
        JOIN Users u ON s.user_id = u.id
        LEFT JOIN Roles r ON u.role_id = r.id
        WHERE s.session_token = ?
        """,
        params=[token]
    )
    
    if not result:
        raise ValueError("Invalid or expired token")
    
    user_id, username, role, expires_at = result[0]
    
    # Check expiration
    if expires_at and datetime.fromisoformat(str(expires_at)) < datetime.utcnow():
        raise ValueError("Token expired")
    
    return {
        "user_id": user_id,
        "username": username,
        "role": role or "user"
    }
