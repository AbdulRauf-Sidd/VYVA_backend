"""
BrainCoach model for brain training and cognitive exercises.
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Float, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from core.database import Base


class BrainCoachQuestions(Base):
    """Model for storing brain coach questions and their metadata."""

    __tablename__ = "brain_coach_questions"

    id = Column(Integer, primary_key=True, index=True)
    session = Column(Integer, nullable=False)  # Session number or identifier
    tier = Column(Integer, nullable=False)  # Difficulty or complexity tier
    question_type = Column(String(100), nullable=False)  # Type of question (e.g., "Memory", "Math", "Logic")
    question = Column(Text, nullable=False)  # The question text
    expected_answer = Column(Text, nullable=False)  # Expected answer or solution
    scoring_logic = Column(Text, nullable=True)  # Logic or criteria for scoring
    theme = Column(String(100), nullable=True)  # Theme or category of the question




class BrainCoachResponses(Base):
    """Model for storing user responses to brain coach questions."""

    __tablename__ = "brain_coach_responses"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)  # Foreign key to User
    question_id = Column(Integer, ForeignKey("brain_coach_questions.id"), nullable=False)  # Foreign key to BrainCoachQuestions
    user_answer = Column(String, nullable=False)  # User's answer to the question
    score = Column(Integer, nullable=False)  # Score achieved for the answer
    created = Column(DateTime(timezone=True), server_default=func.now())  # Timestamp of the response



# class BrainCoach(Base):
#     """BrainCoach model for brain training and cognitive exercises."""
    
#     __tablename__ = "brain_coach"
    
#     id = Column(Integer, primary_key=True, index=True)
    # user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # # Session Information
    # session_type = Column(String(100), nullable=False)  # memory, attention, problem_solving, etc.
    # difficulty_level = Column(String(50), nullable=False)  # easy, medium, hard
    # duration_minutes = Column(Integer, nullable=True)
    
    # # Performance Metrics
    # score = Column(Float, nullable=True)
    # accuracy_percentage = Column(Float, nullable=True)
    # response_time_avg = Column(Float, nullable=True)  # in seconds
    # questions_answered = Column(Integer, nullable=True)
    # questions_correct = Column(Integer, nullable=True)
    
    # # Session Details
    # exercises_completed = Column(Text, nullable=True)  # JSON array of exercise details
    # notes = Column(Text, nullable=True)
    
    # # Progress Tracking
    # is_completed = Column(Boolean, default=False)
    # completion_time = Column(DateTime, nullable=True)
    
    # # Timestamps
    # started_at = Column(DateTime(timezone=True), server_default=func.now())
    # completed_at = Column(DateTime, nullable=True)
    # created_at = Column(DateTime(timezone=True), server_default=func.now())
    # updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # # Relationships
    # user = relationship("User", back_populates="brain_coach_sessions")
    
    # def __repr__(self):
    #     return f"<BrainCoach(id={self.id}, session_type='{self.session_type}', user_id={self.user_id})>" 