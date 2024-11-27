# app/core/security/sanitization.py
from functools import wraps
from flask import request, abort, current_app
import bleach
import re
from typing import Dict, Any, Optional, List, Callable
import json


class RequestSanitizer:
    def __init__(self):
        self.max_content_length = 10 * 1024 * 1024  # 10MB default
        self.allowed_content_types = {
            'application/json',
            'multipart/form-data',
            'application/x-www-form-urlencoded',
            'text/plain'
        }
        self.allowed_tags = [
            'p', 'br', 'strong', 'em', 'u', 'ul', 'ol', 'li'
        ]

    def sanitize_string(self, value: str) -> str:
        """Sanitize a single string value."""
        if not isinstance(value, str):
            return str(value)
        value = value.replace('\x00', '')
        value = ''.join(char for char in value if char >= ' ' or char in '\n\t')
        return bleach.clean(value, tags=self.allowed_tags, strip=True)

    def validate_content_type(self, content_type: str) -> bool:
        """Validate that the content type is allowed."""
        if not content_type:
            return True
        base_content_type = content_type.split(';')[0].strip().lower()
        return base_content_type in self.allowed_content_types

    def validate_content_length(self, content_length: int) -> bool:
        """Validate that the content length is within limits."""
        if not content_length:
            return True
        return content_length <= self.max_content_length


def sanitize_request(exempt_paths: Optional[List[str]] = None):
    """Decorator to sanitize incoming requests."""
    sanitizer = RequestSanitizer()

    def decorator(f: Callable):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Check exemptions
            if exempt_paths:
                for path in exempt_paths:
                    if re.match(path, request.path):
                        return f(*args, **kwargs)

            if request.method in ['POST', 'PUT', 'PATCH']:
                # Validate content length
                content_length = request.content_length or 0
                if not sanitizer.validate_content_length(content_length):
                    abort(413, description="Request entity too large")

                # Validate content type
                content_type = request.headers.get('Content-Type', '')
                if not sanitizer.validate_content_type(content_type):
                    abort(415, description=f"Unsupported content type: {content_type}")

                # Handle JSON data
                if request.is_json:
                    try:
                        data = request.get_json()
                        if data:
                            def sanitize_data(obj):
                                if isinstance(obj, str):
                                    return sanitizer.sanitize_string(obj)
                                elif isinstance(obj, dict):
                                    return {k: sanitize_data(v) for k, v in obj.items()}
                                elif isinstance(obj, list):
                                    return [sanitize_data(item) for item in obj]
                                return obj

                            sanitized_data = sanitize_data(data)
                            request._cached_json = (sanitized_data, request._cached_json[1])
                    except json.JSONDecodeError:
                        abort(400, description="Invalid JSON")

                # Handle form data
                elif request.form:
                    sanitized_form = {
                        key: sanitizer.sanitize_string(value)
                        for key, value in request.form.items()
                    }
                    for key, value in sanitized_form.items():
                        request.form = request.form.copy()
                        request.form[key] = value

            return f(*args, **kwargs)

        return decorated_function

    return decorator