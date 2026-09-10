from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import update as sa_update
from pydantic import BaseModel, EmailStr
from typing import Optional
from slowapi import Limiter
from slowapi.util import get_remote_address
import hashlib
import secrets
import logging

# Re-use the same limiter instance registered in main.py
limiter = Limiter(key_func=get_remote_address)

from app.database import get_db
from app.models.auth import Tenant, User, RoleEnum
from app.core.security import get_password_hash, verify_password
from app.core.config import settings
from app.core.csrf import verify_csrf_token, CSRF_COOKIE
from app.auth.jwt import create_access_token, create_invite_token, decode_invite_token
from app.api.dependencies import get_current_user, get_superadmin_user
from jose import JWTError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

# ------------------------------------------------------------------ #
# Cookie helpers
# ------------------------------------------------------------------ #
ACCESS_TOKEN_COOKIE = "access_token"
_COOKIE_MAX_AGE = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60


def _set_auth_cookies(response: Response, access_token: str) -> str:
    """Attach httpOnly JWT cookie + readable CSRF cookie to *response*.

    Returns the csrf_token value so callers can include it in the body if
    needed (e.g. for the initial login response).
    """
    csrf_token = secrets.token_hex(32)

    # JWT — httpOnly prevents JS access; SameSite=Strict blocks cross-origin sends
    response.set_cookie(
        key=ACCESS_TOKEN_COOKIE,
        value=access_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        max_age=_COOKIE_MAX_AGE,
        path="/",
    )

    # CSRF token — intentionally NOT httpOnly so JS can read it from document.cookie
    response.set_cookie(
        key=CSRF_COOKIE,
        value=csrf_token,
        httponly=False,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        max_age=_COOKIE_MAX_AGE,
        path="/",
    )
    return csrf_token


def _clear_auth_cookies(response: Response) -> None:
    """Expire both auth cookies immediately."""
    for cookie in (ACCESS_TOKEN_COOKIE, CSRF_COOKIE):
        response.delete_cookie(key=cookie, path="/")


# ------------------------------------------------------------------ #
# Schemas
# ------------------------------------------------------------------ #

class CompanyRegisterRequest(BaseModel):
    company_name: str
    admin_email: EmailStr
    admin_password: str
    admin_full_name: str
    plan: str = "basic"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


# ------------------------------------------------------------------ #
# Auth endpoints
# ------------------------------------------------------------------ #

@router.post("/register-company", status_code=status.HTTP_201_CREATED)
def register_company(data: CompanyRegisterRequest, db: Session = Depends(get_db)):
    if db.query(Tenant).filter(Tenant.name == data.company_name).first():
        raise HTTPException(status_code=400, detail="Company name already registered")

    if db.query(User).filter(User.email == data.admin_email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    try:
        new_tenant = Tenant(name=data.company_name, plan=data.plan)
        db.add(new_tenant)
        db.flush()

        new_user = User(
            tenant_id=new_tenant.id,
            email=data.admin_email,
            password_hash=get_password_hash(data.admin_password),
            full_name=data.admin_full_name,
            role=RoleEnum.ADMIN,
        )
        db.add(new_user)
        db.commit()

        return {
            "message": "Company and admin user created successfully",
            "tenant_id": new_tenant.id,
            "user_id": new_user.id,
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")


@router.post("/login")
@limiter.limit("5/minute")
def login(request: Request, data: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access_token = create_access_token(
        user_id=str(user.id),
        role=user.role,
        tenant_id=str(user.tenant_id) if user.tenant_id else None,
    )

    # Use JSONResponse so we can attach Set-Cookie headers before returning.
    # The token is NOT included in the body — it lives only in the httpOnly cookie.
    response = JSONResponse(content={
        "must_change_password": user.must_change_password,
        "user": {
            "id": str(user.id),
            "email": user.email,
            "role": user.role,
            "full_name": user.full_name,
            "tenant_id": str(user.tenant_id) if user.tenant_id else None,
        },
    })
    _set_auth_cookies(response, access_token)
    return response


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    _csrf: None = Depends(verify_csrf_token),
    current_user: User = Depends(get_current_user),
):
    """Clear auth cookies and invalidate the session."""
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    _clear_auth_cookies(response)
    return response


@router.get("/me")
def me(current_user: User = Depends(get_current_user)):
    """Return the authenticated user's profile.

    Used by the frontend on page reload to rehidrate the auth context
    without relying on localStorage.
    """
    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": current_user.role,
        "tenant_id": str(current_user.tenant_id) if current_user.tenant_id else None,
        "must_change_password": current_user.must_change_password,
    }


@router.post("/change-password", status_code=status.HTTP_200_OK)
def change_password(
    data: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _csrf: None = Depends(verify_csrf_token),
):
    """Allows an authenticated user to change their own password.

    Mandatory for accounts flagged with must_change_password=True (e.g. the
    bootstrapped superadmin or freshly invited users).
    """
    if not verify_password(data.current_password, current_user.password_hash):
        raise HTTPException(status_code=401, detail="Current password is incorrect")

    if data.new_password == data.current_password:
        raise HTTPException(
            status_code=400,
            detail="New password must be different from the current password",
        )

    current_user.password_hash = get_password_hash(data.new_password)
    current_user.must_change_password = False
    db.commit()
    return {"message": "Password changed successfully"}


# ------------------------------------------------------------------ #
# SuperAdmin — tenant management
# ------------------------------------------------------------------ #

class TenantCreateByAdmin(BaseModel):
    name: str
    plan: str = "basic"


class TenantUpdateByAdmin(BaseModel):
    name: Optional[str] = None
    plan: Optional[str] = None
    is_active: Optional[bool] = None


@router.post("/admin/tenants", status_code=status.HTTP_201_CREATED)
def create_tenant(
    data: TenantCreateByAdmin,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_superadmin_user),
    _csrf: None = Depends(verify_csrf_token),
):
    if db.query(Tenant).filter(Tenant.name == data.name).first():
        raise HTTPException(status_code=400, detail="Tenant name already exists")

    new_tenant = Tenant(name=data.name, plan=data.plan)
    db.add(new_tenant)
    db.commit()
    db.refresh(new_tenant)
    return {"message": "Tenant created", "tenant_id": new_tenant.id}


def _serialize_tenant(t: Tenant, db: Session) -> dict:
    user_count = db.query(User).filter(User.tenant_id == t.id).count()
    return {
        "id": str(t.id),
        "name": t.name,
        "plan": t.plan,
        "is_active": t.is_active,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "user_count": user_count,
    }


@router.get("/admin/tenants")
def get_tenants(db: Session = Depends(get_db), current_admin: User = Depends(get_superadmin_user)):
    tenants = db.query(Tenant).order_by(Tenant.created_at.desc()).all()
    return [_serialize_tenant(t, db) for t in tenants]


@router.put("/admin/tenants/{tenant_id}")
def update_tenant(
    tenant_id: str,
    data: TenantUpdateByAdmin,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_superadmin_user),
    _csrf: None = Depends(verify_csrf_token),
):
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    if data.name is not None:
        existing = db.query(Tenant).filter(Tenant.name == data.name, Tenant.id != tenant_id).first()
        if existing:
            raise HTTPException(status_code=400, detail="Tenant name already exists")
        tenant.name = data.name
    if data.plan is not None:
        tenant.plan = data.plan
    if data.is_active is not None:
        tenant.is_active = data.is_active
    db.commit()
    return {"message": "Tenant updated"}


@router.delete("/admin/tenants/{tenant_id}")
def delete_tenant(
    tenant_id: str,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_superadmin_user),
    _csrf: None = Depends(verify_csrf_token),
):
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    db.delete(tenant)
    db.commit()
    return {"message": "Tenant deleted"}


@router.get("/admin/tenants/{tenant_id}/users")
def get_tenant_users_admin(
    tenant_id: str,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_superadmin_user),
):
    users = db.query(User).filter(User.tenant_id == tenant_id).all()
    return [
        {"id": str(u.id), "email": u.email, "full_name": u.full_name, "role": u.role, "is_active": u.is_active}
        for u in users
    ]


class UserInvite(BaseModel):
    tenant_id: str
    email: EmailStr
    full_name: str
    role: RoleEnum = RoleEnum.ADMIN


@router.post("/admin/users/invite", status_code=status.HTTP_201_CREATED)
def invite_user(
    data: UserInvite,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_superadmin_user),
    _csrf: None = Depends(verify_csrf_token),
):
    tenant = db.query(Tenant).filter(Tenant.id == data.tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(status_code=400, detail="User with this email already exists")

    raw_token = secrets.token_urlsafe(32)

    new_user = User(
        tenant_id=tenant.id,
        email=data.email,
        password_hash=get_password_hash(secrets.token_urlsafe(32)),
        full_name=data.full_name,
        role=data.role,
        is_active=False,
        invite_token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    token = create_invite_token(new_user.email, str(tenant.id), raw_token)
    invite_link = f"{settings.FRONTEND_URL}/accept-invite?token={token}"
    logger.warning(f"INVITATION LINK GENERATED FOR {data.email}: {invite_link}")

    return {"message": "User invited", "invite_link": invite_link}


class AcceptInvite(BaseModel):
    token: str
    new_password: str


@router.post("/accept-invite")
def accept_invite(data: AcceptInvite, db: Session = Depends(get_db)):
    try:
        payload = decode_invite_token(data.token)
        email = payload.get("sub")
        raw_token = payload.get("invite_token")
        if not email or not raw_token:
            raise ValueError("Missing claims")
    except (JWTError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid or expired invite token")

    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    new_password_hash = get_password_hash(data.new_password)

    result = db.execute(
        sa_update(User)
        .where(User.email == email, User.invite_token_hash == token_hash)
        .values(password_hash=new_password_hash, is_active=True, invite_token_hash=None)
    )
    db.commit()

    if result.rowcount == 0:
        raise HTTPException(status_code=400, detail="Invite token already used or invalid")

    return {"message": "Password updated successfully. You can now login."}


# ------------------------------------------------------------------ #
# Tenant-scoped employee management
# ------------------------------------------------------------------ #

@router.get("/tenant/users")
def get_tenant_users(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role not in [RoleEnum.ADMIN, RoleEnum.MANAGER, RoleEnum.SUPER_ADMIN]:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    if not current_user.tenant_id:
        raise HTTPException(status_code=400, detail="User does not belong to a tenant")

    users = db.query(User).filter(User.tenant_id == current_user.tenant_id).all()
    return [
        {
            "id": str(u.id),
            "email": u.email,
            "full_name": u.full_name,
            "role": u.role,
            "is_active": u.is_active,
            "phone": u.phone,
            "license_number": u.license_number,
            "commission_rate": u.commission_rate,
            "hire_date": u.hire_date.isoformat() if u.hire_date else None,
        }
        for u in users
    ]


class TenantUserCreate(BaseModel):
    email: EmailStr
    full_name: str
    role: RoleEnum = RoleEnum.AGENT
    phone: Optional[str] = None
    license_number: Optional[str] = None
    commission_rate: Optional[float] = 0.0
    hire_date: Optional[str] = None


@router.post("/tenant/users", status_code=status.HTTP_201_CREATED)
def create_tenant_user(
    data: TenantUserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _csrf: None = Depends(verify_csrf_token),
):
    if current_user.role not in [RoleEnum.ADMIN, RoleEnum.MANAGER]:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    if not current_user.tenant_id:
        raise HTTPException(status_code=400, detail="User does not belong to a tenant")

    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(status_code=400, detail="User with this email already exists")

    dummy_password = secrets.token_urlsafe(32)
    pwd_ver = get_password_hash(dummy_password)

    from datetime import date as date_type
    new_user = User(
        tenant_id=current_user.tenant_id,
        email=data.email,
        password_hash=pwd_ver,
        full_name=data.full_name,
        role=data.role,
        phone=data.phone,
        license_number=data.license_number,
        commission_rate=data.commission_rate or 0.0,
        hire_date=date_type.fromisoformat(data.hire_date) if data.hire_date else None,
        is_active=False,
    )
    db.add(new_user)
    db.commit()
    return {"message": "Employee created successfully"}


class TenantUserUpdate(BaseModel):
    full_name: Optional[str] = None
    role: Optional[RoleEnum] = None
    is_active: Optional[bool] = None
    phone: Optional[str] = None
    license_number: Optional[str] = None
    commission_rate: Optional[float] = None
    hire_date: Optional[str] = None


@router.put("/tenant/users/{user_id}")
def update_tenant_user(
    user_id: str,
    data: TenantUserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _csrf: None = Depends(verify_csrf_token),
):
    if current_user.role not in [RoleEnum.ADMIN, RoleEnum.MANAGER]:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    user = db.query(User).filter(User.id == user_id, User.tenant_id == current_user.tenant_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Employee not found")

    from datetime import date as date_type
    if data.full_name is not None:
        user.full_name = data.full_name
    if data.role is not None:
        user.role = data.role
    if data.is_active is not None:
        user.is_active = data.is_active
    if data.phone is not None:
        user.phone = data.phone
    if data.license_number is not None:
        user.license_number = data.license_number
    if data.commission_rate is not None:
        user.commission_rate = data.commission_rate
    if data.hire_date is not None:
        user.hire_date = date_type.fromisoformat(data.hire_date)

    db.commit()
    return {"message": "Employee updated successfully"}


@router.delete("/tenant/users/{user_id}")
def delete_tenant_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _csrf: None = Depends(verify_csrf_token),
):
    if current_user.role not in [RoleEnum.ADMIN, RoleEnum.MANAGER]:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    user = db.query(User).filter(User.id == user_id, User.tenant_id == current_user.tenant_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Employee not found")

    db.delete(user)
    db.commit()
    return {"message": "Employee deleted"}


@router.post("/tenant/users/{user_id}/invite")
def generate_user_invite(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _csrf: None = Depends(verify_csrf_token),
):
    if current_user.role not in [RoleEnum.ADMIN, RoleEnum.MANAGER]:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    user = db.query(User).filter(User.id == user_id, User.tenant_id == current_user.tenant_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Employee not found")

    raw_token = secrets.token_urlsafe(32)
    user.invite_token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    db.commit()

    token = create_invite_token(user.email, str(user.tenant_id), raw_token)
    invite_link = f"{settings.FRONTEND_URL}/accept-invite?token={token}"
    logger.warning(f"INVITATION LINK GENERATED FOR {user.email}: {invite_link}")

    return {"message": "Invite link generated", "invite_link": invite_link}
