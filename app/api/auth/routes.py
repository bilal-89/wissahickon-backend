# app/api/auth/routes.py
from flask import Blueprint, request, jsonify
from app.extensions import db
from app.models.user import User
from app.core.errors import APIError
from flask_jwt_extended import create_access_token, get_jwt_identity, jwt_required
from datetime import timedelta
from google.oauth2 import id_token
from google.auth.transport import requests
from app.core.errors import APIError
import os
from .google import verify_google_token
import logging

logger = logging.getLogger(__name__)


auth_bp = Blueprint('auth', __name__)
print("Auth blueprint created:", auth_bp.url_prefix)  # Debug print

@auth_bp.route('/login', methods=['POST'])
def login():
    logger.info("Login endpoint hit")
    try:
        data = request.get_json()
        logger.info(f"Received data: {data}")

        if not data:
            logger.error("No JSON data received")
            raise APIError('No data provided', status_code=400)

        if not data.get('email') or not data.get('password'):
            logger.error("Missing email or password")
            raise APIError('Missing email or password', status_code=400)

        user = User.query.filter_by(email=data['email']).first()
        logger.info(f"Found user: {user}")

        if not user:
            logger.error(f"No user found with email: {data['email']}")
            raise APIError('Invalid email or password', status_code=401)

        if not user.verify_password(data['password']):
            logger.error("Invalid password")
            raise APIError('Invalid email or password', status_code=401)

        token = create_access_token(
            identity=user.id,
            additional_claims={
                'email': user.email,
                'role': user.role.name if user.role else None,
                'tenant_id': user.tenant_id
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
def google_auth():
    data = request.get_json()

    if not data or not data.get('token'):
        raise APIError('Missing Google token', status_code=400)

    # Verify Google token and get user info
    try:
        google_user = verify_google_token(data['token'])

        # Find existing user or create new one
        user = User.query.filter_by(google_id=google_user['sub']).first()
        if not user:
            user = User(
                email=google_user['email'],
                google_id=google_user['sub'],
                first_name=google_user.get('given_name'),
                last_name=google_user.get('family_name'),
                is_active=True
            )
            db.session.add(user)
            db.session.commit()

        # Create access token
        access_token = create_access_token(
            identity=user.id,
            additional_claims={
                'email': user.email,
                'role': user.role.name if user.role else None,
                'tenant_id': user.tenant_id
            }
        )

        user.update_last_login()

        return jsonify({
            'token': access_token,
            'user': user.to_dict()
        })

    except Exception as e:
        raise APIError('Invalid Google token', status_code=401)


@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)

    if not user:
        raise APIError('User not found', status_code=404)

    return jsonify(user.to_dict())


# Helper function for Google token verification
def verify_google_token(token):
    # Implementation needed - will add Google OAuth verification
    pass

