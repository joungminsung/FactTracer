from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class CollectedArticle:
    title: str
    url: str
    publisher: str = ""
    body_text: str = ""
    summary: str = ""
    published_at: datetime | None = None
    source_type: str = "news"
    image_url: str = ""
    image_candidates: list[str] = field(default_factory=list)
