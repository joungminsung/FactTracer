from sqlalchemy import select

from app import models
from app.db.schema import ensure_database_schema
from app.db.session import SessionLocal, engine
from app.services.classification.taxonomy import classify_issue_taxonomy


def main() -> None:
    ensure_database_schema(engine)
    db = SessionLocal()
    try:
        issues = db.scalars(select(models.Issue).where(models.Issue.status.notin_(["숨김", "병합됨"]))).all()
        for issue in issues:
            classify_issue_taxonomy(db, issue=issue)
        db.commit()
        print(f"Backfilled taxonomy for {len(issues)} issues")
    finally:
        db.close()


if __name__ == "__main__":
    main()
