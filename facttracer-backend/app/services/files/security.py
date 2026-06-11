from __future__ import annotations

from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.services.admin.settings import get_effective_setting


BLOCKED_SCHEMES = {"file", "javascript", "data"}


def validate_external_url(url: str) -> tuple[bool, str]:
    parsed = urlparse(url)
    if parsed.scheme.lower() in BLOCKED_SCHEMES:
        return False, "허용되지 않는 URL 형식입니다."
    if parsed.scheme.lower() not in {"http", "https"}:
        return False, "http 또는 https URL만 입력할 수 있습니다."
    if not parsed.netloc:
        return False, "도메인이 없는 URL입니다."
    return True, ""


def validate_upload_metadata(
    *,
    content_type: str,
    db: Session | None = None,
    size_bytes: int,
) -> tuple[bool, str]:
    upload_max_bytes = get_effective_setting(db, "upload_max_bytes")
    allowed_upload_mime_types = get_effective_setting(db, "allowed_upload_mime_types")
    if size_bytes > upload_max_bytes:
        return False, "파일 크기가 허용 범위를 초과했습니다."
    if content_type not in allowed_upload_mime_types:
        return False, "지원하지 않는 파일 형식입니다."
    return True, ""
