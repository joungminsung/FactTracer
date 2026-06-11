import re
from pathlib import Path

from app.main import app


def normalize_path(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "{}", path)


def main() -> None:
    spec_path = Path("../facttracer-next/docs/API_SPEC.md")
    spec = spec_path.read_text()
    declared = [
        (method, normalize_path(path))
        for method, path in re.findall(r"### (GET|POST|PATCH|PUT|DELETE) `([^`]+)`", spec)
    ]

    routes: set[tuple[str, str]] = set()
    for route in app.routes:
        path = getattr(route, "path", "")
        methods = getattr(route, "methods", set())
        normalized_path = normalize_path(path)
        for method in methods:
            if method in {"GET", "POST", "PATCH", "PUT", "DELETE"}:
                routes.add((method, normalized_path))

    missing = [item for item in declared if item not in routes]
    extra = sorted(
        item for item in routes if item[1].startswith("/v1") and item not in declared
    )
    if missing or extra:
        print({"declared": len(declared), "missing": missing, "extra_v1": extra})
        raise SystemExit(1)

    print(f"API spec audit passed: {len(declared)} declared routes matched")


if __name__ == "__main__":
    main()
