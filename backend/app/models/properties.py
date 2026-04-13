import uuid
import enum
from sqlalchemy import Column, String, Float, Enum, DateTime, func, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base

class PropertyStatus(str, enum.Enum):
    CAPTADA = "CAPTADA"
    PUBLICADA = "PUBLICADA"
    EN_VISITAS = "EN_VISITAS"
    RESERVADA = "RESERVADA"
    PENDIENTE_NOTARIA = "PENDIENTE_NOTARIA"
    VENDIDA = "VENDIDA"
    RETIRADA = "RETIRADA"

class PropertyType(str, enum.Enum):
    PISO = "PISO"
    CASA = "CASA"
    CHALET = "CHALET"
    ATICO = "ATICO"
    LOCAL = "LOCAL"
    OFICINA = "OFICINA"
    TERRENO = "TERRENO"
    GARAJE = "GARAJE"
    TRASTERO = "TRASTERO"

class Property(Base):
    __tablename__ = "properties"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    # Property Info
    reference = Column(String, nullable=True)  # Internal reference code e.g. "INM-2024-001"
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    property_type = Column(Enum(PropertyType), default=PropertyType.PISO, nullable=False)
    price = Column(Float, nullable=False)
    address = Column(String, nullable=False)
    city = Column(String, nullable=True)
    postal_code = Column(String, nullable=True)
    status = Column(Enum(PropertyStatus), default=PropertyStatus.CAPTADA, nullable=False)
    
    # Features
    bedrooms = Column(Integer, default=0)
    bathrooms = Column(Integer, default=0)
    sqm = Column(Float, default=0.0)
    
    # Owner info
    owner_name = Column(String, nullable=True)
    owner_phone = Column(String, nullable=True)
    owner_email = Column(String, nullable=True)
    
    # Commission
    commission_rate = Column(Float, default=0.0)  # % comisión pactada con el propietario
    agent_commission_rate = Column(Float, nullable=True)  # Override: % comisión del agente para esta propiedad (si null, usa la tasa base del agente)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    agent = relationship("User", back_populates="properties")
    sales = relationship("Sale", back_populates="property")
