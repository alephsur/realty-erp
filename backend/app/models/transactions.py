import uuid
from sqlalchemy import Column, String, Float, DateTime, func, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base

class Sale(Base):
    __tablename__ = "sales"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    property_id = Column(UUID(as_uuid=True), ForeignKey("properties.id", ondelete="RESTRICT"), nullable=False)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    buyer_id = Column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="SET NULL"), nullable=True)
    
    sale_price = Column(Float, nullable=False)
    
    # Commission breakdown
    total_commission = Column(Float, nullable=False)     # Total amount earned
    agent_commission = Column(Float, nullable=False)     # Amount for the agent
    agency_commission = Column(Float, nullable=False)    # Amount for the agency
    
    notes = Column(Text, nullable=True)
    
    sale_date = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    property = relationship("Property", back_populates="sales")
    agent = relationship("User", foreign_keys=[agent_id])
    buyer = relationship("Client", foreign_keys=[buyer_id])
