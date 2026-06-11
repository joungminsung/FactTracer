from __future__ import annotations

import html
import xml.etree.ElementTree as ET
from urllib.parse import urlparse


def _is_http_url(url: str) -> bool:
    parsed = urlparse(str(url).strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def extract_media_image_urls(item: ET.Element) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    for child in item.iter():
        if child is item:
            continue
        tag_name = _local_name(child.tag)
        media_type = (child.attrib.get("type") or "").lower()
        medium = (child.attrib.get("medium") or "").lower()
        rel = (child.attrib.get("rel") or "").lower()

        if tag_name == "thumbnail":
            url = child.attrib.get("url") or child.attrib.get("href") or ""
        elif tag_name == "content" and (not medium or medium == "image" or media_type.startswith("image/")):
            url = child.attrib.get("url") or child.attrib.get("href") or ""
        elif tag_name == "enclosure" and media_type.startswith("image/"):
            url = child.attrib.get("url") or child.attrib.get("href") or ""
        elif tag_name == "link" and media_type.startswith("image/") and rel in {"enclosure", "image", ""}:
            url = child.attrib.get("href") or child.attrib.get("url") or ""
        else:
            continue

        cleaned = html.unescape(url.strip())
        if not _is_http_url(cleaned) or cleaned in seen:
            continue
        urls.append(cleaned)
        seen.add(cleaned)
    return urls
