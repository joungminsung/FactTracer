from __future__ import annotations

import json
import urllib.request

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.core.config import get_settings
from app.services.admin.settings import get_effective_setting


def deliver_notification(db: Session, *, notification: models.Notification) -> None:
    tokens = db.scalars(
        select(models.DeviceToken).where(
            models.DeviceToken.user_id == notification.user_id,
            models.DeviceToken.status == "active",
        ),
    ).all()
    if not tokens:
        notification.delivery_status = "stored"
        db.flush()
        return
    settings = get_settings()
    expo_push_enabled = get_effective_setting(db, "expo_push_enabled")
    expo_push_url = get_effective_setting(db, "expo_push_url")
    if not expo_push_enabled:
        notification.delivery_status = "push_queued"
        db.flush()
        return
    try:
        payload = [
            {
                "to": token.token,
                "title": notification.title,
                "body": notification.body,
                "data": {"href": notification.href, "issueId": notification.issue_id},
            }
            for token in tokens
        ]
        request = urllib.request.Request(
            expo_push_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=settings.collector_timeout_seconds) as response:
            response.read()
        notification.delivery_status = "push_sent"
    except Exception:
        notification.delivery_status = "push_failed"
    db.flush()
