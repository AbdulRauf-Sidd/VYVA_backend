"""
Script to insert brain coach questions from a JSON knowledge base into the database.

Usage:
    python add_questionsv2.py <json_file> [--session SESSION] [--tier TIER] [--batch-size BATCH_SIZE]

Example:
    python add_questionsv2.py kb/chess.json --session 1 --tier 1
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import logging

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from models.brain_coach import BrainCoachQuestions, QuestionTranslations
from core.database import engine_sync, SessionLocal
from sqlalchemy import select, inspect

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


# Difficulty to tier mapping
DIFFICULTY_TO_TIER = {
    "easy": 1,
    "medium": 2,
    "hard": 3,
    "advanced": 4,
}

# Language code mapping
LANGUAGE_MAP = {
    "en": "en",
    "es": "es",
    "de": "de",
    "fr": "fr",
}


def load_questions(json_file: str) -> Optional[List[Dict[str, Any]]]:
    """Load questions from JSON file."""
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            questions = json.load(f)
        logger.info(f"Loaded {len(questions)} questions from {json_file}")
        return questions
    except FileNotFoundError:
        logger.error(f"File not found: {json_file}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in file: {e}")
        return None
    except Exception as e:
        logger.error(f"Error loading questions: {e}")
        return None


def get_tier_for_question(question: Dict[str, Any], tier_level: Optional[int]) -> int:
    """Get tier level for a question."""
    if tier_level is not None:
        return tier_level
    
    # Try to get from difficulty field
    difficulty = question.get("difficulty", "").lower()
    tier = DIFFICULTY_TO_TIER.get(difficulty, 1)
    return tier


def validate_question(question: Dict[str, Any]) -> Tuple[bool, str]:
    """Validate question structure."""
    if not isinstance(question.get("translations"), list):
        return False, "Missing or invalid 'translations' field"
    
    if not question.get("translations"):
        return False, "Empty translations list"
    
    for trans in question["translations"]:
        if not trans.get("language"):
            return False, f"Missing 'language' in translation"
        if not trans.get("question"):
            return False, f"Missing 'question' in translation for language {trans.get('language')}"
        if not trans.get("answer"):
            return False, f"Missing 'answer' in translation for language {trans.get('language')}"
    
    return True, "Valid"


def check_existing_question(db, question: Dict[str, Any]) -> bool:
    """Check if question already exists by checking translations."""
    if "id" not in question:
        return False
    
    # Try to find any question with the same first translation text
    if question.get("id"):
        code = question["id"]
        stmt = select(BrainCoachQuestions).where(
            BrainCoachQuestions.code == code
        )
        result = db.execute(stmt)
        return result.scalar_one_or_none() is not None
    
    return False


def insert_questions(
    questions: List[Dict[str, Any]],
    session_num: int = 1,
    tier_level: Optional[int] = None,
    batch_size: int = 10
) -> Tuple[int, int, int]:
    """
    Insert questions into database.
    
    Returns:
        Tuple of (successful, failed, skipped) counts
    """
    successful_count = 0
    failed_count = 0
    skipped_count = 0
    
    with SessionLocal() as db:
        for i, question in enumerate(questions, 1):
            try:

                # Validate question
                is_valid, message = validate_question(question)
                if not is_valid:
                    logger.warning(f"Question {i} skipped - validation error: {message}")
                    skipped_count += 1
                    continue
                
                # Check if question already exists (avoid duplicates)
                if check_existing_question(db, question):
                    logger.info(f"Question {i} already exists (ID: {question.get('id')}), skipping")
                    skipped_count += 1
                    continue
                
                # Create base question object
                tier = get_tier_for_question(question, tier_level)
                base_question = BrainCoachQuestions(
                    session=session_num,
                    tier=tier,
                    difficulty=question.get('difficulty'),
                    type=question.get('type'),
                    code=question.get('id'),
                    max_score=1,
                    category=question.get("category", "general")
                )
                db.add(base_question)
                db.flush()
                
                # Create translations
                for trans in question["translations"]:
                    language = LANGUAGE_MAP.get(trans["language"], trans["language"])
                    
                    translation = QuestionTranslations(
                        question_id=base_question.id,
                        language=language,
                        question_text=trans["question"],
                        expected_answer=trans["answer"],
                        question_type=question.get("type"),
                        theme=question.get("category"),
                        scoring_logic=None
                    )
                    db.add(translation)
                
                # Commit after batch
                if i % batch_size == 0:
                    db.commit()
                    logger.info(f"Progress: {i}/{len(questions)} questions processed")
                
                successful_count += 1
                
            except Exception as e:
                db.rollback()
                logger.error(f"Error inserting question {i}: {str(e)}")
                failed_count += 1
        
        # Final commit for remaining questions
        db.commit()
    
    return successful_count, failed_count, skipped_count


def main():
    """Main function to run the importer."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Import brain coach questions from JSON file to database"
    )
    parser.add_argument(
        "json_file",
        help="Path to the JSON file containing questions"
    )
    parser.add_argument(
        "--session",
        type=int,
        default=1,
        help="Session number (default: 1)"
    )
    parser.add_argument(
        "--tier",
        type=int,
        default=None,
        help="Tier level (default: auto-detect from difficulty)"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=10,
        help="Batch size for commits (default: 10)"
    )
    
    args = parser.parse_args()
    
    # Load questions
    questions = load_questions(args.json_file)
    if questions is None:
        sys.exit(1)
    
    # Insert questions
    logger.info(f"Starting import with session={args.session}, tier={args.tier}")
    successful, failed, skipped = insert_questions(
        questions=questions,
        session_num=args.session,
        tier_level=args.tier,
        batch_size=args.batch_size
    )
    
    # Print summary
    print("\n" + "="*50)
    print("IMPORT SUMMARY")
    print("="*50)
    print(f"Total questions:  {len(questions)}")
    print(f"Successful:       {successful}")
    print(f"Failed:           {failed}")
    print(f"Skipped:          {skipped}")
    print("="*50)
    
    if failed == 0:
        logger.info("Import completed successfully!")
        sys.exit(0)
    else:
        logger.warning(f"Import completed with {failed} errors")
        sys.exit(1)


if __name__ == "__main__":
    main()
