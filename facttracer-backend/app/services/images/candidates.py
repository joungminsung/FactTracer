from __future__ import annotations

import html
import json
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.utils import new_id


def _is_http_url(url: str) -> bool:
    parsed = urlparse(str(url).strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _clean_url(url: str) -> str:
    return html.unescape(str(url or "").strip())


class _ImageMetaParser(HTMLParser):
    def __init__(self, *, base_url: str = "") -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.urls: list[str] = []
        self._seen: set[str] = set()
        self._json_ld_depth = 0
        self._json_ld_chunks: list[str] = []

    def _append_url(self, url: str) -> None:
        cleaned = _clean_url(urljoin(self.base_url, url) if self.base_url else url)
        if not _is_http_url(cleaned) or cleaned in self._seen:
            return
        self.urls.append(cleaned)
        self._seen.add(cleaned)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_name = tag.lower()
        attr_map = {name.lower(): (value or "").strip() for name, value in attrs}
        if tag_name == "script" and "ld+json" in (attr_map.get("type") or "").lower():
            self._json_ld_depth += 1
            return

        if tag_name == "link":
            rel_values = {item.strip().lower() for item in (attr_map.get("rel") or "").split()}
            is_image_preload = "preload" in rel_values and attr_map.get("as", "").lower() == "image"
            if "image_src" in rel_values or is_image_preload:
                self._append_url(attr_map.get("href") or "")
            return

        if tag_name != "meta":
            return
        meta_key = (attr_map.get("property") or attr_map.get("name") or attr_map.get("itemprop") or "").lower()
        if meta_key not in {"og:image", "og:image:url", "og:image:secure_url", "twitter:image", "twitter:image:src", "image"}:
            return
        self._append_url(attr_map.get("content") or "")

    def handle_data(self, data: str) -> None:
        if self._json_ld_depth:
            self._json_ld_chunks.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "script" and self._json_ld_depth:
            self._json_ld_depth -= 1

    def append_json_ld_images(self) -> None:
        raw_json = "".join(self._json_ld_chunks).strip()
        if not raw_json:
            return
        try:
            payload = json.loads(raw_json)
        except json.JSONDecodeError:
            return
        for url in _json_ld_image_urls(payload):
            self._append_url(url)


def _json_ld_image_urls(payload: object) -> list[str]:
    urls: list[str] = []
    if isinstance(payload, list):
        for item in payload:
            urls.extend(_json_ld_image_urls(item))
        return urls
    if not isinstance(payload, dict):
        return urls

    image = payload.get("image")
    if isinstance(image, str):
        urls.append(image)
    elif isinstance(image, list):
        for item in image:
            if isinstance(item, str):
                urls.append(item)
            elif isinstance(item, dict):
                urls.extend(_json_ld_image_object_urls(item))
    elif isinstance(image, dict):
        urls.extend(_json_ld_image_object_urls(image))
    graph = payload.get("@graph")
    if isinstance(graph, list):
        for item in graph:
            urls.extend(_json_ld_image_urls(item))
    return urls


def _json_ld_image_object_urls(payload: dict) -> list[str]:
    urls: list[str] = []
    for key in ("url", "contentUrl"):
        value = payload.get(key)
        if isinstance(value, str):
            urls.append(value)
    return urls


def extract_image_urls_from_html(raw_html: str, *, base_url: str = "") -> list[str]:
    parser = _ImageMetaParser(base_url=base_url)
    parser.feed(raw_html or "")
    parser.append_json_ld_images()
    return parser.urls


def upsert_image_candidate(
    db: Session,
    *,
    url: str,
    article_id: str | None = None,
    height: int = 0,
    issue_id: str | None = None,
    mime_type: str = "",
    publisher: str = "",
    source_type: str = "news",
    source_url: str = "",
    width: int = 0,
) -> models.ImageCandidate | None:
    cleaned_url = _clean_url(url)
    if not _is_http_url(cleaned_url):
        return None

    query = select(models.ImageCandidate).where(models.ImageCandidate.url == cleaned_url)
    if article_id:
        query = query.where(models.ImageCandidate.article_id == article_id)
    elif issue_id:
        query = query.where(
            models.ImageCandidate.article_id.is_(None),
            models.ImageCandidate.issue_id == issue_id,
        )
    else:
        query = query.where(
            models.ImageCandidate.article_id.is_(None),
            models.ImageCandidate.issue_id.is_(None),
        )
    candidate = db.scalar(query.limit(1))
    if candidate:
        if article_id and not candidate.article_id:
            candidate.article_id = article_id
        if issue_id and not candidate.issue_id:
            candidate.issue_id = issue_id
        if source_url and not candidate.source_url:
            candidate.source_url = source_url
        if publisher and not candidate.publisher:
            candidate.publisher = publisher
        if source_type and (not candidate.source_type or candidate.source_type == "news"):
            candidate.source_type = source_type
        if width and not candidate.width:
            candidate.width = width
        if height and not candidate.height:
            candidate.height = height
        if mime_type and not candidate.mime_type:
            candidate.mime_type = mime_type
        candidate.updated_at = models.now_utc()
        db.flush()
        return candidate

    candidate = models.ImageCandidate(
        article_id=article_id,
        height=max(0, int(height or 0)),
        id=new_id("image"),
        issue_id=issue_id,
        mime_type=mime_type,
        publisher=publisher,
        source_type=source_type or "news",
        source_url=source_url,
        status="candidate",
        url=cleaned_url,
        width=max(0, int(width or 0)),
    )
    db.add(candidate)
    db.flush()
    return candidate


def persist_parsed_image_candidates(
    db: Session,
    *,
    article: models.Article,
    parsed: object,
    issue_id: str | None = None,
    source_type: str = "",
    source_url: str = "",
) -> list[models.ImageCandidate]:
    urls = list(getattr(parsed, "image_candidates", None) or [])
    candidates: list[models.ImageCandidate] = []
    seen: set[str] = set()
    for url in urls:
        value = str(url or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        candidate = upsert_image_candidate(
            db,
            article_id=article.id,
            issue_id=article.issue_id or issue_id,
            publisher=article.publisher or str(getattr(parsed, "publisher", "") or ""),
            source_type=source_type or article.source_type,
            source_url=source_url or article.url,
            url=value,
        )
        if candidate:
            candidates.append(candidate)
    return candidates


def link_image_candidates_to_issue(
    db: Session,
    *,
    article_id: str,
    issue_id: str,
) -> list[models.ImageCandidate]:
    linked, _ = link_image_candidates_to_issue_with_previous(db, article_id=article_id, issue_id=issue_id)
    return linked


def link_image_candidates_to_issue_with_previous(
    db: Session,
    *,
    article_id: str,
    issue_id: str,
) -> tuple[list[models.ImageCandidate], set[str]]:
    candidates = db.scalars(
        select(models.ImageCandidate).where(models.ImageCandidate.article_id == article_id),
    ).all()
    linked: list[models.ImageCandidate] = []
    previous_issue_ids: set[str] = set()
    for candidate in candidates:
        if candidate.issue_id == issue_id:
            linked.append(candidate)
            continue
        if candidate.issue_id:
            previous_issue_ids.add(candidate.issue_id)
        candidate.issue_id = issue_id
        candidate.updated_at = models.now_utc()
        linked.append(candidate)
    if linked:
        db.flush()
    return linked, previous_issue_ids
