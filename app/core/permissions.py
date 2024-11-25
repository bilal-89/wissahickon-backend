# app/core/permissions.py
from functools import wraps
from flask import g
from flask_jwt_extended import get_jwt_identity
from app.models import User
from app.core.exceptions import PermissionDenied
from app.core.constants import Permission


def require_permission(permission):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user_id = get_jwt_identity()
            user = User.query.get(user_id)
            tenant = g.tenant

            role = user.get_role_for_tenant(tenant)
            if not role or not role.has_permission(permission):
                raise PermissionDenied(
                    f"User does not have required permission: {permission}"
                )

            return f(*args, **kwargs)

        return decorated_function

    return decorator