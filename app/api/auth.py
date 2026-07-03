"""Authentication routes."""
import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)
from app.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.schemas.learning_coach import AuthRequest, RefreshRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["Auth"])


def _raise_auth_db_error(exc: Exception) -> None:
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Authentication database error: {exc}",
    ) from exc


@router.post("/register")
def register(body: AuthRequest, db: Session = Depends(get_db)):
    try:
        if db.query(User).filter(User.username == body.username).first():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already exists")
        user = User(username=body.username, password_hash=hash_password(body.password))
        db.add(user)
        db.commit()
        db.refresh(user)
        return {"message": "Registered successfully", "username": user.username, "user_id": user.id}
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        _raise_auth_db_error(exc)


@router.post("/login", response_model=TokenResponse)
def login(body: AuthRequest, db: Session = Depends(get_db)):
    try:
        user = db.query(User).filter(User.username == body.username).first()
        if not user or not verify_password(body.password, user.password_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")
        return TokenResponse(
            access_token=create_access_token(user.username, user.id),
            refresh_token=create_refresh_token(user.username, user.id),
        )
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        _raise_auth_db_error(exc)


@router.post("/refresh", response_model=TokenResponse)
def refresh(body: RefreshRequest, db: Session = Depends(get_db)):
    try:
        try:
            payload = decode_refresh_token(body.refresh_token)
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

        raw_user_id = payload.get("uid")
        try:
            user_id = int(raw_user_id) if raw_user_id is not None else None
        except (TypeError, ValueError):
            user_id = None
        username = payload.get("sub")
        user = db.query(User).filter(User.id == user_id).first() if user_id is not None else None
        if user is None and username:
            user = db.query(User).filter(User.username == username).first()
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found, please login again")

        return TokenResponse(
            access_token=create_access_token(user.username, user.id),
            refresh_token=create_refresh_token(user.username, user.id),
        )
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        _raise_auth_db_error(exc)


@router.get("/me")
def me(current_user: User = Depends(get_current_user)):
    return {"user_id": current_user.id, "username": current_user.username}
