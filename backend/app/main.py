from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from app.core.middleware import set_current_tenant_id_in_context, reset_tenant_id_in_context
from app.auth.jwt import decode_access_token
from jose import JWTError

app = FastAPI(title="Realty ERP Multi-tenant API")

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
app.include_router(auth_router)
