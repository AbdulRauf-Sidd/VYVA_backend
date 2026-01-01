"""
Interactive Python shell for testing functions and code within the environment.

Usage:
    python shell.py
    
This loads the FastAPI app, database session, and common utilities into an interactive shell.
"""

import asyncio
import code
from main import app
from core.database import AsyncSessionLocal, get_db
from core.config import settings

# Import common models
from models.user import User
from models.medication import Medication
from models.symptom_checker import SymptomCheckerResponse

# Import repositories
from repositories.user import UserRepository
from repositories.medication import MedicationRepository
from repositories.symptom_checker import SymptomCheckerRepository

# Import services
from services.email_service import email_service
from services.ai_assistant_service import ai_assistant_service

# Import schemas
from schemas.user import UserCreate, UserUpdate
from schemas.medication import MedicationCreate, MedicationUpdate
from schemas.brain_coach import BrainCoachQuestionCreate, BrainCoachResponseCreate

# Helper function for async operations in the shell
async def async_call(coro):
    """Helper to run async functions in the shell."""
    return await coro

# Shortcuts for common operations
async def get_user(user_id: int):
    """Get a user by ID."""
    session = AsyncSessionLocal()
    try:
        repo = UserRepository(session)
        return await repo.get(user_id)
    finally:
        await session.close()

async def get_user_by_email(email: str):
    """Get a user by email."""
    session = AsyncSessionLocal()
    try:
        repo = UserRepository(session)
        return await repo.get_by_email(email)
    finally:
        await session.close()

async def get_user_medications(user_id: int):
    """Get all medications for a user."""
    session = AsyncSessionLocal()
    try:
        repo = MedicationRepository(session)
        return await repo.get_user_medications(user_id)
    finally:
        await session.close()

def main():
    """Start the interactive shell."""
    local_vars = {
        # App and config
        "app": app,
        "settings": settings,
        "AsyncSessionLocal": AsyncSessionLocal,
        
        # Database
        "get_db": get_db,
        
        # Models
        "User": User,
        "Medication": Medication,
        "SymptomCheckerResponse": SymptomCheckerResponse,
        
        # Repositories
        "UserRepository": UserRepository,
        "MedicationRepository": MedicationRepository,
        "SymptomCheckerRepository": SymptomCheckerRepository,
        
        # Services
        "email_service": email_service,
        "ai_assistant_service": ai_assistant_service,
        
        # Schemas
        "UserCreate": UserCreate,
        "UserUpdate": UserUpdate,
        "MedicationCreate": MedicationCreate,
        "MedicationUpdate": MedicationUpdate,
        
        # Helper functions
        "async_call": async_call,
        "get_user": get_user,
        "get_user_by_email": get_user_by_email,
        "get_user_medications": get_user_medications,
        "asyncio": asyncio,
    }
    
    banner = """
╔════════════════════════════════════════════════════════════════╗
║         Vyva Backend Interactive Shell                         ║
║                                                                ║
║  Usage Examples:                                               ║
║  ──────────────────────────────────────────────────────────   ║
║  • await get_user(1)                                           ║
║  • await get_user_medications(1)                               ║
║  • session = AsyncSessionLocal()                               ║
║  • repo = UserRepository(session)                              ║
║  • await repo.list()                                           ║
║  • asyncio.run(get_user(1))    # from outside async context   ║
║                                                                ║
║  Available: app, settings, User, Medication, repositories...  ║
╚════════════════════════════════════════════════════════════════╝
"""
    
    code.interact(banner=banner, local=local_vars, exitmsg="Goodbye!")

if __name__ == "__main__":
    main()
