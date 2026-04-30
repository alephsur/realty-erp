from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, model_validator


class AppointmentRead(BaseModel):
    id: str
    agent_id: Optional[str] = None
    agent_name: Optional[str] = None
    title: str
    description: Optional[str] = None
    location: Optional[str] = None
    appointment_type: str
    start_at: str
    end_at: str
    all_day: bool = False
    created_by_id: Optional[str] = None
    created_at: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def from_orm_object(cls, data: Any) -> Any:
        if isinstance(data, dict):
            return data
        a = data
        return {
            "id": str(a.id),
            "agent_id": str(a.agent_id) if a.agent_id else None,
            "agent_name": a.agent.full_name if a.agent else None,
            "title": a.title,
            "description": a.description,
            "location": a.location,
            "appointment_type": a.appointment_type.value if a.appointment_type else None,
            "start_at": a.start_at.isoformat() if a.start_at else None,
            "end_at": a.end_at.isoformat() if a.end_at else None,
            "all_day": a.all_day,
            "created_by_id": str(a.created_by_id) if a.created_by_id else None,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
