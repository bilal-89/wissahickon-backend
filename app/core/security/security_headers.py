from functools import wraps
from flask import make_response, current_app


class SecurityHeaders:
    """Middleware to add security headers to all responses"""

    @staticmethod
    def init_app(app):
        """Initialize security headers for the application"""

        @app.after_request
        def add_security_headers(response):
            # Protect against clickjacking attacks
            response.headers["X-Frame-Options"] = "SAMEORIGIN"

            # Help prevent XSS attacks
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-XSS-Protection"] = "1; mode=block"

            # Strict Transport Security (only in production)
            if not current_app.debug:
                response.headers["Strict-Transport-Security"] = (
                    "max-age=31536000; includeSubDomains"
                )

            # Content Security Policy
            # Customize these directives based on your needs
            csp = (
                "default-src 'self'; "
                "script-src 'self' https://cdnjs.cloudflare.com; "
                "style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; "
                "img-src 'self' data: https:; "
                "connect-src 'self' https://*.your-api-domain.com; "
                "frame-ancestors 'none'; "
                "form-action 'self'"
            )
            response.headers["Content-Security-Policy"] = csp

            # Referrer Policy
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

            # Permissions Policy (formerly Feature-Policy)
            response.headers["Permissions-Policy"] = (
                "geolocation=(), " "microphone=(), " "camera=()"
            )

            return response


def init_security_headers(app):
    """Initialize security headers for the application"""
    SecurityHeaders.init_app(app)
