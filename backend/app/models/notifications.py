import uuid
from sqlalchemy import Column, String, DateTime, func, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    type = Column(String, nullable=False)
    title = Column(String, nullable=False)
    body = Column(Text, nullable=False)
    read_at = Column(DateTime(timezone=True), nullable=True)
    entity_type = Column(String, nullable=True)   # property | client | visit | sale
    entity_id = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
