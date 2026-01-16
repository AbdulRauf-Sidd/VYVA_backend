"""
BrainCoach model for brain training and cognitive exercises.
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Float, Boolean, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from core.database import Base


class BrainCoachQuestions(Base):
    __tablename__ = "brain_coach_questions"

    id = Column(Integer, primary_key=True, index=True)
    session = Column(Integer, nullable=False)
    tier = Column(Integer, nullable=False)
    max_score = Column(Integer, nullable=True, default=1)
    category = Column(String(100), nullable=True)

class QuestionTranslations(Base):
    __tablename__ = "question_translations"

    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(Integer, ForeignKey('brain_coach_questions.id'), nullable=False)
    language = Column(String(30), nullable=False)  # 'en', 'es', 'fr', etc.
    question_text = Column(Text, nullable=False)
    expected_answer = Column(Text, nullable=False)
    scoring_logic = Column(Text, nullable=True)
    question_type = Column(String(100), nullable=False)
    theme = Column(String(100), nullable=True)
    
    # Composite unique constraint
    __table_args__ = (UniqueConstraint('question_id', 'language', name='uq_question_language'),)




class BrainCoachResponses(Base):
    """Model for storing user responses to brain coach questions."""

    __tablename__ = "brain_coach_responses"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(36), nullable=False) 
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    question_id = Column(Integer, ForeignKey("brain_coach_questions.id"), nullable=False) 
    user_answer = Column(String(100), nullable=True)
    score = Column(Integer, nullable=False)  
    created = Column(DateTime(timezone=True), server_default=func.now())