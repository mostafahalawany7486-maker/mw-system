"""
Authentication business logic: login with lockout protection, token
issuance/refresh, forgot/reset password flow, change password.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import (
    verify_password, hash_password, create_access_token, create_refresh_token,
    create_password_reset_token, decode_token,
)
from app.repositories.user_repository import UserRepository
from app.models.user import User
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 15


class AuthService:
    def __init__(self, db: Session):
        self.db = db
        self.user_repo = UserRepository(db)
        self.audit = AuditService(db)
        self.notifications = NotificationService(db)

    def _build_tokens(self, user: User) -> dict:
        permissions = []
        role_name = user.role.name if user.role else None
        if user.role:
            permissions = [p.code for p in user.role.permissions]
        if user.is_superuser:
            permissions = ["*"]
        access = create_access_token(str(user.id), role_name or "", permissions)
        refresh = create_refresh_token(str(user.id))
        return {"access_token": access, "refresh_token": refresh, "token_type": "bearer"}

    def login(self, email: str, password: str, ip_address: Optional[str] = None) -> dict:
        user = self.user_repo.get_by_email(email)
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

        if user.locked_until and user.locked_until > datetime.now(timezone.utc).replace(tzinfo=user.locked_until.tzinfo):
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail=f"Account locked due to too many failed attempts. Try again after {user.locked_until.isoformat()}.",
            )

        if not user.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is inactive. Contact your administrator.")

        if not verify_password(password, user.hashed_password):
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= MAX_FAILED_ATTEMPTS:
                user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_MINUTES)
                self.audit.log_activity("user", user.id, "account_locked", f"{user.email} locked after {MAX_FAILED_ATTEMPTS} failed attempts", None)
            self.db.commit()
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

        # Success: reset failed attempts, record login
        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_login_at = datetime.now(timezone.utc)
        self.audit.log_activity("user", user.id, "login", f"{user.email} logged in", user.id)
        self.audit.log_audit("user", user.id, "login", None, user.id, ip_address=ip_address)
        self.db.commit()

        return self._build_tokens(user)

    def refresh(self, refresh_token: str) -> dict:
        payload = decode_token(refresh_token)
        if not payload or payload.get("type") != "refresh":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")
        user = self.user_repo.get_with_role(int(payload["sub"]))
        if not user or not user.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
        return self._build_tokens(user)

    def logout(self, user: User, ip_address: Optional[str] = None) -> None:
        # Stateless JWT: logout is enforced client-side (token discard). We still
        # record it for the activity/audit trail. A future phase can add a
        # server-side token blocklist (Redis) for immediate revocation.
        self.audit.log_activity("user", user.id, "logout", f"{user.email} logged out", user.id)
        self.audit.log_audit("user", user.id, "logout", None, user.id, ip_address=ip_address)
        self.db.commit()

    def forgot_password(self, email: str) -> Optional[str]:
        user = self.user_repo.get_by_email(email)
        if not user:
            # Do not reveal whether the email exists
            return None
        token = create_password_reset_token(str(user.id))
        self.notifications.notify(
            recipient_id=user.id,
            title="Password Reset Requested",
            message="A password reset was requested for your account. If this wasn't you, contact your administrator.",
            notification_type="warning",
        )
        self.audit.log_activity("user", user.id, "password_reset_requested", f"Password reset requested for {user.email}", None)
        self.db.commit()
        # In production this token is emailed, never returned via API. Phase 1
        # returns it only when APP_ENV=development to allow manual testing.
        return token

    def reset_password(self, token: str, new_password: str) -> None:
        payload = decode_token(token)
        if not payload or payload.get("type") != "password_reset":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token")
        user = self.user_repo.get(int(payload["sub"]))
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        user.hashed_password = hash_password(new_password)
        user.failed_login_attempts = 0
        user.locked_until = None
        self.audit.log_activity("user", user.id, "password_reset", f"Password reset for {user.email}", None)
        self.db.commit()

    def change_password(self, user: User, current_password: str, new_password: str) -> None:
        if not verify_password(current_password, user.hashed_password):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")
        user.hashed_password = hash_password(new_password)
        self.audit.log_activity("user", user.id, "password_changed", f"{user.email} changed their password", user.id)
        self.db.commit()
