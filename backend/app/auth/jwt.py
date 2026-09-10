from datetime import datetime, timedelta
from jose import jwt, JWTError
from app.core.config import settings
from typing import Optional, Any

def create_access_token(user_id: str, role: str, tenant_id: Optional[str] = None, expires_delta: Optional[timedelta] = None) -> str:
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode = {
        "sub": str(user_id),
        "user_id": str(user_id),
        "role": role,
        "tenant_id": str(tenant_id) if tenant_id else None,
        "exp": expire
    }
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])

def create_invite_token(email: str, tenant_id: str, invite_token: str) -> str:
    expire = datetime.utcnow() + timedelta(hours=48)
    to_encode = {
        "sub": email,
        "tenant_id": str(tenant_id),
        "invite_token": invite_token,
        "exp": expire,
        "type": "invite"
    }
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def decode_invite_token(token: str) -> dict[str, Any]:
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    if payload.get("type") != "invite":
        raise JWTError("Invalid token type")
    return payload
