import uuid
import enum
from sqlalchemy import Column, String, Enum, DateTime, func, Boolean, ForeignKey, Float, Date
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base

class RoleEnum(str, enum.Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    ADMIN = "ADMIN"
    MANAGER = "MANAGER"
    AGENT = "AGENT"

class Tenant(Base):
    __tablename__ = "tenants"
    
    # We do not apply RLS to this table typically, as it defines the tenants
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    plan = Column(String, default="basic", nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    is_active = Column(Boolean, default=True)

    users = relationship("User", back_populates="tenant")


class User(Base):
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    full_name = Column(String, nullable=False)
    role = Column(Enum(RoleEnum), default=RoleEnum.AGENT, nullable=False)
    is_active = Column(Boolean, default=True)
    must_change_password = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    invite_token_hash = Column(String, nullable=True)

    # Agent-specific fields
    phone = Column(String, nullable=True)
    license_number = Column(String, nullable=True)  # Nº de colegiado / licencia
    commission_rate = Column(Float, nullable=True, default=0.0)  # % comisión por defecto del agente
    hire_date = Column(Date, nullable=True)

    tenant = relationship("Tenant", back_populates="users")
    properties = relationship("Property", back_populates="agent")
    clients = relationship("Client", back_populates="agent")
