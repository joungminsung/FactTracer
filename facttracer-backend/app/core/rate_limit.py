from __future__ import annotations

import time
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable

from fastapi import Request
from fastapi.responses import JSONResponse, Response

from app.db.session import SessionLocal
from app.services.admin.settings import get_effective_setting

_requests: dict[str, deque[float]] = defaultdict(deque)


async def rate_limit_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    db = SessionLocal()
    try:
        rate_limit_per_minute = int(get_effective_setting(db, "rate_limit_per_minute"))
    finally:
        db.close()
    if rate_limit_per_minute <= 0 or request.url.path == "/health":
        return await call_next(request)
    key = request.headers.get("authorization") or request.client.host if request.client else "unknown"
    now = time.monotonic()
    bucket = _requests[key]
    while bucket and now - bucket[0] > 60:
        bucket.popleft()
    if len(bucket) >= rate_limit_per_minute:
        return JSONResponse(
            status_code=429,
            content={
                "message": "요청이 너무 많습니다. 잠시 후 다시 시도해 주세요.",
                "code": "RATE_LIMITED",
                "details": {},
            },
        )
    bucket.append(now)
    return await call_next(request)
