"""
Exports brain coach questions (with their code and translations) from the
database into JSON files, one per category, in the same shape as the
kb/*.json files (see kb/chess.json), then emails them as attachments.

Usage:
    python scripts/brain_coach/export_and_email_questions.py
"""

import sys
import json
import asyncio
from pathlib import Path
import logging

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.database import SessionLocal
from models.brain_coach import BrainCoachQuestions, QuestionTranslations
from services.email_service import email_service

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

RECIPIENT_EMAIL = "abdulrauf_99@outlook.com"
OUTPUT_DIR = Path(__file__).parent / "kb_exports"


def export_category(db, category: str) -> list:
    questions = (
        db.query(BrainCoachQuestions)
        .filter(BrainCoachQuestions.category == category)
        .order_by(BrainCoachQuestions.id)
        .all()
    )

    exported = []
    for question in questions:
        translations = (
            db.query(QuestionTranslations)
            .filter(QuestionTranslations.question_id == question.id)
            .all()
        )

        exported.append({
            "id": question.code,
            "category": question.category,
            "type": question.type,
            "difficulty": question.difficulty,
            "translations": [
                {
                    "language": translation.language,
                    "question": translation.question_text,
                    "answer": translation.expected_answer,
                }
                for translation in translations
            ],
        })

    return exported


def export_all_categories() -> dict:
    with SessionLocal() as db:
        categories = [row[0] for row in db.query(BrainCoachQuestions.category).distinct().all()]

        files = {}
        for category in categories:
            data = export_category(db, category)
            files[f"{category}.json"] = data
            logger.info(f"Exported {len(data)} questions for category '{category}'")

        return files


async def email_export(files: dict):
    OUTPUT_DIR.mkdir(exist_ok=True)

    attachments = []
    for file_name, data in files.items():
        file_path = OUTPUT_DIR / file_name
        file_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

        attachments.append({
            "file_name": file_name,
            "file_data": file_path.read_bytes(),
        })

    await email_service.send_email_via_mailgun(
        to=[RECIPIENT_EMAIL],
        subject="Brain Coach Question Export",
        text=f"Attached: {', '.join(files.keys())}",
        attachments=attachments,
    )

    logger.info(f"Emailed {len(attachments)} file(s) to {RECIPIENT_EMAIL}")


if __name__ == "__main__":
    exported_files = export_all_categories()
    asyncio.run(email_export(exported_files))
