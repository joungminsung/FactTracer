from __future__ import annotations

import argparse
import json

from app.db.session import SessionLocal
from app.services.issues.repair import repair_information_quality


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Repair contaminated issue/article quality signals.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="Write changes to the configured database.")
    mode.add_argument("--dry-run", action="store_true", help="Inspect changes without writing them. This is the default.")
    parser.add_argument("--affected-only", action="store_true", help="Rebuild only issues whose articles or retry keywords changed.")
    parser.add_argument("--limit", type=int, default=None, help="Limit the number of issues rebuilt/reassessed.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    apply_changes = bool(args.apply)
    db = SessionLocal()
    try:
        result = repair_information_quality(
            db,
            apply=apply_changes,
            rebuild_all=not args.affected_only,
            limit=args.limit,
        )
        if apply_changes:
            db.commit()
        else:
            db.rollback()
        print(json.dumps({"applied": apply_changes, **result}, ensure_ascii=False, indent=2))
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
