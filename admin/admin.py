from sqladmin import Admin, ModelView
from core.database import engine
from models import User, Medication
from models.organization import Organization, OrganizationAgents
from models.onboarding import OnboardingUser
from models.onboarding import OnboardingLogs
from models.symptom_checker import SymptomCheckerResponse
from admin.auth import AdminAuth
from core.config import settings
from models.medication import MedicationTime
from models.user import Caretaker
from models.brain_coach import BrainCoachQuestions, BrainCoachResponses, QuestionTranslations

def setup_admin(app):
    admin = Admin(
        app,
        engine,
        authentication_backend=AdminAuth(
            secret_key=settings.SECRET_KEY
        ),
    )

    class UserAdmin(ModelView, model=User):
        column_list = [User.id, User.email, User.is_active]

    class CaretakerAdmin(ModelView, model=Caretaker):
        column_list = [Caretaker.id, Caretaker.name, Caretaker.phone_number]

    class MedicationAdmin(ModelView, model=Medication):
        column_list = "__all__"

    class MedicationTimeAdmin(ModelView, model=MedicationTime):
        column_list = "__all__" 

    class OrganizationAdmin(ModelView, model=Organization):
        column_list = "__all__"

    class OrganizationAgentsAdmin(ModelView, model=OrganizationAgents):
        column_list = "__all__"

    class OnboardingUserAdmin(ModelView, model=OnboardingUser):
        column_list = "__all__"

    class OnboardingLogsAdmin(ModelView, model=OnboardingLogs):
        column_list = "__all__"

    class SymptomCheckerResponseAdmin(ModelView, model=SymptomCheckerResponse):
        column_list = "__all__"

    class SymptomCheckerResponseAdmin(ModelView, model=SymptomCheckerResponse):
        column_list = "__all__"

    class BrainCoachQuestionsAdmin(ModelView, model=BrainCoachQuestions):
        column_list = "__all__"

    class QuestionTranslationsAdmin(ModelView, model=QuestionTranslations):
        column_list = "__all__"

    class BrainCoachResponsesAdmin(ModelView, model=BrainCoachResponses):
        column_list = "__all__"

    

    admin.add_view(UserAdmin)
    admin.add_view(CaretakerAdmin)
    admin.add_view(MedicationAdmin)
    admin.add_view(MedicationTimeAdmin)
    admin.add_view(OrganizationAdmin)
    admin.add_view(OrganizationAgentsAdmin)
    admin.add_view(OnboardingUserAdmin)
    admin.add_view(OnboardingLogsAdmin)
    admin.add_view(SymptomCheckerResponseAdmin)
    admin.add_view(BrainCoachQuestionsAdmin)
    admin.add_view(QuestionTranslationsAdmin)
    admin.add_view(BrainCoachResponsesAdmin)