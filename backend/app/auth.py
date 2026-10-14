"""Argon2 passwords and expiring, algorithm-pinned Bearer JWT authentication."""

from datetime import timedelta
from typing import Annotated

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import Profile, User, utcnow
from app.schemas import AuthInput

router = APIRouter(prefix="/auth", tags=["Authentication"])
passwords = PasswordHash.recommended()
bearer = HTTPBearer(auto_error=False)


def public_user(user: User) -> dict:
    return {"id": user.id, "email": user.email, "created_at": user.created_at}


def token_response(user: User) -> dict:
    now = utcnow()
    expires = now + timedelta(minutes=settings.access_token_minutes)
    token = jwt.encode(
        {"sub": user.id, "iat": now, "exp": expires, "iss": "ai-career-agent"},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_at": expires,
        "user": public_user(user),
    }


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    denied = HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        "登录已失效，请重新登录",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise denied
    try:
        claims = jwt.decode(
            credentials.credentials,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            issuer="ai-career-agent",
            options={"require": ["sub", "exp", "iat"]},
        )
    except jwt.InvalidTokenError:
        raise denied from None
    user = db.get(User, claims["sub"])
    if user is None:
        raise denied
    return user


@router.post("/register", status_code=201)
def register(data: AuthInput, db: Annotated[Session, Depends(get_db)]) -> dict:
    user = User(email=data.email, password_hash=passwords.hash(data.password))
    db.add(user)
    try:
        db.flush()
        db.add(Profile(user_id=user.id, email=user.email))
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "该邮箱已经注册") from None
    return token_response(user)


@router.post("/login")
def login(data: AuthInput, db: Annotated[Session, Depends(get_db)]) -> dict:
    user = db.scalar(select(User).where(User.email == data.email))
    if user is None:
        # Match the cost of password verification to reduce account enumeration by timing.
        passwords.hash(data.password)
        raise HTTPException(401, "邮箱或密码不正确")
    try:
        verified = passwords.verify(data.password, user.password_hash)
    except Exception:
        verified = False
    if not verified:
        raise HTTPException(401, "邮箱或密码不正确")
    return token_response(user)


@router.get("/me")
def me(user: Annotated[User, Depends(get_current_user)]) -> dict:
    return public_user(user)
