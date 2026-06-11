from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models import User


def optional_current_user(
    db: Annotated[Session, Depends(get_db)],
    authorization: Annotated[str | None, Header()] = None,
) -> User | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    payload = decode_access_token(token)
    return db.get(User, payload["sub"])


def optional_public_current_user(
    db: Annotated[Session, Depends(get_db)],
    authorization: Annotated[str | None, Header()] = None,
) -> User | None:
    try:
        return optional_current_user(db, authorization)
    except HTTPException:
        return None


def current_user(user: Annotated[User | None, Depends(optional_current_user)]) -> User:
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"message": "로그인 상태를 확인해 주세요.", "code": "UNAUTHORIZED"},
        )
    return user


def reviewer_user(user: Annotated[User, Depends(current_user)]) -> User:
    if user.role not in {"admin", "reviewer"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"message": "이 화면을 볼 권한이 없습니다.", "code": "FORBIDDEN"},
        )
    return user
