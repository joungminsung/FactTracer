from __future__ import annotations

from app.services.files.security import validate_external_url


def validate_manual_input(*, content: str, input_type: str) -> tuple[bool, str]:
    if input_type == "url":
        return validate_external_url(content)
    if input_type in {"text", "youtube"}:
        return (len(content.strip()) >= 8, "내용이 너무 짧습니다." if len(content.strip()) < 8 else "")
    if input_type in {"image", "pdf", "file"}:
        return (bool(content.strip()), "파일 ID가 필요합니다." if not content.strip() else "")
    return False, "지원하지 않는 입력 형식입니다."
