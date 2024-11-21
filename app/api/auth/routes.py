# app/api/auth/routes.py
from flask import Blueprint, request, jsonify
from app.extensions import db
from app.models.user import User
from app.core.errors import APIError
from flask_jwt_extended import create_access_token, get_jwt_identity, jwt_required
from datetime import timedelta

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()

    if not data or not data.get('email') or not data.get('password'):
        raise APIError('Missing email or password', status_code=400)

    user = User.query.filter_by(email=data['email']).first()

    if not user or not user.verify_password(data['password']):
        raise APIError('Invalid email or password', status_code=401)

    if not user.is_active:
        raise APIError('Account is deactivated', status_code=403)

    # Create access token
    access_token = create_access_token(
        identity=user.id,
        additional_claims={
            'email': user.email,
            'role': user.role.name if user.role else None,
            'tenant_id': user.tenant_id
        },
        expires_delta=timedelta(hours=1)
    )

    # Update last login
    user.update_last_login()

    return jsonify({
        'token': access_token,
        'user': user.to_dict()
    })


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