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
from fastapi import Cookie, Depends, HTTPException, Request, status
from jose import JWTError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.auth import User
from app.auth.jwt import decode_access_token


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
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return user


def get_superadmin_user(current_user: User = Depends(get_current_user)) -> User:
    from app.models.auth import RoleEnum

    if current_user.role != RoleEnum.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough privileges (requires SUPER_ADMIN)",
        )
    return current_user
