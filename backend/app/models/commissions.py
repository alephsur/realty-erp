import uuid
import enum
from sqlalchemy import Column, String, Float, Enum, DateTime, func, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
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
    sale_id = Column(UUID(as_uuid=True), ForeignKey("sales.id", ondelete="CASCADE"), nullable=False, unique=True)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    amount = Column(Float, nullable=False)
    status = Column(Enum(CommissionStatus), default=CommissionStatus.PENDING, nullable=False)

    payment_date = Column(DateTime(timezone=True), nullable=True)
    invoice_number = Column(String, nullable=True)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    sale = relationship("Sale", foreign_keys=[sale_id])
    agent = relationship("User", foreign_keys=[agent_id])
