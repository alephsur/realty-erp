from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from app.database import get_db
from app.models.auth import Tenant, User, RoleEnum
from app.core.security import get_password_hash, verify_password
from app.auth.jwt import create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])

class CompanyRegisterRequest(BaseModel):
    company_name: str
    admin_email: EmailStr
    admin_password: str
    admin_full_name: str
    plan: str = "basic"

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

@router.post("/register-company", status_code=status.HTTP_201_CREATED)
def register_company(data: CompanyRegisterRequest, db: Session = Depends(get_db)):
    # Check if company name already exists
    if db.query(Tenant).filter(Tenant.name == data.company_name).first():
        raise HTTPException(status_code=400, detail="Company name already registered")
    
    # Check if user email already exists
    if db.query(User).filter(User.email == data.admin_email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    try:
        # Create Tenant
        new_tenant = Tenant(
            name=data.company_name,
            plan=data.plan
        )
        db.add(new_tenant)
        db.flush() # To get the tenant ID
        
        # Create Admin User
        new_user = User(
            tenant_id=new_tenant.id,
            email=data.admin_email,
            password_hash=get_password_hash(data.admin_password),
            full_name=data.admin_full_name,
            role=RoleEnum.ADMIN
        )
        db.add(new_user)
        db.commit()
        
        return {"message": "Company and admin user created successfully", "tenant_id": new_tenant.id, "user_id": new_user.id}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")

@router.post("/login")
def login(data: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
        
    access_token = create_access_token(
        user_id=str(user.id),
        role=user.role,
        tenant_id=str(user.tenant_id) if user.tenant_id else None
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": str(user.id),
            "email": user.email,
            "role": user.role,
            "tenant_id": str(user.tenant_id) if user.tenant_id else None
        }
    }
