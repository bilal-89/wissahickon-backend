# tests/utils.py
from functools import wraps


def with_app_context(f):
    """Decorator to ensure app context is available"""

    @wraps(f)
    def decorated(test_app, *args, **kwargs):
        with test_app.app_context():
            return f(test_app, *args, **kwargs)

    return decorated
