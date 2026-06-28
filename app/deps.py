"""Authentication / authorization dependencies."""
from __future__ import annotations

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .database import get_db
from .errors import AppError
from .models import Role, User
from .security import decode_access_token

_bearer = HTTPBearer(auto_error=False, description="JWT access token from /auth/login")


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    if creds is None or not creds.credentials:
        raise AppError(401, "unauthorized", "Authentication required.")

    try:
        payload = decode_access_token(creds.credentials)
    except jwt.ExpiredSignatureError as exc:
        raise AppError(401, "token_expired", "Your session has expired. Please log in again.") from exc
    except jwt.PyJWTError as exc:
        raise AppError(401, "invalid_token", "Invalid authentication token.") from exc

    raw_id = payload.get("sub")
    try:
        user_id = int(raw_id)
    except (TypeError, ValueError) as exc:
        raise AppError(401, "invalid_token", "Invalid authentication token.") from exc

    user = db.get(User, user_id)
    if user is None:
        raise AppError(401, "invalid_token", "Invalid authentication token.")
    return user


def require_role(*roles: Role):
    """Dependency factory enforcing that the current user holds one of ``roles``."""

    def _dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise AppError(403, "forbidden", "You do not have permission to perform this action.")
        return user

    return _dependency
