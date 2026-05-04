import sys
import os
from sqlalchemy.orm import Session

# Add the parent directory to sys.path so we can import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models.auth import User, RoleEnum
from app.core.security import get_password_hash

def create_superadmin(email: str, password: str, full_name: str):
    db: Session = SessionLocal()
    try:
        if db.query(User).filter(User.email == email).first():
            print(f"User with email {email} already exists.")
            return

        new_user = User(
            email=email,
            password_hash=get_password_hash(password),
            full_name=full_name,
            role=RoleEnum.SUPER_ADMIN,
        )
        db.add(new_user)
        db.commit()
        print(f"Superadmin user {email} created successfully.")
    except Exception as e:
        db.rollback()
        print(f"Failed to create superadmin: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Create a superadmin user.")
    parser.add_argument("--email", required=True, help="Superadmin email")
    parser.add_argument("--password", required=True, help="Superadmin password")
    parser.add_argument("--name", default="Super Admin", help="Superadmin full name")
    
    args = parser.parse_args()
    create_superadmin(args.email, args.password, args.name)
