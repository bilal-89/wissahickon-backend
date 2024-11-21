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
    logger.info("Google auth request received")

    if not data or not data.get('token'):
        logger.error("No token provided")
        raise APIError('Missing Google token', status_code=400)

    try:
        # Log token prefix for debugging
        token = data['token']
        logger.info(f"Token prefix: {token[:50]}...")

        # Verify Google token
        google_user = verify_google_token(token)
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

        # Create access token
        access_token = create_access_token(
            identity=user.id,
            additional_claims={
                'email': user.email,
                'role': user.role.name if user.role else None,
                'tenant_id': user.tenant_id
            }
        )

        return jsonify({
            'token': access_token,
            'user': user.to_dict()
        })

    except Exception as e:
        logger.exception("Error in google_auth")
        raise APIError(str(e), status_code=401)


@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)

    if not user:
        raise APIError('User not found', status_code=404)

    return jsonify(user.to_dict())


def verify_google_token(token):
    try:
        client_id = os.getenv('GOOGLE_CLIENT_ID')
        logger.info(f"Using client ID: {client_id}")

        idinfo = id_token.verify_oauth2_token(
            token,
            requests.Request(),
            client_id,
            clock_skew_in_seconds=10
        )

        logger.info(f"Token verification successful for email: {idinfo.get('email')}")

        if idinfo['iss'] not in ['accounts.google.com', 'https://accounts.google.com']:
            raise ValueError('Wrong issuer.')

        return {
            'sub': idinfo['sub'],
            'email': idinfo['email'],
            'email_verified': idinfo.get('email_verified'),
            'given_name': idinfo.get('given_name'),
            'family_name': idinfo.get('family_name'),
            'picture': idinfo.get('picture')
        }

    except Exception as e:
        logger.error(f"Token verification failed: {str(e)}")
        raise APIError(f'Token verification failed: {str(e)}', status_code=401)