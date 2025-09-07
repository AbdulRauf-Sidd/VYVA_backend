from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, EmailStr
from enum import Enum

# Add LongTermConditionEnum
class LongTermConditionEnum(str, Enum):
    DIABETES = "Diabetes"
    HEART_DISEASE = "Heart Disease"
    HYPERTENSION = "Hypertension"
    HIGH_CHOLESTEROL = "High Cholesterol"
    STROKE = "Stroke"
    ARTHRITIS = "Arthritis"
    OSTEOPOROSIS = "Osteoporosis"
    RESPIRATORY_DISEASE = "Respiratory Disease"
    CANCER = "Cancer"
    KIDNEY_DISEASE = "Kidney Disease"
    LIVER_DISEASE = "Liver Disease"
    ALZHEIMERS = "Alzheimer's"
    DEMENTIA = "Dementia"
    PARKINSONS = "Parkinson's"
    ANXIETY = "Anxiety"
    DEPRESSION = "Depression"
    VISION_PROBLEMS = "Vision Problems"
    HEARING_LOSS = "Hearing Loss"
    CHRONIC_PAIN = "Chronic Pain"
    MOBILITY_IMPAIRMENT = "Mobility Impairment"
    OTHER = "Other"

# Updated LongTermCondition models
class LongTermConditionBase(BaseModel):
    name: LongTermConditionEnum

class LongTermConditionCreate(LongTermConditionBase):
    pass

class LongTermConditionRead(LongTermConditionBase):
    id: int
    user_id: int
    
    model_config = ConfigDict(from_attributes=True)

# ... rest of the schema remains the same (other enums, TopicOfInterest, Activity, User schemas, etc.)