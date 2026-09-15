import uuid
from sqlalchemy import Column, String, Boolean, Integer, Numeric, UniqueConstraint, DateTime, func, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.database import Base

class Sale(Base):
    __tablename__ = "sales"
    __table_args__ = (
        UniqueConstraint("tenant_id", "closing_request_id", name="uq_sales_tenant_closing_request"),
    )
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    property_id = Column(UUID(as_uuid=True), ForeignKey("properties.id", ondelete="RESTRICT"), nullable=False)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    buyer_id = Column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="SET NULL"), nullable=True)
    
    sale_price = Column(Numeric(), nullable=False)
    
    # Commission breakdown
    total_commission = Column(Numeric(), nullable=False)     # Total amount earned
    agent_commission = Column(Numeric(), nullable=False)     # Amount for the agent
    agency_commission = Column(Numeric(), nullable=False)    # Amount for the agency
    
    commission_rate = Column(Numeric(7, 4), nullable=True)
    agent_commission_rate = Column(Numeric(7, 4), nullable=True)
    closing_request_id = Column(UUID(as_uuid=True), nullable=True)
    closing_request_hash = Column(String(64), nullable=True)
    closed_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    closed_from_status = Column(String(32), nullable=True)

    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    version = Column(Integer, nullable=False, default=1, server_default="1")
    reopened_at = Column(DateTime(timezone=True), nullable=True)

    notes = Column(Text, nullable=True)
    
    sale_date = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    property = relationship("Property", back_populates="sales")
    agent = relationship("User", foreign_keys=[agent_id])
    buyer = relationship("Client", foreign_keys=[buyer_id])


class SaleEvent(Base):
    __tablename__ = "sale_events"
    __table_args__ = (
        UniqueConstraint("tenant_id", "request_id", name="uq_sale_events_request"),
        UniqueConstraint("sale_id", "version", name="uq_sale_events_version"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    sale_id = Column(UUID(as_uuid=True), ForeignKey("sales.id", ondelete="RESTRICT"), nullable=False, index=True)
    request_id = Column(UUID(as_uuid=True), nullable=False)
    request_hash = Column(String(64), nullable=False)
    kind = Column(String(16), nullable=False)
    version = Column(Integer, nullable=False)
    actor_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    actor_name = Column(String, nullable=False)
    reason = Column(Text, nullable=False)
    before_data = Column(JSONB, nullable=True)
    after_data = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
