# app/api/tenant/routes.py
from flask import Blueprint, jsonify, request, g
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.core.monitoring import capture_error
from app.extensions import db
from app.models import User, Tenant, Role, UserTenantRole
from app.core.errors import APIError
from app.core.permissions import require_permission
from app.core.constants import Permission
from app.core.audit import audit_action
import logging
from uuid import uuid4

logger = logging.getLogger(__name__)
tenant_bp = Blueprint("tenant", __name__)


@tenant_bp.route("", methods=["GET"])
@jwt_required()
@require_permission(Permission.VIEW_TENANT)
@audit_action("list", "tenants")
def list_tenants():
    """List tenants user belongs to"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        if not user:
            raise APIError("User not found", status_code=404)

        # Get only tenants where user has VIEW_TENANT permission
        tenant_roles = [
            tr
            for tr in user.tenant_roles
            if tr.role and Permission.VIEW_TENANT.value in tr.role.permissions
        ]

        primary_tenant_role = UserTenantRole.query.filter_by(
            user_id=user.id, is_primary=True
        ).first()

        # Only include primary tenant if user has VIEW_TENANT permission
        if (
            primary_tenant_role
            and Permission.VIEW_TENANT.value not in primary_tenant_role.role.permissions
        ):
            primary_tenant_role = None

        return jsonify(
            {
                "tenants": [tr.tenant.to_dict() for tr in tenant_roles],
                "primary_tenant": (
                    primary_tenant_role.tenant.to_dict() if primary_tenant_role else None
                ),
            }
        )

    except Exception as e:
        logger.exception("Error in list_tenants")
        raise APIError(str(e), status_code=500)


@tenant_bp.route("", methods=["POST"])
@jwt_required()
@capture_error
@require_permission(Permission.MANAGE_TENANT)
@audit_action("create", "tenant", lambda r: r.get_json().get("id"))
def create_tenant():
    """Create new tenant"""
    try:
        logger.info("Starting tenant creation process")

        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        if not user:
            logger.error(f"User {user_id} not found")
            raise APIError("User not found", status_code=404)

        data = request.get_json()
        if not data:
            logger.error("No data provided in request")
            raise APIError("No data provided", status_code=400)

        required_fields = ["name", "subdomain"]
        for field in required_fields:
            if field not in data:
                logger.error(f"Missing required field: {field}")
                raise APIError(f"Missing required field: {field}", status_code=400)

        existing_tenant = Tenant.query.filter_by(subdomain=data["subdomain"]).first()
        if existing_tenant:
            logger.error(f"Subdomain already exists: {data['subdomain']}")
            raise APIError("Subdomain already in use", status_code=400)

        try:
            tenant_id = str(uuid4())
            # Create new tenant
            new_tenant = Tenant(
                id=tenant_id,
                name=data["name"],
                subdomain=data["subdomain"],
                settings=data.get("settings", {}),
                is_active=True,
            )
            db.session.add(new_tenant)
            logger.info(f"Created tenant: {new_tenant.name}")

            # Create default roles including admin
            roles = Role.create_default_roles(new_tenant.id)
            logger.info("Created default roles")

            # Find admin role
            admin_role = next(role for role in roles if role.name == "admin")

            # Create user-tenant-role relationship
            user_role = UserTenantRole(
                id=str(uuid4()),
                user_id=user.id,
                tenant_id=new_tenant.id,
                role_id=admin_role.id,
                is_primary=not UserTenantRole.query.filter_by(
                    user_id=user.id, is_primary=True
                ).first(),
            )
            db.session.add(user_role)
            logger.info("Created user-tenant-role relationship")

            db.session.commit()
            logger.info(f"Successfully created tenant: {new_tenant.name}")

            return jsonify(new_tenant.to_dict()), 201

        except Exception as e:
            logger.exception("Database error during tenant creation")
            db.session.rollback()
            raise APIError(f"Error creating tenant: {str(e)}", status_code=500)

    except APIError:
        raise
    except Exception as e:
        logger.exception("Unexpected error in create_tenant")
        raise APIError(str(e), status_code=500)


@tenant_bp.route("/<tenant_id>", methods=["GET"])
@jwt_required()
@require_permission(Permission.VIEW_TENANT)
@audit_action("view", "tenant", lambda r: r.view_args.get("tenant_id"))
def get_tenant(tenant_id):
    """Get tenant details if user has access"""
    try:
        tenant = Tenant.query.get(tenant_id)
        if not tenant:
            raise APIError("Tenant not found", status_code=404)

        return jsonify(tenant.to_dict())

    except APIError:
        raise
    except Exception as e:
        logger.exception("Unexpected error in get_tenant")
        raise APIError(str(e), status_code=500)


@tenant_bp.route("/<tenant_id>/users", methods=["GET"])
@jwt_required()
@require_permission(Permission.VIEW_USERS)
@audit_action("list_users", "tenant", lambda r: r.view_args.get("tenant_id"))
def list_tenant_users(tenant_id):
    """List users in a tenant"""
    try:
        tenant = Tenant.query.get_or_404(tenant_id)
        tenant_users = UserTenantRole.query.filter_by(tenant_id=tenant.id).all()

        return jsonify({"users": [tr.user.to_dict() for tr in tenant_users]})

    except Exception as e:
        logger.exception("Error in list_tenant_users")
        raise APIError(str(e), status_code=500)


@tenant_bp.route("/<tenant_id>/roles", methods=["GET"])
@jwt_required()
@require_permission(Permission.VIEW_ROLES)
@audit_action("list_roles", "tenant", lambda r: r.view_args.get("tenant_id"))
def list_tenant_roles(tenant_id):
    """List roles in a tenant"""
    try:
        tenant = Tenant.query.get_or_404(tenant_id)
        roles = Role.query.filter_by(tenant_id=tenant.id).all()

        return jsonify({"roles": [role.to_dict() for role in roles]})

    except Exception as e:
        logger.exception("Error in list_tenant_roles")
        raise APIError(str(e), status_code=500)


@tenant_bp.route("/<tenant_id>/roles", methods=["POST"])
@jwt_required()
@capture_error
@require_permission(Permission.MANAGE_ROLES)
@audit_action("create_role", "tenant", lambda r: r.view_args.get("tenant_id"))
def create_tenant_role(tenant_id):
    """Create a new role in the tenant"""
    try:
        tenant = Tenant.query.get_or_404(tenant_id)
        data = request.get_json()

        if not data or not data.get("name"):
            raise APIError("Role name is required", status_code=400)

        # Check for existing role with same name
        existing_role = Role.get_role_by_name(tenant.id, data["name"])
        if existing_role:
            raise APIError("Role with this name already exists", status_code=400)

        # Create new role
        new_role = Role(
            id=str(uuid4()),
            tenant_id=tenant.id,
            name=data["name"],
            description=data.get("description"),
            permissions=data.get("permissions", {}),
        )
        db.session.add(new_role)
        db.session.commit()

        return jsonify(new_role.to_dict()), 201

    except APIError:
        raise
    except Exception as e:
        logger.exception("Error in create_tenant_role")
        raise APIError(str(e), status_code=500)
