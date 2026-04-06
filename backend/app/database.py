import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import text

SQLALCHEMY_DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://postgres:postgrespassword@localhost:5432/realty_erp"
)

# We use SQLAlchemy 2.0 with create_engine
engine = create_engine(SQLALCHEMY_DATABASE_URL, echo=False)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db(tenant_id: str | None = None):
    """
    Dependency to get a database session.
    If a tenant_id is provided (usually via the global request state injected by middleware),
    it executes a SET command to set the tenant parameter for Row-Level Security isolation.
    """
    db = SessionLocal()
    try:
        from app.core.middleware import get_current_tenant_id_from_context
        ctx_tenant_id = get_current_tenant_id_from_context()
        effective_tenant_id = tenant_id or ctx_tenant_id
        
        # Set tenant session variable if available
        if effective_tenant_id:
            db.execute(
                text("SET LOCAL app.current_tenant = :tenant_id"),
                {"tenant_id": str(effective_tenant_id)}
            )
        else:
            # Clear or ensure empty tenant to avoid leaking previous contexts in connection pools
            db.execute(text("SET LOCAL app.current_tenant = ''"))
        
        yield db
    finally:
        db.close()
