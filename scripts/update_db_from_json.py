"""
Update the brain coach questions in the DB from the JSON files in scripts/brain_coach/.

Connection: core.database (.env DATABASE_URL).
Matching:   JSON "id" == BrainCoachQuestions.code

For every JSON entry:
  - BrainCoachQuestions: UPDATE only (never created). Sets type and difficulty when the
    JSON value is non-empty.
  - QuestionTranslations: created or updated per (question, language). Blank JSON values
    never overwrite data that is already in the database.

JSON entries whose code does not exist in the DB are skipped and reported
(session/tier are NOT NULL, so questions can't be created from JSON alone).

Everything runs in one transaction.

Usage:
    .venv/bin/python scripts/update_db_from_json.py            # apply changes
    .venv/bin/python scripts/update_db_from_json.py --dry-run  # preview, nothing saved
"""

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import select

# make `core` / `models` importable when running as `python scripts/update_db_from_json.py`
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import models  # noqa: E402,F401  (registers every mapper so relationships resolve)
from core.database import get_sync_session  # noqa: E402
from models.brain_coach import BrainCoachQuestions, QuestionTranslations  # noqa: E402

JSON_DIR = Path(__file__).parent / "brain_coach"
JSON_FILES = [
    "cognitive_assessment.json",
    "games.json",
    "memory.json",
    "trivia.json",
]


def clean(value):
    """Return a stripped string, or None if the value is missing/blank."""
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def run(session, dry_run):
    questions = {
        q.code: q
        for q in session.scalars(
            select(BrainCoachQuestions).where(BrainCoachQuestions.code.is_not(None))
        )
    }
    translations = {
        (t.question_id, t.language): t
        for t in session.scalars(select(QuestionTranslations))
    }

    stats = {
        "questions_seen": 0,
        "questions_updated": 0,
        "translations_inserted": 0,
        "translations_updated": 0,
    }
    # per-language tracker: {"en": {"inserted": n, "updated": n}, ...}
    by_language = {}
    missing_codes = []

    try:
        for filename in JSON_FILES:
            entries = json.loads((JSON_DIR / filename).read_text(encoding="utf-8"))
            print(f"{filename}: {len(entries)} entries")

            for entry in entries:
                stats["questions_seen"] += 1
                code = entry["id"]
                question = questions.get(code)
                if question is None:
                    missing_codes.append(code)
                    continue

                question.difficulty = clean(entry.get("difficulty")) or question.difficulty
                question.type = clean(entry.get("type")) or question.type
                stats["questions_updated"] += 1

                for t in entry.get("translations", []):
                    language = clean(t.get("language"))
                    question_text = clean(t.get("question"))
                    expected_answer = clean(t.get("answer"))
                    question_type = clean(t.get("question_type"))
                    if not (language and question_text and expected_answer and question_type):
                        print(f"  skipped incomplete translation: {code} [{language}]")
                        continue

                    scoring_logic = clean(t.get("scoring_logic"))
                    theme = clean(t.get("theme"))

                    translation = translations.get((question.id, language))
                    if translation is None:
                        translation = QuestionTranslations(
                            question_id=question.id,
                            language=language,
                            question_text=question_text,
                            expected_answer=expected_answer,
                            question_type=question_type,
                            scoring_logic=scoring_logic,
                            theme=theme,
                        )
                        session.add(translation)
                        translations[(question.id, language)] = translation
                        action = "inserted"
                    else:
                        translation.question_text = question_text
                        translation.expected_answer = expected_answer
                        translation.question_type = question_type
                        translation.scoring_logic = scoring_logic or translation.scoring_logic or None
                        translation.theme = theme or translation.theme or None
                        action = "updated"

                    stats[f"translations_{action}"] += 1
                    counts = by_language.setdefault(language, {"inserted": 0, "updated": 0})
                    counts[action] += 1

        if dry_run:
            session.rollback()
            print("\nDRY RUN -> rolled back, nothing was saved.")
        else:
            session.commit()
            print("\nCommitted.")
    except Exception:
        session.rollback()
        print("\nError -> rolled back, nothing was saved.")
        raise

    print("\nSummary")
    for key, value in stats.items():
        print(f"  {key}: {value}")
    print("\nTranslations by language")
    for language in sorted(by_language):
        c = by_language[language]
        print(f"  {language}: inserted={c['inserted']} updated={c['updated']}")
    if missing_codes:
        print(f"\n  codes not found in DB ({len(missing_codes)}): {missing_codes[:20]}"
              + (" ..." if len(missing_codes) > 20 else ""))


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("--dry-run", action="store_true",
                        help="do everything, print the summary, then roll back")
    args = parser.parse_args()

    with get_sync_session() as session:
        run(session, args.dry_run)


if __name__ == "__main__":
    main()
