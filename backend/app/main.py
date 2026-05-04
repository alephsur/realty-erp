from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from app.core.middleware import set_current_tenant_id_in_context, reset_tenant_id_in_context
from app.core.security_headers import SecurityHeadersMiddleware
from app.core.config import settings
from app.auth.jwt import decode_access_token
from jose import JWTError
import logging
import secrets
from contextlib import asynccontextmanager
from app.database import SessionLocal
from app.models.auth import User, RoleEnum
from app.core.security import get_password_hash

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
# Rate limiter (in-memory, per remote IP)
# ------------------------------------------------------------------ #
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ------------------------------------------------------------------ #
    # Superadmin bootstrap — only runs when BOOTSTRAP_SUPERADMIN_EMAIL is
    # set in the environment.  In production, set the env var exactly once
    # for the very first deploy.  The created account is flagged with
    # must_change_password=True so the operator must rotate the temporary
    # password on the first login.
    # ------------------------------------------------------------------ #
    bootstrap_email = settings.BOOTSTRAP_SUPERADMIN_EMAIL
    if bootstrap_email:
        db = SessionLocal()
        try:
            superadmin = db.query(User).filter(User.role == RoleEnum.SUPER_ADMIN).first()
            if not superadmin:
                password = secrets.token_urlsafe(16)
                hashed = get_password_hash(password)
                new_superadmin = User(
                    email=bootstrap_email,
                    password_hash=hashed,
                    full_name="System Superadmin",
                    role=RoleEnum.SUPER_ADMIN,
                    must_change_password=True,  # operator MUST rotate on first login
                )
                db.add(new_superadmin)
                db.commit()
                logger.warning("==================================================")
                logger.warning("SUPERADMIN CREATED — CHANGE PASSWORD IMMEDIATELY")
                logger.warning(f"   Email:    {bootstrap_email}")
                logger.warning(f"   Password: {password}")
                logger.warning("   This account requires a password change on first login.")
                logger.warning("==================================================")
            else:
                logger.info("Bootstrap: superadmin already exists, skipping creation.")
        except Exception as e:
            logger.error(
                "Database might not be ready or migrations not applied yet. "
                f"Skipping superadmin creation. Error: {e}"
            )
        finally:
            db.close()
    else:
        logger.debug(
            "BOOTSTRAP_SUPERADMIN_EMAIL not set — skipping superadmin bootstrap."
        )
    yield


app = FastAPI(title="Realty ERP Multi-tenant API", lifespan=lifespan)

# ------------------------------------------------------------------ #
# Rate-limiter state must be attached to the app BEFORE adding routes
# ------------------------------------------------------------------ #
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ------------------------------------------------------------------ #
# Security headers — runs on every response (registered first so it
# wraps everything; Starlette middleware stack is LIFO)
# ------------------------------------------------------------------ #
app.add_middleware(SecurityHeadersMiddleware)

# ------------------------------------------------------------------ #
# CORS — origins come from env (CORS_ORIGINS).
# NOTE: allow_credentials=True is *required* when sending cookies and is
# incompatible with allow_origins=["*"] per the Fetch spec.
# ------------------------------------------------------------------ #
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins(),
    allow_credentials=True,  # required for cookie-based auth
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-CSRF-Token"],
    expose_headers=["X-CSRF-Token"],
)


@app.middleware("http")
async def tenant_middleware(request: Request, call_next):
    """
    Middleware to extract tenant_id from JWT and set it in context.
    Reads the token from the httpOnly cookie (cookie-based auth strategy).
    The database dependency will read this context var to set RLS.
    """
    tenant_id_from_token = None

    # JWT is now in the httpOnly cookie, not the Authorization header
    token = request.cookies.get("access_token")
    if token:
        try:
            payload = decode_access_token(token)
            tenant_id_from_token = payload.get("tenant_id")
        except JWTError:
            pass  # Invalid token — do not set tenant_id

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
from app.api.clients import router as clients_router
from app.api.visits import router as visits_router
from app.api.reports import router as reports_router
from app.api.notifications import router as notifications_router
from app.api.calendar import router as calendar_router
from app.api.commissions import router as commissions_router

app.include_router(auth_router)
app.include_router(properties_router)
app.include_router(clients_router)
app.include_router(visits_router)
app.include_router(reports_router)
app.include_router(notifications_router)
app.include_router(calendar_router)
app.include_router(commissions_router)
