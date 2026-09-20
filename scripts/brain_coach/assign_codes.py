"""
One-off script to backfill `code` values for brain coach questions that
were created before the project had a `code` convention (trivia and
cognitive_assessment). Codes are assigned as "<prefix>_<n>" (no leading
zeroes), e.g. trivia_1, trivia_2, ..., cognitive_1, cognitive_2, ...

Usage:
    python scripts/brain_coach/assign_codes.py
"""

import sys
from pathlib import Path
import logging

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.database import SessionLocal
from models.brain_coach import BrainCoachQuestions

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# category -> code prefix
CATEGORY_PREFIXES = {
    "trivia": "trivia",
    "cognitive_assessment": "cognitive",
}


def assign_codes():
    with SessionLocal() as db:
        for category, prefix in CATEGORY_PREFIXES.items():
            questions = (
                db.query(BrainCoachQuestions)
                .filter(
                    BrainCoachQuestions.category == category,
                    BrainCoachQuestions.code.is_(None),
                )
                .order_by(BrainCoachQuestions.id)
                .all()
            )

            for i, question in enumerate(questions, start=1):
                question.code = f"{prefix}_{i}"

            db.commit()
            logger.info(f"Assigned codes to {len(questions)} '{category}' questions ({prefix}_1..{prefix}_{len(questions)})")


if __name__ == "__main__":
    assign_codes()
