from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy.orm import Session, joinedload
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timedelta, timezone
import logging

from app.database import get_db
from app.models.auth import User, RoleEnum
from app.models.visits import Visit, VisitStatus
from app.models.appointments import Appointment, AppointmentType
from app.api.dependencies import get_current_user
from app.schemas import AppointmentRead

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/calendar", tags=["calendar"])

APPOINTMENT_TYPE_LABELS = {
    "VISIT": "Visita",
    "CALL": "Llamada",
    "MEETING": "Reunión",
    "OTHER": "Otro",
}


# ==========================================
# SCHEMAS
# ==========================================

class AppointmentCreate(BaseModel):
    title: str
    appointment_type: AppointmentType = AppointmentType.MEETING
    agent_id: Optional[str] = None
    start_at: str
    end_at: str
    description: Optional[str] = None
    location: Optional[str] = None
    all_day: bool = False


class AppointmentUpdate(BaseModel):
    title: Optional[str] = None
    appointment_type: Optional[AppointmentType] = None
    agent_id: Optional[str] = None
    start_at: Optional[str] = None
    end_at: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None
    all_day: Optional[bool] = None


# ==========================================
# HELPERS
# ==========================================

def _appointment_options():
    return [joinedload(Appointment.agent), joinedload(Appointment.created_by)]


def _visit_options_calendar():
    return [joinedload(Visit.property), joinedload(Visit.agent), joinedload(Visit.client)]


def _get_conflicts(
    db: Session,
    agent_id: str,
    tenant_id,
    start_at: datetime,
    end_at: datetime,
    exclude_appointment_id: Optional[str] = None,
) -> List[dict]:
    conflicts = []

    visits = (
        db.query(Visit)
        .options(joinedload(Visit.property))
        .filter(
            Visit.tenant_id == tenant_id,
            Visit.agent_id == agent_id,
            Visit.status == VisitStatus.SCHEDULED,
            Visit.scheduled_at < end_at,
        )
        .all()
    )
    for v in visits:
        v_end = v.scheduled_at + timedelta(minutes=v.duration_minutes or 30)
        if v.scheduled_at < end_at and v_end > start_at:
            conflicts.append({
                "type": "VISIT",
                "id": str(v.id),
                "title": f"Visita: {v.property.title if v.property else 'Propiedad'}",
                "start": v.scheduled_at.isoformat(),
            })

    appt_q = db.query(Appointment).filter(
        Appointment.tenant_id == tenant_id,
        Appointment.agent_id == agent_id,
        Appointment.start_at < end_at,
        Appointment.end_at > start_at,
    )
    if exclude_appointment_id:
        appt_q = appt_q.filter(Appointment.id != exclude_appointment_id)
    for a in appt_q.all():
        conflicts.append({
            "type": "APPOINTMENT",
            "id": str(a.id),
            "title": a.title,
            "start": a.start_at.isoformat(),
        })

    return conflicts


def _format_ical_dt(dt: datetime) -> str:
    utc = dt.astimezone(timezone.utc)
    return utc.strftime("%Y%m%dT%H%M%SZ")


def _escape_ical(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def _fold(line: str) -> str:
    if len(line.encode("utf-8")) <= 75:
        return line
    result = []
    buf = line
    while len(buf.encode("utf-8")) > 75:
        result.append(buf[:75])
        buf = " " + buf[75:]
    result.append(buf)
    return "\r\n".join(result)


def _build_ical(events: list) -> str:
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//RealtyApp//Agenda//ES",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]
    for e in events:
        try:
            start_dt = datetime.fromisoformat(e["start"])
            end_dt = datetime.fromisoformat(e["end"])
        except (ValueError, KeyError):
            continue
        uid = f"{e['id']}@realtyapp"
        lines += [
            "BEGIN:VEVENT",
            _fold(f"UID:{uid}"),
            _fold(f"DTSTART:{_format_ical_dt(start_dt)}"),
            _fold(f"DTEND:{_format_ical_dt(end_dt)}"),
            _fold(f"SUMMARY:{_escape_ical(e.get('title', ''))}"),
        ]
        desc = e.get("description") or ""
        agent = e.get("agent_name") or ""
        if agent:
            desc = f"Agente: {agent}\n{desc}".strip()
        if desc:
            lines.append(_fold(f"DESCRIPTION:{_escape_ical(desc)}"))
        if e.get("location"):
            lines.append(_fold(f"LOCATION:{_escape_ical(e['location'])}"))
        lines.append("STATUS:CONFIRMED")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


# ==========================================
# ENDPOINTS
# ==========================================

@router.get("/agents")
def get_calendar_agents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return agents relevant to the calendar (all for managers, self for agents)."""
    if not current_user.tenant_id:
        raise HTTPException(status_code=400, detail="User does not belong to a tenant")

    if current_user.role == RoleEnum.AGENT:
        return {
            "agents": [{
                "id": str(current_user.id),
                "full_name": current_user.full_name,
                "role": current_user.role.value,
            }]
        }

    users = (
        db.query(User)
        .filter(
            User.tenant_id == current_user.tenant_id,
            User.is_active == True,
            User.role.in_([RoleEnum.AGENT, RoleEnum.MANAGER, RoleEnum.ADMIN]),
        )
        .order_by(User.full_name)
        .all()
    )
    return {
        "agents": [
            {"id": str(u.id), "full_name": u.full_name, "role": u.role.value}
            for u in users
        ]
    }


@router.get("/events")
def get_calendar_events(
    start: str = Query(..., description="ISO datetime range start"),
    end: str = Query(..., description="ISO datetime range end"),
    agent_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return unified calendar events (visits + appointments) in the date range."""
    if not current_user.tenant_id:
        raise HTTPException(status_code=400, detail="User does not belong to a tenant")

    try:
        start_dt = datetime.fromisoformat(start)
        end_dt = datetime.fromisoformat(end)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format")

    tid = current_user.tenant_id
    events = []

    # --- Visits ---
    visit_q = (
        db.query(Visit)
        .options(*_visit_options_calendar())
        .filter(
            Visit.tenant_id == tid,
            Visit.scheduled_at >= start_dt,
            Visit.scheduled_at < end_dt,
        )
    )
    if current_user.role == RoleEnum.AGENT:
        visit_q = visit_q.filter(Visit.agent_id == current_user.id)
    elif agent_id:
        visit_q = visit_q.filter(Visit.agent_id == agent_id)

    for v in visit_q.all():
        v_end = v.scheduled_at + timedelta(minutes=v.duration_minutes or 30)
        prop_title = v.property.title if v.property else "Propiedad"
        events.append({
            "id": str(v.id),
            "type": "VISIT",
            "title": f"Visita: {prop_title}",
            "start": v.scheduled_at.isoformat(),
            "end": v_end.isoformat(),
            "all_day": False,
            "agent_id": str(v.agent_id) if v.agent_id else None,
            "agent_name": v.agent.full_name if v.agent else None,
            "description": v.notes,
            "location": v.property.address if v.property else None,
            "appointment_type": None,
            "visit_status": v.status.value if v.status else None,
            "visit_id": str(v.id),
            "property_title": prop_title,
            "property_id": str(v.property_id) if v.property_id else None,
            "client_name": (
                f"{v.client.first_name} {v.client.last_name}" if v.client else None
            ),
            "client_id": str(v.client_id) if v.client_id else None,
            "rating": v.rating,
            "feedback": v.feedback,
        })

    # --- Appointments ---
    appt_q = (
        db.query(Appointment)
        .options(*_appointment_options())
        .filter(
            Appointment.tenant_id == tid,
            Appointment.start_at < end_dt,
            Appointment.end_at > start_dt,
        )
    )
    if current_user.role == RoleEnum.AGENT:
        appt_q = appt_q.filter(Appointment.agent_id == current_user.id)
    elif agent_id:
        appt_q = appt_q.filter(Appointment.agent_id == agent_id)

    for a in appt_q.all():
        events.append({
            "id": str(a.id),
            "type": "APPOINTMENT",
            "title": a.title,
            "start": a.start_at.isoformat(),
            "end": a.end_at.isoformat(),
            "all_day": a.all_day,
            "agent_id": str(a.agent_id) if a.agent_id else None,
            "agent_name": a.agent.full_name if a.agent else None,
            "description": a.description,
            "location": a.location,
            "appointment_type": a.appointment_type.value if a.appointment_type else None,
            "visit_status": None,
            "visit_id": None,
            "property_title": None,
            "property_id": None,
            "client_name": None,
            "client_id": None,
            "rating": None,
            "feedback": None,
        })

    return {"events": events}


@router.get("/export/ical")
def export_ical(
    start: str = Query(...),
    end: str = Query(...),
    agent_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Download events as an iCal (.ics) file."""
    result = get_calendar_events(start=start, end=end, agent_id=agent_id, db=db, current_user=current_user)
    ical_content = _build_ical(result["events"])
    return Response(
        content=ical_content.encode("utf-8"),
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="agenda.ics"'},
    )


@router.post("/appointments", status_code=status.HTTP_201_CREATED)
def create_appointment(
    data: AppointmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.tenant_id:
        raise HTTPException(status_code=400, detail="User does not belong to a tenant")

    try:
        start_dt = datetime.fromisoformat(data.start_at)
        end_dt = datetime.fromisoformat(data.end_at)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format")

    if end_dt <= start_dt:
        raise HTTPException(status_code=400, detail="end_at must be after start_at")

    effective_agent_id = data.agent_id
    if current_user.role == RoleEnum.AGENT:
        effective_agent_id = str(current_user.id)

    conflicts = []
    if effective_agent_id:
        conflicts = _get_conflicts(
            db, effective_agent_id, current_user.tenant_id, start_dt, end_dt
        )

    appt = Appointment(
        tenant_id=current_user.tenant_id,
        agent_id=effective_agent_id,
        created_by_id=str(current_user.id),
        title=data.title,
        appointment_type=data.appointment_type,
        start_at=start_dt,
        end_at=end_dt,
        description=data.description,
        location=data.location,
        all_day=data.all_day,
    )
    db.add(appt)
    db.commit()
    db.refresh(appt)

    return {
        "message": "Appointment created",
        "id": str(appt.id),
        "conflicts": conflicts,
    }


@router.put("/appointments/{appointment_id}")
def update_appointment(
    appointment_id: str,
    data: AppointmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    appt = db.query(Appointment).filter(
        Appointment.id == appointment_id,
        Appointment.tenant_id == current_user.tenant_id,
    ).first()
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")

    if current_user.role == RoleEnum.AGENT and appt.agent_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if key in ("start_at", "end_at") and value:
            setattr(appt, key, datetime.fromisoformat(value))
        else:
            setattr(appt, key, value)

    db.commit()

    start_dt = appt.start_at
    end_dt = appt.end_at
    agent_id = str(appt.agent_id) if appt.agent_id else None
    conflicts = []
    if agent_id:
        conflicts = _get_conflicts(
            db, agent_id, current_user.tenant_id, start_dt, end_dt,
            exclude_appointment_id=appointment_id,
        )

    return {"message": "Appointment updated", "conflicts": conflicts}


@router.delete("/appointments/{appointment_id}")
def delete_appointment(
    appointment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    appt = db.query(Appointment).filter(
        Appointment.id == appointment_id,
        Appointment.tenant_id == current_user.tenant_id,
    ).first()
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")

    if current_user.role == RoleEnum.AGENT and appt.agent_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    db.delete(appt)
    db.commit()
    return {"message": "Appointment deleted"}


@router.get("/appointments/{appointment_id}", response_model=AppointmentRead)
def get_appointment(
    appointment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    appt = (
        db.query(Appointment)
        .options(*_appointment_options())
        .filter(
            Appointment.id == appointment_id,
            Appointment.tenant_id == current_user.tenant_id,
        )
        .first()
    )
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")

    if current_user.role == RoleEnum.AGENT and appt.agent_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    return appt
