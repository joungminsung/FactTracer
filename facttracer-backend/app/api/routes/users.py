from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.api.dependencies import current_user
from app.db.session import get_db
from app.schemas import (
    AuthUser,
    DeviceTokenRequest,
    MutationResponse,
    NotificationSettings,
    UserDashboardResponse,
    UserNotificationsResponse,
    UserPreferencesUpdateRequest,
    UserProfileUpdateRequest,
)
from app.serializers import (
    auth_user,
    saved_issue,
    submitted_claim,
    user_notification,
    verification_request,
)
from app.utils import default_notification_settings

router = APIRouter(prefix="/users/me", tags=["users"])


@router.get("", response_model=AuthUser)
def me(user: Annotated[models.User, Depends(current_user)]) -> AuthUser:
    return auth_user(user)


@router.patch("", response_model=AuthUser)
def update_me(
    payload: UserProfileUpdateRequest,
    user: Annotated[models.User, Depends(current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> AuthUser:
    user.name = payload.name
    db.commit()
    db.refresh(user)
    return auth_user(user)


@router.get("/dashboard", response_model=UserDashboardResponse)
def dashboard(
    user: Annotated[models.User, Depends(current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> UserDashboardResponse:
    saved_issue_ids = db.scalars(
        select(models.SavedIssue.issue_id).where(models.SavedIssue.user_id == user.id),
    ).all()
    issues = (
        db.scalars(select(models.Issue).where(models.Issue.id.in_(saved_issue_ids))).all()
        if saved_issue_ids
        else []
    )
    claims = db.scalars(
        select(models.SubmittedClaim)
        .where(models.SubmittedClaim.user_id == user.id)
        .order_by(models.SubmittedClaim.submitted_at.desc()),
    ).all()
    issue_by_id = {
        issue.id: issue
        for issue in db.scalars(
            select(models.Issue).where(models.Issue.id.in_({claim.issue_id for claim in claims})),
        ).all()
    }
    requests = db.scalars(
        select(models.VerificationRequest)
        .where(models.VerificationRequest.user_id == user.id)
        .order_by(models.VerificationRequest.requested_at.desc()),
    ).all()

    return UserDashboardResponse(
        savedIssues=[saved_issue(issue) for issue in issues],
        submittedClaims=[submitted_claim(claim, issue_by_id.get(claim.issue_id)) for claim in claims],
        user=auth_user(user),
        verificationRequests=[verification_request(request) for request in requests],
    )


@router.put("/saved-issues/{issue_id}", response_model=MutationResponse)
def save_issue(
    issue_id: str,
    user: Annotated[models.User, Depends(current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> MutationResponse:
    issue = db.get(models.Issue, issue_id)
    if not issue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "해당 항목을 찾을 수 없습니다.", "code": "NOT_FOUND"},
        )
    existing = db.get(models.SavedIssue, {"user_id": user.id, "issue_id": issue_id})
    if not existing:
        db.add(models.SavedIssue(issue_id=issue_id, user_id=user.id))
        db.commit()
    return MutationResponse(id=issue_id, message="이슈가 내 계정에 저장되었습니다.", status="updated")


@router.delete("/saved-issues/{issue_id}", response_model=MutationResponse)
def remove_saved_issue(
    issue_id: str,
    user: Annotated[models.User, Depends(current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> MutationResponse:
    row = db.get(models.SavedIssue, {"user_id": user.id, "issue_id": issue_id})
    if row:
        db.delete(row)
        db.commit()
    return MutationResponse(id=issue_id, message="저장 이슈에서 제거했습니다.", status="updated")


@router.delete("/submitted-claims/{claim_id}", response_model=MutationResponse)
def withdraw_claim(
    claim_id: str,
    user: Annotated[models.User, Depends(current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> MutationResponse:
    claim = db.get(models.SubmittedClaim, claim_id)
    if not claim or claim.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "해당 항목을 찾을 수 없습니다.", "code": "NOT_FOUND"},
        )
    claim.status = "withdrawn"
    db.commit()
    return MutationResponse(id=claim_id, message="제출한 주장을 철회했습니다.", status="updated")


@router.delete("/verification-requests/{request_id}", response_model=MutationResponse)
def cancel_verification_request(
    request_id: str,
    user: Annotated[models.User, Depends(current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> MutationResponse:
    request = db.get(models.VerificationRequest, request_id)
    if not request or request.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "해당 항목을 찾을 수 없습니다.", "code": "NOT_FOUND"},
        )
    request.status = "cancelled"
    db.commit()
    return MutationResponse(id=request_id, message="검증 요청을 취소했습니다.", status="updated")


@router.get("/notifications", response_model=UserNotificationsResponse)
def notifications(
    user: Annotated[models.User, Depends(current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> UserNotificationsResponse:
    saved_issue_ids = db.scalars(
        select(models.SavedIssue.issue_id).where(models.SavedIssue.user_id == user.id),
    ).all()
    followed = (
        db.scalars(select(models.Issue).where(models.Issue.id.in_(saved_issue_ids))).all()
        if saved_issue_ids
        else []
    )
    rows = db.scalars(
        select(models.Notification)
        .where(models.Notification.user_id == user.id)
        .order_by(models.Notification.created_at.desc())
        .limit(50),
    ).all()
    issue_by_id = {
        issue.id: issue
        for issue in db.scalars(
            select(models.Issue).where(models.Issue.id.in_({row.issue_id for row in rows if row.issue_id})),
        ).all()
    }
    return UserNotificationsResponse(
        followedIssues=[saved_issue(issue) for issue in followed],
        notifications=[user_notification(row, issue_by_id.get(row.issue_id or "")) for row in rows],
        settings=NotificationSettings(**(user.preferences or default_notification_settings())),
    )


@router.patch("/preferences", response_model=MutationResponse)
def update_preferences(
    payload: UserPreferencesUpdateRequest,
    user: Annotated[models.User, Depends(current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> MutationResponse:
    next_preferences = user.preferences or default_notification_settings()
    for key, value in payload.model_dump(exclude_none=True).items():
        next_preferences[key] = value
    user.preferences = next_preferences
    db.commit()
    return MutationResponse(id=user.id, message="알림 설정을 저장했습니다.", status="updated")


@router.post("/device-tokens", response_model=MutationResponse)
def register_device_token(
    payload: DeviceTokenRequest,
    user: Annotated[models.User, Depends(current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> MutationResponse:
    existing = db.scalar(
        select(models.DeviceToken).where(
            models.DeviceToken.user_id == user.id,
            models.DeviceToken.token == payload.token,
        ),
    )
    if existing:
        existing.platform = payload.platform
        existing.status = "active"
        existing.updated_at = models.now_utc()
        token_id = existing.id
    else:
        row = models.DeviceToken(
            id=f"dev_{payload.token[-12:]}",
            platform=payload.platform,
            token=payload.token,
            user_id=user.id,
        )
        db.add(row)
        token_id = row.id
    db.commit()
    return MutationResponse(id=token_id, message="디바이스 알림 토큰을 저장했습니다.", status="updated")
