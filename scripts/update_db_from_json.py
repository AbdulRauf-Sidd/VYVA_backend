"""
Update vyva_db (connection from core.database / .env DATABASE_URL) from the JSON question files in this folder.

Matching: JSON "id" == brain_coach_questions.code

For every JSON entry:
  - brain_coach_questions: set type and difficulty (only if the JSON value is non-empty)
  - question_translations: upsert per (question_id, language). Missing translations
    (e.g. missing "en") are inserted, existing ones are updated. Empty/blank JSON
    values never overwrite data that is already in the database.

JSON entries whose code does not exist in brain_coach_questions are skipped and
reported (session/tier are NOT NULL, so new questions can't be created from JSON alone).

Questions are UPDATE-only (never created). Translations are created or updated.
Everything runs in one transaction. To preview without saving, use dry_run_update.py.

Usage:
    .venv/bin/python scripts/update_db_from_json.py
"""

import json
import sys
from pathlib import Path

from sqlalchemy import text

# make `core` importable when running as `python scripts/update_db_from_json.py`
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database import get_sync_session  # noqa: E402

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


def main(dry_run=False):
    with get_sync_session() as session:
        _run(session, dry_run)


def _run(session, dry_run):
    code_to_id = dict(
        session.execute(
            text("SELECT code, id FROM brain_coach_questions WHERE code IS NOT NULL")
        ).all()
    )

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
            path = JSON_DIR / filename
            entries = json.loads(path.read_text(encoding="utf-8"))
            print(f"{filename}: {len(entries)} entries")

            for entry in entries:
                stats["questions_seen"] += 1
                code = entry["id"]
                question_id = code_to_id.get(code)
                if question_id is None:
                    missing_codes.append(code)
                    continue

                result = session.execute(
                    text(
                        """
                        UPDATE brain_coach_questions
                           SET difficulty = COALESCE(:difficulty, difficulty),
                               type       = COALESCE(:type, type)
                         WHERE id = :id
                        """
                    ),
                    {
                        "difficulty": clean(entry.get("difficulty")),
                        "type": clean(entry.get("type")),
                        "id": question_id,
                    },
                )
                stats["questions_updated"] += result.rowcount

                for t in entry.get("translations", []):
                    language = clean(t.get("language"))
                    question_text = clean(t.get("question"))
                    expected_answer = clean(t.get("answer"))
                    question_type = clean(t.get("question_type"))
                    if not (language and question_text and expected_answer and question_type):
                        print(f"  skipped incomplete translation: {code} [{language}]")
                        continue

                    # xmax = 0 only for freshly inserted rows
                    was_inserted = session.execute(
                        text(
                            """
                            INSERT INTO question_translations
                                (question_id, language, question_text, expected_answer,
                                 scoring_logic, question_type, theme)
                            VALUES (:question_id, :language, :question_text, :expected_answer,
                                    :scoring_logic, :question_type, :theme)
                            ON CONFLICT ON CONSTRAINT uq_question_language DO UPDATE SET
                                question_text   = EXCLUDED.question_text,
                                expected_answer = EXCLUDED.expected_answer,
                                question_type   = EXCLUDED.question_type,
                                scoring_logic   = COALESCE(EXCLUDED.scoring_logic,
                                                           NULLIF(question_translations.scoring_logic, '')),
                                theme           = COALESCE(EXCLUDED.theme,
                                                           NULLIF(question_translations.theme, ''))
                            RETURNING (xmax = 0) AS inserted
                            """
                        ),
                        {
                            "question_id": question_id,
                            "language": language,
                            "question_text": question_text,
                            "expected_answer": expected_answer,
                            "scoring_logic": clean(t.get("scoring_logic")),
                            "question_type": question_type,
                            "theme": clean(t.get("theme")),
                        },
                    ).scalar_one()
                    action = "inserted" if was_inserted else "updated"
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


if __name__ == "__main__":
    main()
