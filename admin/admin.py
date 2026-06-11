from sqladmin import Admin, ModelView
from core.database import engine
from models import User, Medication
from models.authentication import CaretakerSession, CaretakerTempToken
from models.organization import Organization, OrganizationAgents, TwilioWhatsappTemplates
from models.onboarding import OnboardingUser
from models.onboarding import OnboardingLogs
from models.symptom_checker import SymptomCheckerResponse
from models.user_check_ins import UserCheckin, ScheduledSession, CheckinLog
from admin.auth import AdminAuth
from core.config import settings
from models.medication import MedicationTime, MedicationLog
from models.user import Caretaker
from models.brain_coach import BrainCoachQuestions, BrainCoachResponses, QuestionTranslations
from models.prompt import Prompt
from models.eleven_labs_sessions import ElevenLabsSessions
from models.emergency_numbers import EmergencyNumber
from models.outbound_call_logs import OutboundCallLog
from models.doctor import Doctor

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

    class TwilioWhatsappTemplatesAdmin(ModelView, model=TwilioWhatsappTemplates):
        column_list = "__all__"

    class MedicationAdmin(ModelView, model=Medication):
        column_list = [
            Medication.id,
            Medication.user_id,
            Medication.name,
            Medication.dosage,
            Medication.start_date,
            Medication.end_date,
            Medication.purpose,
            Medication.is_active,
            Medication.created_at,
        ]

    class MedicationTimeAdmin(ModelView, model=MedicationTime):
        column_list = [
            MedicationTime.id,
            MedicationTime.medication_id,
            MedicationTime.time_of_day,
            MedicationTime.days_of_week,
            MedicationTime.created_at,
        ]

    class OrganizationAdmin(ModelView, model=Organization):
        column_list = "__all__"

    class OrganizationAgentsAdmin(ModelView, model=OrganizationAgents):
        column_list = "__all__"

    class OnboardingUserAdmin(ModelView, model=OnboardingUser):
        column_list = [
            OnboardingUser.id,
            OnboardingUser.first_name,
            OnboardingUser.last_name,
            OnboardingUser.phone_number,
            OnboardingUser.onboarding_status,
            OnboardingUser.created_at,
        ]

    class OnboardingLogsAdmin(ModelView, model=OnboardingLogs):
        column_list = "__all__"

    class SymptomCheckerResponseAdmin(ModelView, model=SymptomCheckerResponse):
        column_list = [
            SymptomCheckerResponse.id,
            SymptomCheckerResponse.user_id,
            SymptomCheckerResponse.conversation_id,
            SymptomCheckerResponse.symptoms,
            SymptomCheckerResponse.created_at,
        ]

    class BrainCoachQuestionsAdmin(ModelView, model=BrainCoachQuestions):
        column_list = "__all__"

    class QuestionTranslationsAdmin(ModelView, model=QuestionTranslations):
        column_list = "__all__"

    class BrainCoachResponsesAdmin(ModelView, model=BrainCoachResponses):
        column_list = "__all__"

    class CareTakerTempTokenAdmin(ModelView, model=CaretakerTempToken):
        column_list = "__all__"

    class CaretakerSessionAdmin(ModelView, model=CaretakerSession):
        column_list = "__all__"
        
    class MedicationLogAdmin(ModelView, model=MedicationLog):
        column_list = "__all__"

    class UserCheckinAdmin(ModelView, model=UserCheckin):
        column_list = [
            UserCheckin.id,
            UserCheckin.user_id,
            UserCheckin.check_in_type,
            UserCheckin.check_in_frequency_days,
            UserCheckin.check_in_time,
            UserCheckin.is_active,
            UserCheckin.created_at,
        ]

    class UserCheckinLogAdmin(ModelView, model=CheckinLog):
        column_list = "__all__"

    class ScheduledSessionAdmin(ModelView, model=ScheduledSession):
        column_list = "__all__"

    class PromptAdmin(ModelView, model=Prompt):
        column_list = [
            Prompt.id,
            Prompt.name,
            Prompt.prompt_type,
            Prompt.organization_id,
            Prompt.organization_agent_id,
            Prompt.agent_type,
            Prompt.model,
            Prompt.is_active,
            Prompt.updated_at,
        ]
        form_columns = "__all__"

    class ElevenLabsSessionsAdmin(ModelView, model=ElevenLabsSessions):
        column_list = [
            ElevenLabsSessions.id,
            ElevenLabsSessions.conversation_id,
            ElevenLabsSessions.user_id,
            ElevenLabsSessions.agent_type,
            ElevenLabsSessions.status,
            ElevenLabsSessions.duration,
            ElevenLabsSessions.cost,
            ElevenLabsSessions.call_successful,
            ElevenLabsSessions.created,
        ]
        form_columns = "__all__"

    class EmergencyNumberAdmin(ModelView, model=EmergencyNumber):
        column_list = [
            EmergencyNumber.id,
            EmergencyNumber.phone_number,
            EmergencyNumber.type,
            EmergencyNumber.organization_id,
            EmergencyNumber.created_at,
        ]
        form_columns = "__all__"

    class DoctorAdmin(ModelView, model=Doctor):
        column_list = [
            Doctor.id,
            Doctor.first_name,
            Doctor.last_name,
            Doctor.email,
            Doctor.phone,
            Doctor.organization_id,
            Doctor.user_id,
            Doctor.created_at,
        ]
        form_columns = "__all__"

    class OutboundCallLogAdmin(ModelView, model=OutboundCallLog):
        column_list = [
            OutboundCallLog.id,
            OutboundCallLog.agent_id,
            OutboundCallLog.phone_number,
            OutboundCallLog.success,
            OutboundCallLog.created_at,
        ]
        column_details_list = "__all__"
        can_create = False
        can_edit = False
        can_delete = False


    admin.add_view(UserAdmin)
    admin.add_view(CaretakerAdmin)
    admin.add_view(TwilioWhatsappTemplatesAdmin)
    admin.add_view(MedicationAdmin)
    admin.add_view(MedicationTimeAdmin)
    admin.add_view(MedicationLogAdmin)
    admin.add_view(OrganizationAdmin)
    admin.add_view(OrganizationAgentsAdmin)
    admin.add_view(OnboardingUserAdmin)
    admin.add_view(OnboardingLogsAdmin)
    admin.add_view(SymptomCheckerResponseAdmin)
    admin.add_view(BrainCoachQuestionsAdmin)
    admin.add_view(QuestionTranslationsAdmin)
    admin.add_view(BrainCoachResponsesAdmin)
    admin.add_view(CareTakerTempTokenAdmin)
    admin.add_view(CaretakerSessionAdmin)
    admin.add_view(UserCheckinAdmin)
    admin.add_view(UserCheckinLogAdmin)
    admin.add_view(ScheduledSessionAdmin)
    admin.add_view(PromptAdmin)
    admin.add_view(ElevenLabsSessionsAdmin)
    admin.add_view(EmergencyNumberAdmin)
    admin.add_view(OutboundCallLogAdmin)
    admin.add_view(DoctorAdmin)
