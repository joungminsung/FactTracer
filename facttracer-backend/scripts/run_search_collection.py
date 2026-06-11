import argparse

from app.db.schema import ensure_database_schema
from app.db.session import SessionLocal, engine
from app.services.search.keywords import seed_search_keywords
from app.workers.issue_jobs import search_news


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("query")
    parser.add_argument("--topic", default="정치")
    parser.add_argument("--interval-minutes", type=int, default=30)
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--max-items", type=int, default=3)
    args = parser.parse_args()

    ensure_database_schema(engine)
    db = SessionLocal()
    try:
        keywords = seed_search_keywords(
            db,
            interval_minutes=args.interval_minutes,
            priority="high",
            query=args.query,
            source="cli",
            topic=args.topic,
        )
        for keyword in keywords:
            keyword.metadata_json = {**(keyword.metadata_json or {}), "max_items": args.max_items}
        db.commit()
        selected = keywords[: args.limit]
        results = [search_news(keyword.id) for keyword in selected]
        print(
            {
                "query": args.query,
                "keywords": [keyword.query for keyword in selected],
                "results": results,
            },
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
