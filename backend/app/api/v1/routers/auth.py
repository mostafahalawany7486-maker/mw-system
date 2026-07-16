from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import settings
from app.api.deps import get_current_user, get_client_ip
from app.schemas.auth import (
    LoginRequest, TokenResponse, RefreshRequest, ForgotPasswordRequest,
    ResetPasswordRequest, ChangePasswordRequest,
)
from app.schemas.user import UserMeOut
from app.schemas.common import MessageResponse
from app.services.auth_service import AuthService
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    service = AuthService(db)
    tokens = service.login(payload.email, payload.password, ip_address=get_client_ip(request))
    return tokens


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    return AuthService(db).refresh(payload.refresh_token)


@router.post("/logout", response_model=MessageResponse)
def logout(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    AuthService(db).logout(current_user, ip_address=get_client_ip(request))
    return {"message": "Logged out successfully"}


@router.post("/forgot-password", response_model=MessageResponse)
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    service = AuthService(db)
    token = service.forgot_password(payload.email)
    # Always return a generic success message so we never leak which emails
    # are registered. In development, include the raw token so testers can
    # complete the flow without a real mail server.
    if settings.APP_ENV == "development" and token:
        return {"message": f"If that email exists, a reset link has been sent. [DEV TOKEN: {token}]"}
    return {"message": "If that email exists, a password reset link has been sent."}


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    AuthService(db).reset_password(payload.token, payload.new_password)
    return {"message": "Password has been reset successfully. You may now log in."}


@router.post("/change-password", response_model=MessageResponse)
def change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    AuthService(db).change_password(current_user, payload.current_password, payload.new_password)
    return {"message": "Password changed successfully"}


@router.get("/me", response_model=UserMeOut)
def get_me(current_user: User = Depends(get_current_user)):
    permissions = ["*"] if current_user.is_superuser else (
        [p.code for p in current_user.role.permissions] if current_user.role else []
    )
    result = UserMeOut.model_validate(current_user)
    result.permissions = permissions
    return result
