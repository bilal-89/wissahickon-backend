from flask import Blueprint, request, jsonify, g
from app.extensions import db
from app.models.user import User
from app.models.tenant import Tenant
from app.models.role import Role  # Add this import

from app.core.errors import APIError
from flask_jwt_extended import create_access_token, get_jwt_identity, jwt_required
from datetime import datetime
from .google import verify_google_token
import logging
from app.core.middleware import TenantMiddleware
from ...core.monitoring import capture_error

logger = logging.getLogger(__name__)
auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['POST'])
@capture_error
@TenantMiddleware.tenant_required
def login():
    logger.info("Login endpoint hit")
    try:
        data = request.get_json()
        logger.info(f"Received data: {data}")

        if not data or not data.get('email') or not data.get('password'):
            logger.error("Missing email or password")
            raise APIError('Missing email or password', status_code=400)

        # First try to find user in current tenant
        user = User.query.filter_by(email=data['email']).first()

        if not user:
            logger.error(f"No user found with email: {data['email']}")
            raise APIError('Invalid email or password', status_code=401)

        if not user.verify_password(data['password']):
            logger.error("Invalid password")
            raise APIError('Invalid email or password', status_code=401)

        if not user.is_active:
            logger.error("User is inactive")
            raise APIError('Account is inactive', status_code=401)

        # Check if user has role in current tenant
        tenant_role = user.get_role_for_tenant(g.tenant)
        if not tenant_role:
            logger.error(f"User has no role in tenant: {g.tenant.subdomain}")
            raise APIError('No access to this tenant', status_code=403)

        # Update last login
        user.update_last_login()

        # Get or set primary tenant role if none exists
        if not user.primary_tenant_role:
            user.add_tenant_role(g.tenant, tenant_role, is_primary=True)

        token = create_access_token(
            identity=user.id,
            additional_claims={
                'email': user.email,
                'tenant_id': g.tenant.id,
                'tenant_subdomain': g.tenant.subdomain,
                'role': tenant_role.name
            }
        )
        logger.info("Token created successfully")

        return jsonify({
            'token': token,
            'user': user.to_dict()
        })

    except Exception as e:
        logger.exception("Error in login endpoint")
        raise


@auth_bp.route('/google', methods=['POST'])
@capture_error
@TenantMiddleware.tenant_required
def google_auth():
    logger.info("Google auth request received")
    data = request.get_json()

    if not data or not data.get('token'):
        logger.error("No token provided")
        raise APIError('Missing Google token', status_code=400)

    try:
        google_user = verify_google_token(data['token'])
        logger.info(f"Google user verified: {google_user.get('email')}")

        # Find or create user
        user = User.query.filter_by(google_id=google_user['sub']).first()

        if not user:
            logger.info(f"Creating new user for {google_user.get('email')}")
            user = User(
                email=google_user['email'],
                google_id=google_user['sub'],
                first_name=google_user.get('given_name'),
                last_name=google_user.get('family_name'),
                is_active=True
            )
            db.session.add(user)
            db.session.commit()

        # Check or create tenant role
        tenant_role = user.get_role_for_tenant(g.tenant)
        if not tenant_role:
            # You might want to add logic here to determine the appropriate role
            default_role = Role.query.filter_by(name='user', tenant_id=g.tenant.id).first()
            if default_role:
                user.add_tenant_role(g.tenant, default_role, is_primary=not bool(user.primary_tenant_role))

        user.update_last_login()

        token = create_access_token(
            identity=user.id,
            additional_claims={
                'email': user.email,
                'tenant_id': g.tenant.id,
                'tenant_subdomain': g.tenant.subdomain,
                'role': tenant_role.name if tenant_role else None
            }
        )

        return jsonify({
            'token': token,
            'user': user.to_dict()
        })

    except Exception as e:
        logger.exception("Error in google_auth")
        raise APIError(str(e), status_code=401)


@auth_bp.route('/me', methods=['GET'])
@jwt_required()
@TenantMiddleware.tenant_required
def get_current_user():
    user_id = get_jwt_identity()
    user = User.query.get_or_404(user_id)

    # Verify user has access to current tenant
    tenant_role = user.get_role_for_tenant(g.tenant)
    if not tenant_role:
        raise APIError('No access to this tenant', status_code=403)

    return jsonify(user.to_dict())


@auth_bp.route('/switch-tenant', methods=['POST'])
@jwt_required()
def switch_tenant():
    """Switch user's primary tenant"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()

        if not data or not data.get('tenant_id'):
            raise APIError('tenant_id is required', status_code=400)

        user = User.query.get_or_404(user_id)
        new_tenant = Tenant.query.get_or_404(data['tenant_id'])

        user.switch_primary_tenant(new_tenant)

        # Create new token with updated tenant info
        tenant_role = user.get_role_for_tenant(new_tenant)
        token = create_access_token(
            identity=user.id,
            additional_claims={
                'email': user.email,
                'tenant_id': new_tenant.id,
                'tenant_subdomain': new_tenant.subdomain,
                'role': tenant_role.name if tenant_role else None
            }
        )

        return jsonify({
            'token': token,
            'user': user.to_dict()
        })

    except Exception as e:
        logger.exception("Error in switch_tenant")
        raise APIError(str(e), status_code=400)