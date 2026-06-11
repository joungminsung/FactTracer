from app.db.session import SessionLocal
from app.services.jobs import run_due_jobs


def main() -> None:
    db = SessionLocal()
    try:
        jobs = run_due_jobs(db, limit=50)
        db.commit()
        print({"status": "completed", "executed": len(jobs)})
    finally:
        db.close()


if __name__ == "__main__":
    main()
