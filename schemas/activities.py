from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, EmailStr
from enum import Enum

# Add TopicEnum
class TopicEnum(str, Enum):
    NEWS = "News"
    MUSIC = "Music"
    COOKING = "Cooking"
    SPORTS = "Sports"
    GARDENING = "Gardening"
    READING = "Reading"
    HISTORY = "History"
    TECH = "Tech"
    TRAVEL = "Travel"
    MOVIES = "Movies"
    ARTS = "Arts"
    PETS = "Pets"
    FAMILY = "Family"
    WELLNESS = "Wellness"
    OTHER = "Other"

# Add ActivityEnum
class ActivityEnum(str, Enum):
    MUSIC = "Music"
    BRAIN_GAMES = "Brain Games"
    STORYTELLING = "Storytelling"
    RELAXATION = "Relaxation"
    LEARNING = "Learning"
    RECIPES = "Recipes"
    EXERCISE = "Exercise"
    NEUTRAL_INSPIRATION = "Neutral Inspiration"
    FAITH_BASED_INSPIRATION = "Faith-based Inspiration"
    OTHER = "Other"

# Updated TopicOfInterest models
class TopicOfInterestBase(BaseModel):
    name: TopicEnum

class TopicOfInterestCreate(TopicOfInterestBase):
    pass

class TopicOfInterestRead(TopicOfInterestBase):
    id: int
    user_id: int
    
    model_config = ConfigDict(from_attributes=True)

# Updated Activity models
class ActivityBase(BaseModel):
    name: ActivityEnum

class ActivityCreate(ActivityBase):
    pass

class ActivityRead(ActivityBase):
    id: int
    user_id: int
    
    model_config = ConfigDict(from_attributes=True)

# ... rest of the schema remains the same (other enums, User schemas, etc.)