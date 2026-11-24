import uuid
from datetime import datetime, timezone

from sqladmin import BaseView, expose
from sqlalchemy import select, or_
from starlette.requests import Request
from starlette.responses import RedirectResponse

from core.database import AsyncSessionLocal
from models.manual_whatsapp import ManualWhatsapp
from models.organization import Organization, TwilioWhatsappTemplates as Template
from models.user import User
from models.whatsapp_messages import WhatsappMessage
from services.meta_whatsapp_service import META_LANGUAGE_MAP

LANGUAGES = list(META_LANGUAGE_MAP.keys())


class ManualWhatsappView(BaseView):
    name = "Send WhatsApp"
    icon = "fa-brands fa-whatsapp"

    async def _render(self, request: Request, org_id, form=None, errors=None, results=None):
        async with AsyncSessionLocal() as db:
            orgs = (await db.execute(select(Organization).order_by(Organization.name))).scalars().all()
            users, templates = [], []
            if org_id:
                users = (await db.execute(
                    select(User)
                    .where(User.organization_id == org_id, User.phone_number.isnot(None))
                    .order_by(User.first_name, User.last_name)
                )).scalars().all()
                templates = (await db.execute(
                    select(Template)
                    .where(Template.is_active.is_(True), or_(Template.organization_id == org_id, Template.organization_id.is_(None)))
                    .order_by(Template.template_id, Template.language)
                )).scalars().all()
        return await self.templates.TemplateResponse(request, "manual_whatsapp.html", {
            "orgs": orgs, "users": users, "templates": templates, "org_id": org_id,
            "languages": LANGUAGES, "form": form or {}, "errors": errors or [], "results": results,
        })

    @expose("/manual-whatsapp", identity="manual-whatsapp", methods=["GET"])
    async def compose(self, request: Request):
        org_id = request.query_params.get("organization_id")
        return await self._render(request, int(org_id) if org_id else None)

    @expose("/manual-whatsapp", identity="manual-whatsapp-send", methods=["POST"])
    async def send(self, request: Request):
        form = await request.form()
        org_id = int(form["organization_id"]) if form.get("organization_id") else None
        user_ids = [int(u) for u in form.getlist("user_ids")]
        use_vars = bool(form.get("use_variables"))
        keys, values = form.getlist("var_key"), form.getlist("var_value")
        variables = {}
        if use_vars:
            for k, v in zip(keys, values):
                if k.strip():
                    variables[k.strip()] = v
        raw = {
            "user_ids": user_ids, "template_row": form.get("template_row"), "manual_template": bool(form.get("manual_template")),
            "template_name": (form.get("template_name") or "").strip(), "language": form.get("language") or "",
            "use_variables": use_vars, "variables": list(zip(keys, values)) if use_vars else [],
            "schedule_mode": form.get("schedule_mode") or "now", "scheduled_at": form.get("scheduled_at") or "",
        }

        errors = []
        if not org_id:
            errors.append("Select an organization.")
        if not user_ids:
            errors.append("Select at least one user.")
        if raw["manual_template"]:
            if not raw["template_name"]:
                errors.append("Enter the template name.")
            elif " " in raw["template_name"]:
                errors.append("Template name must be the Meta template name (no spaces).")
        elif not form.get("template_row"):
            errors.append("Select a template.")
        for k in variables:
            if not k.isdigit() or int(k) < 1:
                errors.append(f"Variable key '{k}' must be a position number (1, 2, 3...).")

        scheduled_at = datetime.now(timezone.utc)
        if raw["schedule_mode"] == "later":
            try:
                scheduled_at = datetime.fromisoformat(raw["scheduled_at"]).replace(tzinfo=timezone.utc)
            except ValueError:
                errors.append("Pick a valid schedule time (UTC).")
        if errors:
            return await self._render(request, org_id, raw, errors)

        async with AsyncSessionLocal() as db:
            template = None if raw["manual_template"] else await db.get(Template, int(form["template_row"]))
            users = (await db.execute(
                select(User).where(User.id.in_(user_ids), User.organization_id == org_id)
            )).scalars().all()
            batch_id = str(uuid.uuid4())
            for user in users:
                db.add(ManualWhatsapp(
                    batch_id=batch_id,
                    user_id=user.id,
                    organization_id=org_id,
                    template_name=raw["template_name"] if raw["manual_template"] else template.template_id,
                    language=form.get("language") or (template.language if template else "english"),
                    variables=variables or None,
                    scheduled_at=scheduled_at,
                    status="scheduled",
                ))
            await db.commit()

        return RedirectResponse(str(request.url_for("admin:manual-whatsapp-status")) + f"?batch_id={batch_id}", status_code=303)


class ManualWhatsappStatusView(BaseView):
    name = "WhatsApp Send Status"
    icon = "fa-solid fa-list-check"

    @expose("/manual-whatsapp/status", identity="manual-whatsapp-status", methods=["GET"])
    async def status(self, request: Request):
        batch_id = request.query_params.get("batch_id")
        status_filter = request.query_params.get("status")
        async with AsyncSessionLocal() as db:
            stmt = (
                select(ManualWhatsapp, User, WhatsappMessage.status)
                .join(User, User.id == ManualWhatsapp.user_id)
                .outerjoin(WhatsappMessage, WhatsappMessage.wa_message_id == ManualWhatsapp.wa_message_id)
                .order_by(ManualWhatsapp.scheduled_at.desc(), ManualWhatsapp.id.desc())
                .limit(300)
            )
            if batch_id:
                stmt = stmt.where(ManualWhatsapp.batch_id == batch_id)
            rows = (await db.execute(stmt)).all()

        items = []
        for item, user, delivery in rows:
            # once sent, the delivery status from Meta (sent / delivered / read / failed) is the status
            shown = delivery if item.status == "sent" and delivery else item.status
            if status_filter and shown != status_filter:
                continue
            items.append({"item": item, "user": user, "status": shown})
        return await self.templates.TemplateResponse(request, "manual_whatsapp_status.html", {
            "items": items, "batch_id": batch_id, "status_filter": status_filter,
        })

    @expose("/manual-whatsapp/cancel", identity="manual-whatsapp-cancel", methods=["POST"])
    async def cancel(self, request: Request):
        form = await request.form()
        async with AsyncSessionLocal() as db:
            item = await db.get(ManualWhatsapp, int(form["item_id"]))
            if item and item.status == "scheduled":
                item.status = "cancelled"
                await db.commit()
        return RedirectResponse(str(request.url_for("admin:manual-whatsapp-status")), status_code=303)
