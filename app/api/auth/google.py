# app/api/auth/google.py
from google.oauth2 import id_token
from google.auth.transport import requests
from app.core.errors import APIError
import os
import logging

logger = logging.getLogger(__name__)

def verify_google_token(token):
    try:
        client_id = os.getenv('GOOGLE_CLIENT_ID')
        logger.info(f"Using client ID: {client_id}")
        if not client_id:
            raise APIError('Google OAuth not configured', status_code=500)

        try:
            idinfo = id_token.verify_oauth2_token(
                token,
                requests.Request(),
                client_id
            )
            logger.info(f"Token info received: {idinfo.get('email')}")
        except Exception as e:
            logger.error(f"Token verification failed: {str(e)}")
            raise ValueError(f"Token verification failed: {str(e)}")

        if idinfo['iss'] not in ['accounts.google.com', 'https://accounts.google.com']:
            logger.error(f"Invalid issuer: {idinfo['iss']}")
            raise ValueError('Wrong issuer.')

        return {
            'sub': idinfo['sub'],
            'email': idinfo['email'],
            'email_verified': idinfo['email_verified'],
            'given_name': idinfo.get('given_name'),
            'family_name': idinfo.get('family_name'),
            'picture': idinfo.get('picture')
        }

    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        raise APIError(f'Invalid token: {str(e)}', status_code=401)
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise APIError(f'Authentication failed: {str(e)}', status_code=500)