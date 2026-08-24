from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import get_db
from app.db.models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def get_current_user_optional(
    token: str | None = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User | None:
    if not token:
        return None
    user_id = decode_access_token(token)
    if not user_id:
        return None
    return db.query(User).filter(User.id == user_id).first()


def get_current_user(
    user: User | None = Depends(get_current_user_optional),
) -> User:
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user
