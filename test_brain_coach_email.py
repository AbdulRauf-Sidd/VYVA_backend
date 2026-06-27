"""
Quick test for send_brain_coach_report email template.

Usage:
    python test_brain_coach_email.py <recipient_email> [language]

    language: en (default) | es | de

Example:
    python test_brain_coach_email.py you@example.com en
    python test_brain_coach_email.py you@example.com es
    python test_brain_coach_email.py you@example.com de
"""

import asyncio
import sys

from services.email_service import EmailService

SAMPLE_REPORT = [
    {
        "question_text": "Recall the 5 words presented at the start of the session",
        "question_type": "Memory",
        "theme": "Episodic Recall",
        "score": 4,
        "max_score": 5,
        "tier": 2,
        "session": 1,
    },
    {
        "question_text": "Follow the alternating number-letter trail (1-A-2-B…)",
        "question_type": "Attention",
        "theme": "Trail Making",
        "score": 8,
        "max_score": 10,
        "tier": 2,
        "session": 1,
    },
    {
        "question_text": "Name as many animals as possible in 60 seconds",
        "question_type": "Language",
        "theme": "Verbal Fluency",
        "score": 7,
        "max_score": 10,
        "tier": 2,
        "session": 1,
    },
    {
        "question_text": "Sort the coloured cards by rule (colour → shape → size)",
        "question_type": "Executive Function",
        "theme": "Set Shifting",
        "score": 6,
        "max_score": 10,
        "tier": 2,
        "session": 1,
    },
    {
        "question_text": "Copy the geometric figure and redraw it from memory",
        "question_type": "Visual-Spatial",
        "theme": "Rey Figure",
        "score": 9,
        "max_score": 10,
        "tier": 2,
        "session": 1,
    },
]

SAMPLE_SUGGESTIONS = (
    "Good progress today! Your attention and visual-spatial scores are strong. "
    "Focus on memory recall exercises tomorrow — try the 5-word delayed recall drill "
    "and spaced repetition flashcards. Executive function showed slight hesitation; "
    "a daily card-sorting game can help reinforce rule-switching skills."
)


async def main(recipient: str, language: str) -> None:
    service = EmailService()
    print(f"Sending test brain-coach report to {recipient!r} (lang={language!r}) …")
    await service.send_brain_coach_report(
        recipient_email=recipient,
        report_content=SAMPLE_REPORT,
        name="Jane Doe",
        suggestions=SAMPLE_SUGGESTIONS,
        performance_tier="Moderate",
        language=language,
    )
    print("Done — check your inbox.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    email = sys.argv[1]
    lang = sys.argv[2] if len(sys.argv) > 2 else "en"
    asyncio.run(main(email, lang))
