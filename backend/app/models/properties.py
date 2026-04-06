import uuid
import enum
from sqlalchemy import Column, String, Float, Enum, DateTime, func, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base

class PropertyStatus(str, enum.Enum):
    AVAILABLE = "Disponible"
    RESERVED = "Reservado"
    SOLD = "Vendido"

class Property(Base):
    __tablename__ = "properties"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    price = Column(Float, nullable=False)
    address = Column(String, nullable=False)
    status = Column(Enum(PropertyStatus), default=PropertyStatus.AVAILABLE, nullable=False)
    
    bedrooms = Column(Integer, default=0)
    bathrooms = Column(Integer, default=0)
    sqm = Column(Float, default=0.0)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # RLS ensures row isolation by tenant_id automatically.
    # The agent assignment helps in business logic when filtering "only my properties".
    agent = relationship("User", back_populates="properties")
    sales = relationship("Sale", back_populates="property")
