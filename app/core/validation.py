# app/core/validation.py
from functools import wraps
from flask import request, jsonify
import re
from typing import Dict, Any, Optional, Callable


class RequestValidator:
    """Basic request validation middleware"""

    @staticmethod
    def validate_json(schema: Dict[str, Any]) -> Callable:
        """Decorator for validating JSON request data"""

        def decorator(f: Callable) -> Callable:
            @wraps(f)
            def wrapped(*args, **kwargs):
                if not request.is_json:
                    return jsonify({'error': 'Content-Type must be application/json'}), 400

                data = request.get_json()

                # Validate required fields and types
                for field, field_schema in schema.items():
                    field_type = field_schema.get('type')
                    required = field_schema.get('required', False)
                    pattern = field_schema.get('pattern')
                    max_length = field_schema.get('max_length')
                    min_length = field_schema.get('min_length')

                    # Check required fields
                    if required and field not in data:
                        return jsonify({
                            'error': f'Missing required field: {field}'
                        }), 400

                    # Skip further validation if field is not present and not required
                    if field not in data:
                        continue

                    value = data[field]

                    # Type validation
                    if field_type and not isinstance(value, field_type):
                        return jsonify({
                            'error': f'Invalid type for field {field}. Expected {field_type.__name__}'
                        }), 400

                    # String-specific validations
                    if isinstance(value, str):
                        # Pattern validation
                        if pattern and not re.match(pattern, value):
                            return jsonify({
                                'error': f'Invalid format for field {field}'
                            }), 400

                        # Length validation
                        if max_length and len(value) > max_length:
                            return jsonify({
                                'error': f'Field {field} exceeds maximum length of {max_length}'
                            }), 400

                        if min_length and len(value) < min_length:
                            return jsonify({
                                'error': f'Field {field} is shorter than minimum length of {min_length}'
                            }), 400

                return f(*args, **kwargs)

            return wrapped

        return decorator

    @staticmethod
    def sanitize_string(value: str, max_length: Optional[int] = None) -> str:
        """Sanitize a string value while preserving newlines"""
        # Convert tabs to spaces and preserve newlines
        value = value.replace('\t', ' ')

        # Remove control characters except newlines
        value = ''.join(char for char in value if ord(char) >= 32 or char == '\n')

        # Normalize whitespace while preserving newlines
        lines = value.split('\n')
        lines = [line.strip() for line in lines]
        value = '\n'.join(lines)

        # Apply length limit if specified
        if max_length:
            value = value[:max_length]

        return value


# Example usage in a route
"""
@app.route('/api/user', methods=['POST'])
@RequestValidator.validate_json({
    'email': {
        'type': str,
        'required': True,
        'pattern': r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
        'max_length': 255
    },
    'name': {
        'type': str,
        'required': True,
        'max_length': 100,
        'min_length': 2
    },
    'age': {
        'type': int,
        'required': False
    }
})
def create_user():
    data = request.get_json()
    # Data is already validated here
    return jsonify({'status': 'success'})
"""