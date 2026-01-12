from sqlalchemy import update
from core.database import SessionLocal
from models.brain_coach import BrainCoachQuestions


def update_category():
    db = SessionLocal()
    try:
        stmt = (
            update(BrainCoachQuestions)
            .where(BrainCoachQuestions.category.is_(None))
            .values(category="cognitive_assessment")
        )

        result = db.execute(stmt)
        db.commit()

        print(f"Updated {result.rowcount} records")

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()