import uuid
from datetime import datetime, timezone

from sqladmin import BaseView, expose
from sqlalchemy import select
from starlette.requests import Request
from starlette.responses import RedirectResponse

from core.database import AsyncSessionLocal
from models.eleven_labs_sessions import ElevenLabsSessions
from models.manual_calls import ManualCall
from models.organization import Organization, OrganizationAgents, AgentTypeEnum
from models.user import User


async def _main_agent_id(db, organization_id):
    result = await db.execute(
        select(OrganizationAgents).where(
            OrganizationAgents.organization_id == organization_id,
            OrganizationAgents.agent_type == AgentTypeEnum.main_agent.value,
            OrganizationAgents.is_active.is_(True),
        )
    )
    agent = result.scalars().first()
    return agent.agent_id if agent else None


class ManualCallComposeView(BaseView):
    name = "Trigger Calls"
    icon = "fa-solid fa-phone-volume"

    async def _render(self, request: Request, org_id, errors=None, form=None):
        async with AsyncSessionLocal() as db:
            orgs = (await db.execute(select(Organization).order_by(Organization.name))).scalars().all()
            users = []
            if org_id:
                users = (await db.execute(
                    select(User)
                    .where(User.organization_id == org_id, User.phone_number.isnot(None))
                    .order_by(User.first_name, User.last_name)
                )).scalars().all()
        return await self.templates.TemplateResponse(request, "manual_calls_new.html", {
            "orgs": orgs, "users": users, "org_id": org_id, "errors": errors or [], "form": form or {},
        })

    @expose("/manual-calls/new", identity="manual-calls-new", methods=["GET"])
    async def compose(self, request: Request):
        org_id = request.query_params.get("organization_id")
        return await self._render(request, int(org_id) if org_id else None)

    @expose("/manual-calls/new", identity="manual-calls-create", methods=["POST"])
    async def create(self, request: Request):
        form = await request.form()
        org_id = int(form["organization_id"]) if form.get("organization_id") else None
        user_ids = [int(u) for u in form.getlist("user_ids")]
        first_message = (form.get("first_message") or "").strip() if form.get("use_first_message") else None
        prompt = (form.get("system_prompt") or "").strip() if form.get("use_prompt") else None
        raw = {
            "use_first_message": bool(form.get("use_first_message")),
            "use_prompt": bool(form.get("use_prompt")),
            "first_message": form.get("first_message") or "",
            "system_prompt": form.get("system_prompt") or "",
            "schedule_mode": form.get("schedule_mode") or "now",
            "scheduled_at": form.get("scheduled_at") or "",
            "user_ids": user_ids,
        }

        errors = []
        if not org_id:
            errors.append("Select an organization.")
        if not user_ids:
            errors.append("Select at least one user.")
        if form.get("use_first_message") and not first_message:
            errors.append("First message override is enabled but empty.")
        if form.get("use_prompt") and not prompt:
            errors.append("System prompt override is enabled but empty.")

        scheduled_at = datetime.now(timezone.utc)
        if raw["schedule_mode"] == "later":
            try:
                scheduled_at = datetime.fromisoformat(raw["scheduled_at"]).replace(tzinfo=timezone.utc)
            except ValueError:
                errors.append("Pick a valid schedule time (UTC).")

        if errors:
            return await self._render(request, org_id, errors, raw)

        async with AsyncSessionLocal() as db:
            agent_id = await _main_agent_id(db, org_id)
            if not agent_id:
                return await self._render(request, org_id, ["This organization has no active main_agent."], raw)

            users = (await db.execute(
                select(User).where(User.id.in_(user_ids), User.organization_id == org_id)
            )).scalars().all()
            batch_id = str(uuid.uuid4())
            for user in users:
                db.add(ManualCall(
                    batch_id=batch_id,
                    user_id=user.id,
                    organization_id=org_id,
                    agent_id=agent_id,
                    phone_number=user.phone_number,
                    override_first_message=first_message or None,
                    override_prompt=prompt or None,
                    scheduled_at=scheduled_at,
                    status="scheduled",
                ))
            await db.commit()

        return RedirectResponse(str(request.url_for("admin:manual-calls-status")) + f"?batch_id={batch_id}", status_code=303)


class ManualCallStatusView(BaseView):
    name = "Manual Call Status"
    icon = "fa-solid fa-list-check"

    @expose("/manual-calls/status", identity="manual-calls-status", methods=["GET"])
    async def status(self, request: Request):
        batch_id = request.query_params.get("batch_id")
        status_filter = request.query_params.get("status")
        async with AsyncSessionLocal() as db:
            stmt = (
                select(ManualCall, User, ElevenLabsSessions.status)
                .join(User, User.id == ManualCall.user_id)
                .outerjoin(ElevenLabsSessions, ElevenLabsSessions.call_sid == ManualCall.conversation_id)
                .order_by(ManualCall.scheduled_at.desc(), ManualCall.id.desc())
                .limit(300)
            )
            if batch_id:
                stmt = stmt.where(ManualCall.batch_id == batch_id)
            rows = (await db.execute(stmt)).all()

        calls = []
        for call, user, call_status in rows:
            # once placed, the live ElevenLabs outcome (ringing / answered / no_answer ...) is the status
            shown = call_status if call.status == "placed" and call_status else call.status
            if status_filter and shown != status_filter:
                continue
            calls.append({"call": call, "user": user, "status": shown})
        return await self.templates.TemplateResponse(request, "manual_calls_status.html", {
            "calls": calls, "batch_id": batch_id, "status_filter": status_filter,
        })

    @expose("/manual-calls/cancel", identity="manual-calls-cancel", methods=["POST"])
    async def cancel(self, request: Request):
        form = await request.form()
        async with AsyncSessionLocal() as db:
            call = await db.get(ManualCall, int(form["call_id"]))
            if call and call.status == "scheduled":
                call.status = "cancelled"
                await db.commit()
        return RedirectResponse(str(request.url_for("admin:manual-calls-status")), status_code=303)
