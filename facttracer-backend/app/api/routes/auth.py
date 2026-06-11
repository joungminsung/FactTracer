from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.schemas import AuthSession, LoginRequest, SignupRequest
from app.serializers import auth_user
from app.utils import default_notification_settings, new_id

router = APIRouter(prefix="/auth", tags=["auth"])


def build_session(user: models.User) -> AuthSession:
    token, expires_at = create_access_token(user.id, user.role)
    return AuthSession(
        accessToken=token,
        expiresAt=expires_at.isoformat(),
        refreshToken=None,
        user=auth_user(user),
    )


@router.post("/signup", response_model=AuthSession, status_code=status.HTTP_201_CREATED)
def signup(payload: SignupRequest, db: Annotated[Session, Depends(get_db)]) -> AuthSession:
    existing = db.scalar(select(models.User).where(models.User.email == payload.email))
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": "이미 가입된 이메일입니다.", "code": "EMAIL_EXISTS"},
        )

    user_count = db.scalar(select(func.count()).select_from(models.User)) or 0
    user = models.User(
        email=payload.email,
        id=new_id("usr"),
        last_login_at=datetime.now(UTC),
        name=payload.name,
        password_hash=hash_password(payload.password),
        preferences=default_notification_settings(),
        role="admin" if user_count == 0 else "user",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return build_session(user)


@router.post("/login", response_model=AuthSession)
def login(payload: LoginRequest, db: Annotated[Session, Depends(get_db)]) -> AuthSession:
    user = db.scalar(select(models.User).where(models.User.email == payload.email))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"message": "이메일 또는 비밀번호를 확인해 주세요.", "code": "INVALID_LOGIN"},
        )
    user.last_login_at = datetime.now(UTC)
    db.commit()
    db.refresh(user)
    return build_session(user)
