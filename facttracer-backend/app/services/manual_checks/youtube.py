from __future__ import annotations

import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from app.core.config import get_settings
from app.services.articles.normalizer import normalize_whitespace


def youtube_video_id(url: str) -> str | None:
    parsed = urllib.parse.urlparse(url)
    if parsed.netloc.endswith("youtu.be"):
        return parsed.path.strip("/") or None
    query = urllib.parse.parse_qs(parsed.query)
    if "v" in query:
        return query["v"][0]
    match = re.search(r"/(?:shorts|embed)/([^/?#]+)", parsed.path)
    return match.group(1) if match else None


def fetch_youtube_transcript(url: str) -> tuple[str, str]:
    video_id = youtube_video_id(url)
    if not video_id:
        return "", "invalid_youtube_url"
    endpoint = "https://video.google.com/timedtext?" + urllib.parse.urlencode(
        {"lang": "ko", "v": video_id},
    )
    request = urllib.request.Request(endpoint, headers={"User-Agent": get_settings().collector_user_agent})
    try:
        with urllib.request.urlopen(request, timeout=get_settings().collector_timeout_seconds) as response:
            raw = response.read(2_000_000)
        root = ET.fromstring(raw)
        text = " ".join(item.text or "" for item in root.findall(".//text"))
        text = normalize_whitespace(text)
        return text, "parsed" if text else "empty_transcript"
    except Exception:
        return "", "transcript_unavailable"
