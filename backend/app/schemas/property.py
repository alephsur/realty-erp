"""
Pydantic v2 read-schemas for Properties and Sales.

The model_validator(mode='before') handles the ORM → dict conversion so that:
  - Enum fields are serialized to their .value string.
  - Computed fields (e.g. agent_name) are resolved from loaded relationships.
  - All UUIDs are returned as plain strings for JSON compatibility.

FastAPI will use these as response_model= so OpenAPI/Swagger describes every
field and TypeScript clients can be regenerated automatically.
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, model_validator


class PropertyRead(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    property_type: Optional[str] = None
    price: float
    address: str
    city: Optional[str] = None
    postal_code: Optional[str] = None
    reference: Optional[str] = None
    status: Optional[str] = None
    status_key: Optional[str] = None
    bedrooms: int = 0
    bathrooms: int = 0
    sqm: float = 0.0
    owner_name: Optional[str] = None
    owner_phone: Optional[str] = None
    owner_email: Optional[str] = None
    commission_rate: float = 0.0
    agent_commission_rate: Optional[float] = None
    agent_id: Optional[str] = None
    agent_name: Optional[str] = None
    created_at: Optional[str] = None
    status_changed_at: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def from_orm_object(cls, data: Any) -> Any:
        if isinstance(data, dict):
            return data
        p = data
        return {
            "id": str(p.id),
            "title": p.title,
            "description": p.description,
            "property_type": p.property_type.value if p.property_type else None,
            "price": p.price,
            "address": p.address,
            "city": p.city,
            "postal_code": p.postal_code,
            "reference": p.reference,
            "status": p.status.value if p.status else None,
            "status_key": p.status.name if p.status else None,
            "bedrooms": p.bedrooms,
            "bathrooms": p.bathrooms,
            "sqm": p.sqm,
            "owner_name": p.owner_name,
            "owner_phone": p.owner_phone,
            "owner_email": p.owner_email,
            "commission_rate": p.commission_rate,
            "agent_commission_rate": p.agent_commission_rate,
            "agent_id": str(p.agent_id) if p.agent_id else None,
            "agent_name": p.agent.full_name if p.agent else None,
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "status_changed_at": p.status_changed_at.isoformat() if p.status_changed_at else None,
        }


class SaleRead(BaseModel):
    id: str
    property_id: str
    property_title: Optional[str] = None
    property_reference: Optional[str] = None
    agent_id: Optional[str] = None
    agent_name: Optional[str] = None
    buyer_id: Optional[str] = None
    buyer_name: Optional[str] = None
    sale_price: float
    total_commission: float
    agent_commission: float
    agency_commission: float
    notes: Optional[str] = None
    sale_date: Optional[str] = None
    created_at: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def from_orm_object(cls, data: Any) -> Any:
        if isinstance(data, dict):
            return data
        s = data
        return {
            "id": str(s.id),
            "property_id": str(s.property_id),
            "property_title": s.property.title if s.property else None,
            "property_reference": s.property.reference if s.property else None,
            "agent_id": str(s.agent_id) if s.agent_id else None,
            "agent_name": s.agent.full_name if s.agent else None,
            "buyer_id": str(s.buyer_id) if s.buyer_id else None,
            "buyer_name": (
                f"{s.buyer.first_name} {s.buyer.last_name}" if s.buyer else None
            ),
            "sale_price": s.sale_price,
            "total_commission": s.total_commission,
            "agent_commission": s.agent_commission,
            "agency_commission": s.agency_commission,
            "notes": s.notes,
            "sale_date": s.sale_date.isoformat() if s.sale_date else None,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }


class AgentRankingRead(BaseModel):
    id: str
    full_name: str
    email: str
    active_properties: int
    total_sales: int
    total_commission: float
    total_volume: float
    commission_rate: float
