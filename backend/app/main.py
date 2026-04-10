from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from app.core.middleware import set_current_tenant_id_in_context, reset_tenant_id_in_context
from app.auth.jwt import decode_access_token
from jose import JWTError
import logging
import secrets
from contextlib import asynccontextmanager
from app.database import SessionLocal
from app.models.auth import User, RoleEnum
from app.core.security import get_password_hash

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create superadmin if it doesn't exist
    db = SessionLocal()
    try:
        superadmin = db.query(User).filter(User.role == RoleEnum.SUPER_ADMIN).first()
        if not superadmin:
            email = "admin@erp.com"
            password = secrets.token_urlsafe(12)
            hashed = get_password_hash(password)
            new_superadmin = User(
                email=email,
                password_hash=hashed,
                full_name="System Superadmin",
                role=RoleEnum.SUPER_ADMIN
            )
            db.add(new_superadmin)
            db.commit()
            logger.warning("==================================================")
            logger.warning("🚀 SUPERADMIN CREATED AUTOMATICALLY")
            logger.warning(f"Email: {email}")
            logger.warning(f"Password: {password}")
            logger.warning("==================================================")
    except Exception as e:
        logger.error(f"Database might not be ready or migrations not applied yet. Skipping superadmin creation. Error: {e}")
    finally:
        db.close()
    yield

app = FastAPI(title="Realty ERP Multi-tenant API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict this
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def tenant_middleware(request: Request, call_next):
    """
    Middleware to extract tenant_id from JWT and set it in context.
    The database dependency will read this context var to set RLS.
    """
    tenant_id_from_token = None
    auth_header = request.headers.get("Authorization")
    
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        try:
            payload = decode_access_token(token)
            # Must match the claim in the token creation
            tenant_id_from_token = payload.get("tenant_id")
        except JWTError:
            pass # Invalid token, do not set tenant_id
            
    # Set context
    token_ctx = set_current_tenant_id_in_context(tenant_id_from_token)
    
    try:
        response = await call_next(request)
        return response
    finally:
        # Prevent context leakage between requests
        reset_tenant_id_in_context(token_ctx)

@app.get("/health")
def health_check():
    return {"status": "ok"}

from app.api.auth import router as auth_router
from app.api.properties import router as properties_router
app.include_router(auth_router)
app.include_router(properties_router)
