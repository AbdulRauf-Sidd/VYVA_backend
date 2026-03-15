import json
from sqlalchemy import select
from core.database import get_sync_session
from models.brain_coach import BrainCoachQuestions, QuestionTranslations

COGNITIVE_JSON_FILE="scripts/brain_coach/german_cognitive_translations.json"
TRIVIA_JSON_FILE="scripts/brain_coach/trivia_questions_german.json"

def add_german_translations_cognitive(json_file):
    with get_sync_session() as session:
        # Load JSON
        with open(json_file, "r", encoding="utf-8") as f:
            german_data = json.load(f)

        # Fetch all questions ordered by ID
        result = session.execute(
            select(BrainCoachQuestions).where(BrainCoachQuestions.category == "cognitive_assessment").order_by(BrainCoachQuestions.id)
        )

        questions = result.scalars().all()

        if len(german_data) != len(questions):
            print("WARNING: JSON count does not match DB questions")
            print(f"JSON: {len(german_data)}, DB: {len(questions)}")

        for question, german_entry in zip(questions, german_data):

            translation = german_entry["translations"][0]

            new_translation = QuestionTranslations(
                question_id=question.id,
                language=translation["language"],
                question_text=translation["question_text"],
                expected_answer=translation["expected_answer"],
                question_type=translation["question_type"],
                theme=translation.get("theme"),
                scoring_logic=translation.get("scoring_logic"),
            )

            session.add(new_translation)

        session.commit()

        print("German translations inserted successfully.")


def add_german_translations_trivia(json_file):
    with get_sync_session() as session:
        # Load JSON
        with open(json_file, "r", encoding="utf-8") as f:
            german_data = json.load(f)

        # Fetch all questions ordered by ID
        result = session.execute(
            select(BrainCoachQuestions).where(BrainCoachQuestions.category == "trivia").order_by(BrainCoachQuestions.id)
        )

        questions = result.scalars().all()

        if len(german_data) != len(questions):
            print("WARNING: JSON count does not match DB questions")
            print(f"JSON: {len(german_data)}, DB: {len(questions)}")

        for question, german_entry in zip(questions, german_data):

            translation = german_entry["translations"][0]

            new_translation = QuestionTranslations(
                question_id=question.id,
                language=translation["language"],
                question_text=translation["question_text"],
                expected_answer=translation["expected_answer"],
                question_type=translation["question_type"],
                theme=translation.get("theme"),
                scoring_logic=translation.get("scoring_logic"),
            )

            session.add(new_translation)

        session.commit()

        print("German translations inserted successfully.")