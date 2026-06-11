from __future__ import annotations

import base64
from pathlib import Path

from app.core.config import get_settings


def storage_root() -> Path:
    path = Path(get_settings().object_storage_path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def store_base64_file(*, content_base64: str, file_id: str, filename: str) -> tuple[str, int]:
    suffix = Path(filename).suffix[:16]
    target = storage_root() / f"{file_id}{suffix}"
    data = base64.b64decode(content_base64)
    target.write_bytes(data)
    return str(target), len(data)


def store_binary_file(*, data: bytes, directory: str = "", file_id: str, suffix: str) -> tuple[str, int]:
    clean_suffix = suffix if suffix.startswith(".") else f".{suffix}"
    clean_suffix = clean_suffix[:16]
    root = storage_root()
    if directory:
        root = root / directory.strip("/").replace("..", "")
        root.mkdir(parents=True, exist_ok=True)
    target = root / f"{file_id}{clean_suffix}"
    target.write_bytes(data)
    return str(target), len(data)


def read_storage_url(storage_url: str) -> bytes:
    if not storage_url:
        return b""
    if storage_url.startswith("http://") or storage_url.startswith("https://"):
        import urllib.request

        with urllib.request.urlopen(storage_url, timeout=get_settings().collector_timeout_seconds) as response:
            return response.read(get_settings().upload_max_bytes)
    return Path(storage_url).read_bytes()
