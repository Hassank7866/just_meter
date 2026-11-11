"""JWT authentication and demo role seeding for the prototype API."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import HTTPException, Request


JWT_SECRET = os.environ.get("AUTH_JWT_SECRET", "").strip()
if not JWT_SECRET:
    raise RuntimeError("AUTH_JWT_SECRET must be set before starting the backend")
if len(JWT_SECRET.encode("utf-8")) < 32:
    raise RuntimeError("AUTH_JWT_SECRET must contain at least 32 bytes")

JWT_ALGORITHM = "HS256"
TOKEN_LIFETIME = timedelta(hours=8)
CAMERA_TOKEN_LIFETIME = timedelta(minutes=20)


_DUMMY_PASSWORD_HASH = bcrypt.hashpw(b"not-a-real-demo-password", bcrypt.gensalt()).decode("ascii")

ALL_ROLES = {"Administrator", "Transport Officer", "Supervisory Officer", "Auditor"}
OFFICER_ROLES = {"Administrator", "Transport Officer", "Supervisory Officer"}


def authenticate(email: str, password: str, engine=None) -> dict[str, str] | None:
    from sqlalchemy import select
    from sqlalchemy.orm import Session
    from .database import get_engine
    from .db_models import User
    with Session(engine if engine is not None else get_engine()) as session:
        user = session.scalar(select(User).where(User.email == email.strip().lower(), User.active.is_(True)))
        account = {"email": user.email, "name": user.name, "role": user.role,
                   "department_id": user.department_id, "token_version": user.token_version,
                   "password_hash": user.password_hash} if user else None
    password_bytes = password.encode("utf-8")[:72]
    if len(password.encode("utf-8")) > 72:
        bcrypt.checkpw(_DUMMY_PASSWORD_HASH.encode("ascii"), _DUMMY_PASSWORD_HASH.encode("ascii"))
        return None
    if account is None:
        # Perform a bcrypt check for unknown users too, reducing obvious timing differences.
        bcrypt.checkpw(password_bytes, _DUMMY_PASSWORD_HASH.encode("ascii"))
        return None
    try:
        valid = bcrypt.checkpw(password_bytes, account["password_hash"].encode("ascii"))
    except (ValueError, TypeError):
        return None
    return account if valid else None


def create_access_token(account: dict[str, str]) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": account["email"],
        "name": account["name"],
        "role": account["role"],
        "token_version": account.get("token_version", 0),
        "iat": now,
        "exp": now + TOKEN_LIFETIME,
        "iss": "just-meter",
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def create_camera_token(principal: dict[str, str]) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": principal["sub"],
        "name": principal.get("name", ""),
        "role": principal["role"],
        "scope": "camera_upload",
        "token_version": principal.get("token_version", 0),
        "iat": now,
        "exp": now + CAMERA_TOKEN_LIFETIME,
        "iss": "just-meter",
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def create_live_feed_token(principal: dict[str, str]) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": principal["sub"],
        "name": principal.get("name", ""),
        "role": principal["role"],
        "scope": "live_feed",
        "token_version": principal.get("token_version", 0),
        "iat": now,
        "exp": now + CAMERA_TOKEN_LIFETIME,
        "iss": "just-meter",
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str, engine=None) -> dict:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM], issuer="just-meter")
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired access token") from exc
    role = payload.get("role")
    subject = payload.get("sub")
    if role not in ALL_ROLES or not isinstance(subject, str):
        raise HTTPException(status_code=401, detail="Invalid access token")
    from sqlalchemy import select
    from sqlalchemy.orm import Session
    from .database import get_engine
    from .db_models import User
    with Session(engine if engine is not None else get_engine()) as session:
        user = session.scalar(select(User).where(User.email == subject, User.active.is_(True)))
        if user is None or payload.get("token_version", 0) != user.token_version or role != user.role:
            raise HTTPException(401, "Session revoked; sign in again")
        payload.update(name=user.name, role=user.role, department_id=user.department_id,
                       token_version=user.token_version, user_id=user.id)
    return payload


def token_from_request(request: Request) -> str | None:
    authorization = request.headers.get("Authorization", "")
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    # Browser image and download tags cannot set Authorization headers.
    return request.query_params.get("token")


def require_principal(request: Request) -> dict[str, str]:
    principal = getattr(request.state, "principal", None)
    if principal is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return principal


def require_roles(*roles: str):
    allowed = set(roles)

    def dependency(request: Request) -> dict[str, str]:
        principal = require_principal(request)
        if principal["role"] not in allowed:
            raise HTTPException(status_code=403, detail="Your role is not allowed to perform this action")
        return principal

    return dependency
