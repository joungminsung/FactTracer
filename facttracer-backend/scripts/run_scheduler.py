import time
import os

from app.db.schema import ensure_database_schema
from app.db.session import SessionLocal, engine
from app.services.admin.settings import get_effective_setting
from app.services.scheduler.runtime import tick_scheduler_once


def tick() -> dict:
    db = SessionLocal()
    try:
        result = tick_scheduler_once(db, owner_id=f"cli:{os.getpid()}")
        db.commit()
        return result
    finally:
        db.close()


def scheduler_poll_seconds() -> int:
    db = SessionLocal()
    try:
        return int(get_effective_setting(db, "scheduler_poll_seconds"))
    finally:
        db.close()


def main() -> None:
    ensure_database_schema(engine)
    while True:
        print({"status": "tick", **tick()})
        time.sleep(scheduler_poll_seconds())


if __name__ == "__main__":
    main()
