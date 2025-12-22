from sqladmin import Admin, ModelView
from core.database import engine
from models import User, Medication
from models.organization import Organization
from admin.auth import AdminAuth
from core.config import settings

def setup_admin(app):
    # admin = Admin(app, engine)
    admin = Admin(
        app,
        engine,
        authentication_backend=AdminAuth(
            secret_key=settings.SECRET_KEY
        ),
    )

    class UserAdmin(ModelView, model=User):
        column_list = [User.id, User.email, User.is_active]

    class MedicationAdmin(ModelView, model=Medication):
        column_list = "__all__"

    class OrganizationAdmin(ModelView, model=Organization):
        column_list = "__all__"

    # admin = Admin(
    #     app,
    #     engine,
    #     authentication_backend=AdminAuth(secret_key=settings.SECRET_KEY),
    # )

    admin.add_view(UserAdmin)
    admin.add_view(MedicationAdmin)
    admin.add_view(OrganizationAdmin)