from __future__ import annotations
from typing import Any, Optional
from pydantic import BaseModel, model_validator


class CommissionPaymentRead(BaseModel):
    id: str
    sale_id: str
    agent_id: Optional[str] = None
    agent_name: Optional[str] = None
    amount: float
    status: str
    payment_date: Optional[str] = None
    invoice_number: Optional[str] = None
    notes: Optional[str] = None
    created_at: Optional[str] = None
    property_title: Optional[str] = None
    property_reference: Optional[str] = None
    sale_price: Optional[float] = None
    sale_date: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def from_orm_object(cls, data: Any) -> Any:
        if isinstance(data, dict):
            return data
        cp = data
        sale = cp.sale if cp.sale else None
        return {
            "id": str(cp.id),
            "sale_id": str(cp.sale_id),
            "agent_id": str(cp.agent_id) if cp.agent_id else None,
            "agent_name": cp.agent.full_name if cp.agent else None,
            "amount": cp.amount,
            "status": cp.status.value if cp.status else None,
            "payment_date": cp.payment_date.isoformat() if cp.payment_date else None,
            "invoice_number": cp.invoice_number,
            "notes": cp.notes,
            "created_at": cp.created_at.isoformat() if cp.created_at else None,
            "property_title": sale.property.title if sale and sale.property else None,
            "property_reference": sale.property.reference if sale and sale.property else None,
            "sale_price": sale.sale_price if sale else None,
            "sale_date": sale.sale_date.isoformat() if sale and sale.sale_date else None,
        }
