# app/core/errors.py
from flask import jsonify
from .exceptions import PermissionDenied

class APIError(Exception):
    def __init__(self, message, status_code=400, payload=None):
        super().__init__()
        self.message = message
        self.status_code = status_code
        self.payload = payload

    def to_dict(self):
        rv = dict(self.payload or ())
        rv['message'] = self.message
        return rv

    def __str__(self):
        return self.message


def handle_api_error(error):
    """Handle APIError exceptions"""
    response = jsonify(error.to_dict())
    response.status_code = error.status_code
    return response


def handle_permission_denied(error):
    """Handle PermissionDenied exceptions"""
    response = jsonify({
        'message': str(error),
        'error': 'permission_denied'
    })
    response.status_code = 403
    return response


def register_error_handlers(app):
    """Register error handlers with the Flask app"""
    app.register_error_handler(APIError, handle_api_error)
    app.register_error_handler(PermissionDenied, handle_permission_denied)