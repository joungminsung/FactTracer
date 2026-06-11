from redis import Redis
from rq import Queue, SimpleWorker

from app.db.schema import ensure_database_schema
from app.db.session import SessionLocal, engine
from app.services.admin.settings import get_effective_setting


def main() -> None:
    ensure_database_schema(engine)
    db = SessionLocal()
    try:
        redis_url = get_effective_setting(db, "redis_url")
    finally:
        db.close()
    redis = Redis.from_url(redis_url)
    worker = SimpleWorker([Queue("facttracer", connection=redis)], connection=redis)
    worker.work()


if __name__ == "__main__":
    main()
