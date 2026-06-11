from datetime import datetime
from uuid import uuid4


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def to_iso(value: datetime | None) -> str:
    if value is None:
        return ""
    return value.isoformat()


def default_notification_settings() -> dict:
    return {
        "dailyDigest": False,
        "numberChanges": True,
        "officialSourceChanges": True,
        "preferredPerspective": "균형",
        "reviewCompleted": True,
        "timelineUpdates": True,
    }
