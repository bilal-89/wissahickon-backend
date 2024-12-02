# app/core/security/__init__.py
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token, get_jwt_identity, jwt_required
from flask import g, current_app
from datetime import datetime
from typing import Optional


class SecurityMixin:
    @property
    def password(self):
        raise AttributeError("password is not a readable attribute")

    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(password)

    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)

    def generate_token(self):
        return create_access_token(identity=self.id)


def get_current_user_id() -> Optional[str]:
    """Get the current user ID from JWT token or context"""
    try:
        # First try to get from JWT
        user_id = get_jwt_identity()
        if user_id:
            return str(user_id)

        # Fallback to context (for testing/non-JWT routes)
        return getattr(g, "user_id", None)
    except Exception as e:
        current_app.logger.debug(f"Error getting current user: {str(e)}")
        return None


def set_current_user_id(user_id: str) -> None:
    """Set the current user ID in context (useful for testing)"""
    g.user_id = user_id


# Export all the components
__all__ = ["SecurityMixin", "get_current_user_id", "set_current_user_id"]
