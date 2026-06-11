from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.services.notifications.push import deliver_notification
from app.utils import new_id


def create_issue_notification(
    db: Session,
    *,
    body: str,
    issue_id: str,
    title: str,
    type: str,
) -> list[models.Notification]:
    subscribers = db.scalars(select(models.SavedIssue).where(models.SavedIssue.issue_id == issue_id)).all()
    notifications: list[models.Notification] = []
    for saved in subscribers:
        notification = models.Notification(
            body=body,
            href=f"/issues/{issue_id}",
            id=new_id("noti"),
            issue_id=issue_id,
            title=title,
            type=type,
            user_id=saved.user_id,
        )
        db.add(notification)
        db.flush()
        deliver_notification(db, notification=notification)
        notifications.append(notification)
    db.flush()
    return notifications


def notify_update_log(db: Session, *, update_log: models.UpdateLog) -> list[models.Notification]:
    return create_issue_notification(
        db,
        body=update_log.description,
        issue_id=update_log.issue_id,
        title=update_log.title,
        type=update_log.update_type,
    )
