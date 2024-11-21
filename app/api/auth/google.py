# app/api/auth/google.py
from google.oauth2 import id_token
from google.auth.transport import requests
from app.core.errors import APIError
import os


def verify_google_token(token):
    try:
        # Get client ID from environment or config
        client_id = os.getenv('GOOGLE_CLIENT_ID')
        if not client_id:
            raise APIError('Google OAuth not configured', status_code=500)

        # Verify the token
        idinfo = id_token.verify_oauth2_token(
            token,
            requests.Request(),
            client_id
        )

        # Verify issuer
        if idinfo['iss'] not in ['accounts.google.com', 'https://accounts.google.com']:
            raise ValueError('Wrong issuer.')

        # Return relevant user info
        return {
            'sub': idinfo['sub'],  # Google's unique user identifier
            'email': idinfo['email'],
            'email_verified': idinfo['email_verified'],
            'given_name': idinfo.get('given_name'),
            'family_name': idinfo.get('family_name'),
            'picture': idinfo.get('picture')
        }

    except ValueError:
        raise APIError('Invalid token', status_code=401)