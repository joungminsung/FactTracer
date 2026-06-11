from __future__ import annotations

from app.services.files.storage import read_storage_url


def extract_text_from_file(*, content_type: str, storage_url: str) -> tuple[str, str]:
    data = read_storage_url(storage_url)
    if not data:
        return "", "empty"
    if content_type == "text/plain":
        return data.decode("utf-8", errors="ignore"), "parsed"
    if content_type == "application/pdf":
        text = _extract_pdf_text(data)
        return (text, "parsed" if text else "needs_ocr")
    if content_type.startswith("image/"):
        text = _extract_image_text(data)
        return (text, "parsed" if text else "needs_ocr")
    return data.decode("utf-8", errors="ignore"), "fallback_text"


def _extract_pdf_text(data: bytes) -> str:
    try:
        from io import BytesIO

        from pypdf import PdfReader

        reader = PdfReader(BytesIO(data))
        return "\n".join(page.extract_text() or "" for page in reader.pages).strip()
    except Exception:
        return data.decode("utf-8", errors="ignore")


def _extract_image_text(data: bytes) -> str:
    try:
        from io import BytesIO

        import pytesseract
        from PIL import Image

        return pytesseract.image_to_string(Image.open(BytesIO(data)), lang="kor+eng").strip()
    except Exception:
        return ""
