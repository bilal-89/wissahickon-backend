# app/api/user/routes.py
from flask import jsonify, request, g
from flask_jwt_extended import jwt_required
from app.extensions import db
from app.models import User, Role, UserTenantRole
from app.core.errors import APIError
from app.core.permissions import require_permission
from app.core.constants import Permission
from app.core.middleware import TenantMiddleware
from app.core.audit import audit_action
import logging
from uuid import uuid4
from . import user_bp
from ...core.monitoring import capture_error

logger = logging.getLogger(__name__)


@user_bp.route("", methods=["GET"])
@jwt_required()
@TenantMiddleware.tenant_required
@require_permission(Permission.VIEW_USERS)
@audit_action("list", "users")
def list_users():
    """List users in current tenant with filtering options"""
    try:
        # Get query parameters
        role_id = request.args.get("role")
        is_active = request.args.get("is_active", "true").lower() == "true"
        page = int(request.args.get("page", 1))
        per_page = min(int(request.args.get("per_page", 20)), 100)

        # Base query for current tenant
        query = UserTenantRole.query.filter_by(tenant_id=g.tenant.id)

        # Apply filters
        if role_id:
            query = query.filter_by(role_id=role_id)

        # Get paginated results
        pagination = query.paginate(page=page, per_page=per_page)

        return jsonify(
            {
                "users": [tr.user.to_dict() for tr in pagination.items],
                "total": pagination.total,
                "pages": pagination.pages,
                "current_page": page,
            }
        )

    except Exception as e:
        logger.exception("Error in list_users")
        raise APIError(str(e), status_code=500)


@user_bp.route("", methods=["POST"])
@jwt_required()
@TenantMiddleware.tenant_required
@require_permission(Permission.MANAGE_USERS)
@audit_action("create", "user", lambda r: r.get_json().get("id"))
def create_user():
    """Create new user in current tenant"""
    try:
        data = request.get_json()

        # Validate required fields
        required_fields = ["email", "first_name", "last_name", "role_id"]
        for field in required_fields:
            if field not in data:
                raise APIError(f"Missing required field: {field}", status_code=400)

        # Check if email already exists (Using 2.0 syntax)
        existing_user = db.session.execute(
            db.select(User).filter_by(email=data["email"])
        ).scalar_one_or_none()

        if existing_user:
            raise APIError("Email already exists", status_code=400)

        # Create user
        user_id = str(uuid4())
        new_user = User(
            id=user_id,
            email=data["email"],
            first_name=data["first_name"],
            last_name=data["last_name"],
        )

        # Set password if provided
        if "password" in data:
            new_user.password = data["password"]
        else:
            # Generate random temporary password
            temp_password = str(uuid4())
            new_user.password = temp_password
            # TODO: Send email with temporary password

        db.session.add(new_user)

        # Create user-tenant-role relationship
        user_role = UserTenantRole(
            id=str(uuid4()),
            user_id=new_user.id,
            tenant_id=g.tenant.id,
            role_id=data["role_id"],
            is_primary=True,
        )
        db.session.add(user_role)

        db.session.commit()

        return jsonify(new_user.to_dict()), 201

    except Exception as e:
        logger.exception("Error in create_user")
        db.session.rollback()
        raise APIError(str(e), status_code=500)


@user_bp.route("/<user_id>", methods=["GET"])
@jwt_required()
@TenantMiddleware.tenant_required
@require_permission(Permission.VIEW_USERS)
@audit_action("view", "user", lambda r: r.view_args.get("user_id"))
def get_user(user_id):
    """Get user details"""
    try:
        # Get user-tenant relationship (Using 2.0 syntax)
        user_role = db.session.execute(
            db.select(UserTenantRole).filter_by(user_id=user_id, tenant_id=g.tenant.id)
        ).scalar_one_or_none()

        if not user_role:
            raise APIError("User not found", status_code=404)

        return jsonify(user_role.user.to_dict())

    except Exception as e:
        logger.exception("Error in get_user")
        raise APIError(str(e), status_code=500)


@user_bp.route("/<user_id>", methods=["PUT"])
@jwt_required()
@TenantMiddleware.tenant_required
@capture_error
@require_permission(Permission.MANAGE_USERS)
@audit_action("update", "user", lambda r: r.view_args.get("user_id"))
def update_user(user_id):
    """Update user details"""
    try:
        # Get user-tenant relationship (Using 2.0 syntax)
        user_role = db.session.execute(
            db.select(UserTenantRole).filter_by(user_id=user_id, tenant_id=g.tenant.id)
        ).scalar_one_or_none()

        if not user_role:
            raise APIError("User not found", status_code=404)

        data = request.get_json()
        user = user_role.user

        # Update allowed fields
        allowed_fields = ["first_name", "last_name", "is_active"]
        for field in allowed_fields:
            if field in data:
                setattr(user, field, data[field])

        db.session.commit()

        return jsonify(user.to_dict())

    except Exception as e:
        logger.exception("Error in update_user")
        db.session.rollback()
        raise APIError(str(e), status_code=500)


@user_bp.route("/<user_id>/role", methods=["PUT"])
@jwt_required()
@TenantMiddleware.tenant_required
@require_permission(Permission.MANAGE_USERS)
@audit_action("update_role", "user", lambda r: r.view_args.get("user_id"))
def update_user_role(user_id):
    """Update user's role in current tenant"""
    try:
        data = request.get_json()
        if not data:
            raise APIError("No data provided", status_code=400)

        if "role_id" not in data:
            raise APIError("role_id is required", status_code=400)

        # Get user-tenant relationship
        user_role = db.session.execute(
            db.select(UserTenantRole).filter_by(user_id=user_id, tenant_id=g.tenant.id)
        ).scalar_one_or_none()

        if not user_role:
            logger.error(
                f"User-tenant relationship not found. User: {user_id}, Tenant: {g.tenant.id}"
            )
            raise APIError("User not found in current tenant", status_code=404)

        # Verify new role exists and belongs to current tenant
        new_role = db.session.execute(
            db.select(Role).filter_by(id=data["role_id"], tenant_id=g.tenant.id)
        ).scalar_one_or_none()

        if not new_role:
            logger.error(f"Role not found. Role ID: {data['role_id']}, Tenant: {g.tenant.id}")
            raise APIError("Role not found in current tenant", status_code=404)

        # Update role
        user_role.role_id = new_role.id
        db.session.commit()

        return jsonify(user_role.user.to_dict())

    except Exception as e:
        logger.exception("Error in update_user_role")
        db.session.rollback()
        if isinstance(e, APIError):
            raise
        raise APIError(str(e), status_code=500)
