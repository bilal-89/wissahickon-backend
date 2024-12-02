from functools import wraps
from flask import request, g, current_app, abort, Response
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import time
import logging
import re
from typing import Optional, Callable, Any
from datetime import datetime

from app.models import Tenant
from app.core.exceptions import (
    TenantNotFoundError,
    InactiveTenantError,
    RateLimitExceededError,
    SecurityViolationError,
)

logger = logging.getLogger(__name__)

# Initialize rate limiter
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="redis://localhost:6379",  # Should come from config
)


class SecurityMiddleware:
    """Security middleware for request validation and protection"""

    ALLOWED_CONTENT_TYPES = {"application/json", "multipart/form-data"}
    BLOCKED_CHARACTERS = re.compile(r"[<>]")
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10MB

    @staticmethod
    def validate_request() -> Optional[Response]:
        """Validate incoming request for security concerns"""
        # Check content length
        content_length = request.content_length or 0
        if content_length > SecurityMiddleware.MAX_CONTENT_LENGTH:
            return abort(413, "Request entity too large")

        # Validate content type for POST/PUT/PATCH
        if request.method in {"POST", "PUT", "PATCH"}:
            content_type = request.content_type or ""
            if not any(
                allowed in content_type for allowed in SecurityMiddleware.ALLOWED_CONTENT_TYPES
            ):
                return abort(415, "Unsupported content type")

        # Check for malicious characters in URL
        if SecurityMiddleware.BLOCKED_CHARACTERS.search(request.path):
            return abort(400, "Invalid characters in request URL")

        return None

    @staticmethod
    def security_headers(response: Response) -> Response:
        """Add security headers to response"""
        headers = {
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "SAMEORIGIN",
            "X-XSS-Protection": "1; mode=block",
            "Content-Security-Policy": "default-src 'self'",
            "Referrer-Policy": "strict-origin-when-cross-origin",
        }

        for key, value in headers.items():
            response.headers[key] = value

        return response


class MetricsMiddleware:
    """Middleware for collecting request metrics"""

    @staticmethod
    def start_timer() -> None:
        g.start_time = time.time()

    @staticmethod
    def record_metrics(response) -> None:
        if hasattr(g, "start_time"):
            elapsed_time = time.time() - g.start_time
            tenant = getattr(g, "tenant", None)
            tenant_id = tenant.id if tenant else None

            # Handle tuple responses (common in Flask for (response, status_code))
            if isinstance(response, tuple):
                status_code = response[1] if len(response) > 1 else 200
                content_length = len(str(response[0])) if response[0] else 0
            else:
                status_code = response.status_code
                content_length = response.content_length or 0

            logger.info(
                "Request metrics",
                extra={
                    "method": request.method,
                    "path": request.path,
                    "status_code": status_code,
                    "tenant_id": tenant_id,
                    "elapsed_time": elapsed_time,
                    "content_length": content_length,
                    "user_agent": request.user_agent.string,
                    "remote_addr": request.remote_addr,
                },
            )


class TenantMiddleware:
    """Enhanced tenant middleware with security and monitoring"""

    @staticmethod
    def get_tenant_from_request() -> Optional[Tenant]:
        """Extract and validate tenant from request with enhanced logging"""
        try:
            if current_app.debug:
                # Development tenant resolution
                tenant_id = request.headers.get("X-Tenant-ID")
                if tenant_id:
                    tenant = Tenant.query.get(tenant_id)
                    if tenant:
                        logger.debug(f"Development tenant resolved from header: {tenant.id}")
                        return tenant

                # Get first active tenant for development
                tenant = Tenant.query.filter_by(is_active=True).first()
                if tenant:
                    logger.debug(f"Development tenant resolved from database: {tenant.id}")
                    return tenant

                # Create default development tenant if none exist
                if not Tenant.query.first():
                    from app.extensions import db

                    default_tenant = Tenant(
                        name="Development Tenant", subdomain="development", is_active=True
                    )
                    db.session.add(default_tenant)
                    db.session.commit()
                    logger.info(f"Created default development tenant: {default_tenant.id}")
                    return default_tenant

            # Production tenant resolution
            hostname = request.headers.get("Host", "")
            if hostname:
                subdomain = hostname.split(":")[0].split(".")[0]
                if subdomain not in ["localhost", "www", "api"]:
                    tenant = Tenant.query.filter_by(subdomain=subdomain, is_active=True).first()
                    if tenant:
                        logger.debug(f"Production tenant resolved: {tenant.id}")
                        return tenant
                    else:
                        logger.warning(f"No tenant found for subdomain: {subdomain}")

            return None

        except Exception as e:
            logger.error(f"Error resolving tenant: {str(e)}", exc_info=True)
            return None

    @classmethod
    def tenant_required(cls, f: Callable) -> Callable:
        """Enhanced decorator to enforce tenant context with security and monitoring"""

        @wraps(f)
        def decorated(*args: Any, **kwargs: Any) -> Any:
            # Start request timing
            MetricsMiddleware.start_timer()

            # Security validation
            security_result = SecurityMiddleware.validate_request()
            if security_result is not None:
                return security_result

            # Tenant resolution
            tenant = cls.get_tenant_from_request()

            if not tenant:
                error_msg = "Invalid tenant"
                if current_app.debug:
                    error_msg = (
                        "No valid tenant found. In development, either: "
                        "1) Set X-Tenant-ID header, or "
                        "2) Create a tenant in the database"
                    )
                logger.warning(f"Tenant resolution failed: {error_msg}")
                raise TenantNotFoundError(error_msg)

            if not tenant.is_active:
                error_msg = f"Tenant {tenant.name} is not active"
                logger.warning(f"Inactive tenant accessed: {tenant.id}")
                raise InactiveTenantError(error_msg)

            # Set tenant context
            g.tenant = tenant
            g.current_tenant = tenant

            try:
                # Execute route handler
                response = f(*args, **kwargs)

                # Add security headers
                if isinstance(response, Response):
                    response = SecurityMiddleware.security_headers(response)

                # Record metrics
                MetricsMiddleware.record_metrics(response)

                return response

            except Exception as e:
                logger.error(
                    "Error processing request",
                    extra={
                        "tenant_id": tenant.id,
                        "error": str(e),
                        "path": request.path,
                        "method": request.method,
                    },
                    exc_info=True,
                )
                raise

        return limiter.limit("60 per minute")(decorated)  # Apply rate limiting

    @staticmethod
    def get_current_tenant() -> Optional[Tenant]:
        """Get current tenant from context with logging"""
        tenant = getattr(g, "tenant", None) or getattr(g, "current_tenant", None)
        if tenant is None:
            logger.warning("Attempt to access current_tenant outside tenant context")
        return tenant


def configure_middleware(app):
    """Configure all middleware for the application"""
    # Use ProxyFix if behind a proxy (like nginx)
    if not app.debug:
        app.wsgi_app = ProxyFix(
            app.wsgi_app,
            x_for=1,  # Number of proxy servers
            x_proto=1,  # Whether to trust X-Forwarded-Proto
            x_host=1,  # Whether to trust X-Forwarded-Host
            x_port=1,  # Whether to trust X-Forwarded-Port
            x_prefix=1,  # Whether to trust X-Forwarded-Prefix
        )

    # Initialize rate limiter
    limiter.init_app(app)

    # Register before_request handlers
    @app.before_request
    def before_request():
        MetricsMiddleware.start_timer()
        return SecurityMiddleware.validate_request()

    # Register after_request handlers
    @app.after_request
    def after_request(response):
        MetricsMiddleware.record_metrics(response)
        return SecurityMiddleware.security_headers(response)

    logger.info("Middleware configured successfully")
    return app

    # Register before_request handlers
    @app.before_request
    def before_request():
        MetricsMiddleware.start_timer()
        return SecurityMiddleware.validate_request()

    # Register after_request handlers
    @app.after_request
    def after_request(response):
        MetricsMiddleware.record_metrics(response)
        return SecurityMiddleware.security_headers(response)

    logger.info("Middleware configured successfully")
    return app
