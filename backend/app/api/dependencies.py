"""FastAPI route dependencies for authentication and authorization.

JWT strategy
-----------
The access token is stored in an httpOnly cookie called ``access_token``.
It is *never* transmitted as a plain Bearer header (that path is gone) so JS
cannot touch it, eliminating the XSS-based token theft vector.

For routes that need the current user we:
  1. Read ``request.cookies["access_token"]``
  2. Decode the JWT with the application secret
  3. Look up the user in the database
  4. Guard that the account is active
"""
from uuid import UUID

from fastapi import Cookie, Depends, HTTPException, Request, status
from jose import JWTError
from sqlalchemy.orm import Session

from app.auth.jwt import decode_access_token
from app.database import get_db
from app.models.auth import RoleEnum, User


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    access_token: str | None = Cookie(default=None),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not access_token:
        raise credentials_exception

    try:
        payload = decode_access_token(access_token)
        user_id: str | None = payload.get("sub")
        user_id = UUID(user_id)
    except (JWTError, ValueError, TypeError, AttributeError):
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception
    validate_active_account(user)
    return user


def get_superadmin_user(current_user: User = Depends(get_current_user)) -> User:
    from app.models.auth import RoleEnum

    if current_user.role != RoleEnum.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough privileges (requires SUPER_ADMIN)",
        )
    return current_user


def validate_active_account(user):
    if not user.is_active:
        raise HTTPException(403, "La cuenta está inactiva.")
    if user.role == RoleEnum.SUPER_ADMIN:
        if user.tenant_id is not None:
            raise HTTPException(403, "Un superadministrador no puede pertenecer a una agencia.")
    elif not user.tenant or not user.tenant.is_active:
        raise HTTPException(403, "La agencia está inactiva.")


def get_agency_user(current_user: User = Depends(get_current_user)):
    from app.services.access import require_agency
    require_agency(current_user)
    return current_user
