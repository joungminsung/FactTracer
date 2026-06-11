from __future__ import annotations

import hashlib
import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse


TRACKING_PREFIXES = ("utm_",)
TRACKING_KEYS = {"fbclid", "gclid", "igshid", "mc_cid", "mc_eid", "ref"}


def normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def normalize_url(url: str) -> str:
    parsed = urlparse(str(url).strip())
    query_items = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key not in TRACKING_KEYS and not key.startswith(TRACKING_PREFIXES)
    ]
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/") or "/"
    return urlunparse((parsed.scheme.lower() or "https", netloc, path, "", urlencode(query_items), ""))


def hash_text(value: str) -> str:
    return hashlib.sha256(normalize_whitespace(value).lower().encode("utf-8")).hexdigest()


def article_dedup_hash(*, title: str, url: str, body_text: str = "") -> str:
    normalized_url = normalize_url(url)
    if normalized_url:
        return hash_text(normalized_url)
    basis = f"{title}\n{body_text[:1200]}"
    return hash_text(basis)


def token_set(value: str) -> set[str]:
    normalized = normalize_whitespace(value).lower()
    return {token for token in re.split(r"[^0-9a-zA-Z가-힣]+", normalized) if len(token) >= 2}


def jaccard_similarity(left: str, right: str) -> float:
    left_tokens = token_set(left)
    right_tokens = token_set(right)
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)
