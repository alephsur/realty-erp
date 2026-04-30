"""
Pydantic v2 read-schema for Report endpoints that load ORM objects
(currently only top_sales — the other report endpoints use pure SQL aggregates
that already return plain dicts with no ORM lazy-loading).
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, model_validator


class TopSaleRead(BaseModel):
    id: str
    property_title: Optional[str] = None
    property_reference: Optional[str] = None
    agent_name: Optional[str] = None
    buyer_name: Optional[str] = None
    sale_price: float
    total_commission: float
    agency_commission: float
    agent_commission: float
    sale_date: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def from_orm_object(cls, data: Any) -> Any:
        if isinstance(data, dict):
            return data
        s = data
        return {
            "id": str(s.id),
            "property_title": s.property.title if s.property else None,
            "property_reference": s.property.reference if s.property else None,
            "agent_name": s.agent.full_name if s.agent else None,
            "buyer_name": (
                f"{s.buyer.first_name} {s.buyer.last_name}" if s.buyer else None
            ),
            "sale_price": s.sale_price,
            "total_commission": round(s.total_commission, 2),
            "agency_commission": round(s.agency_commission, 2),
            "agent_commission": round(s.agent_commission, 2),
            "sale_date": s.sale_date.isoformat() if s.sale_date else None,
        }
