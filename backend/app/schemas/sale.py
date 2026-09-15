"""Explicit, validated inputs for the single sale-closing operation."""

from decimal import Decimal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

from app.models.properties import PropertyStatus


class SellPropertyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: UUID
    buyer_id: UUID
    agent_id: UUID
    sale_price: Decimal = Field(gt=0, max_digits=16, decimal_places=2)
    commission_rate: Decimal = Field(ge=0, le=100, decimal_places=4)
    agent_commission_rate: Decimal = Field(ge=0, le=100, decimal_places=4)
    notes: str | None = Field(default=None, max_length=10000)


class CorrectSaleRequest(SellPropertyRequest):
    expected_version: int = Field(ge=1)
    sale_date: AwareDatetime
    reason: str = Field(min_length=1, max_length=2000)

    @field_validator("reason")
    @classmethod
    def nonblank_reason(cls, value):
        if not value.strip():
            raise ValueError("Indica el motivo de la corrección")
        return value.strip()


class ReopenSaleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: UUID
    expected_version: int = Field(ge=1)
    target_status: PropertyStatus
    reason: str = Field(min_length=1, max_length=2000)

    @field_validator("target_status")
    @classmethod
    def open_status(cls, value):
        if value == PropertyStatus.VENDIDA:
            raise ValueError("La reapertura requiere un estado distinto de VENDIDA")
        return value

    @field_validator("reason")
    @classmethod
    def nonblank_reason(cls, value):
        if not value.strip():
            raise ValueError("Indica el motivo de la reapertura")
        return value.strip()
