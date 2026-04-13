import uuid
import enum
from sqlalchemy import Column, String, Enum, DateTime, func, ForeignKey, Boolean, Float, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base

class ClientType(str, enum.Enum):
    OWNER = "Propietario"
    BUYER = "Demandante"

class Client(Base):
    __tablename__ = "clients"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    client_type = Column(Enum(ClientType), nullable=False)
    
    # Extended CRM fields
    dni = Column(String, nullable=True)  # DNI / NIE / Passport
    address = Column(String, nullable=True)
    
    # Buyer preferences
    budget_min = Column(Float, nullable=True)
    budget_max = Column(Float, nullable=True)
    desired_zones = Column(String, nullable=True)  # Comma-separated zones
    desired_type = Column(String, nullable=True)  # Preferred property type
    
    notes = Column(Text, nullable=True)
    
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    agent = relationship("User", back_populates="clients")
    
    # Relationships for linked properties (interests)
    property_interests = relationship("ClientPropertyInterest", back_populates="client", cascade="all, delete-orphan")


class ClientPropertyInterest(Base):
    """Tracks which properties a buyer client is interested in."""
    __tablename__ = "client_property_interests"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    property_id = Column(UUID(as_uuid=True), ForeignKey("properties.id", ondelete="CASCADE"), nullable=False)
    
    interest_level = Column(String, default="medium")  # low, medium, high
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    client = relationship("Client", back_populates="property_interests")
    property = relationship("Property")
