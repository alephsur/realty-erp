import uuid
import enum
from sqlalchemy import Column, String, Numeric, Enum, DateTime, func, ForeignKey, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.database import Base


class CommissionStatus(str, enum.Enum):
    PENDING = "PENDING"
    INVOICED = "INVOICED"
    PAID = "PAID"


class CommissionPayment(Base):
    __tablename__ = "commission_payments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    sale_id = Column(UUID(as_uuid=True), ForeignKey("sales.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    settlement_id = Column(UUID(as_uuid=True), ForeignKey("commission_settlements.id", ondelete="RESTRICT"), nullable=True)
    event_id = Column(UUID(as_uuid=True), ForeignKey("sale_events.id", ondelete="RESTRICT"), nullable=True)
    kind = Column(String(16), nullable=False, default="EARNED", server_default="EARNED")

    amount = Column(Numeric(), nullable=False)
    status = Column(Enum(CommissionStatus), default=CommissionStatus.PENDING, nullable=False)

    payment_date = Column(DateTime(timezone=True), nullable=True)
    invoice_number = Column(String, nullable=True)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    settlement = relationship("CommissionSettlement", foreign_keys=[settlement_id])
    sale = relationship("Sale", foreign_keys=[sale_id])
    agent = relationship("User", foreign_keys=[agent_id])


class CommissionSettlement(Base):
    __tablename__ = "commission_settlements"
    __table_args__ = (UniqueConstraint("tenant_id", "request_id", name="uq_commission_settlement_request"),)
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    request_id = Column(UUID(as_uuid=True), nullable=False)
    request_hash = Column(String(64), nullable=False)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    actor_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    amount = Column(Numeric(), nullable=False)
    entry_ids = Column(JSONB, nullable=False)
    payment_date = Column(DateTime(timezone=True), nullable=False)
    invoice_number = Column(String)
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
