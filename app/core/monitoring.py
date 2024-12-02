# app/core/monitoring.py

from flask import g, request, current_app
import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.integrations.redis import RedisIntegration
from functools import wraps
import traceback
from random import random


def sample_error(sample_rate=0.1):
    """Decorator to sample errors at a given rate"""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if random() < sample_rate:  # Only capture some errors
                    with sentry_sdk.configure_scope() as scope:
                        if hasattr(g, "tenant"):
                            scope.set_tag("tenant_id", g.tenant.id)
                        sentry_sdk.capture_exception(e)
                raise

        return wrapper

    return decorator


def should_capture_error(exception):
    """Determine if an error should be captured based on type and context"""
    # Don't capture common 4xx errors
    if hasattr(exception, "status_code") and exception.status_code < 500:
        return False

    # Always capture database errors
    if "sqlalchemy" in traceback.extract_stack()[-1].filename.lower():
        return True

    # Always capture redis errors
    if "redis" in traceback.extract_stack()[-1].filename.lower():
        return True

    # Always capture 500s
    if hasattr(exception, "status_code") and exception.status_code >= 500:
        return True

    return True


def init_sentry(app):
    """Initialize Sentry with optimized settings for free tier"""
    if not app.config.get("SENTRY_DSN"):
        app.logger.warning("SENTRY_DSN not configured, skipping Sentry initialization")
        return

    def before_send(event, hint):
        """Process and filter events before sending to Sentry"""
        try:
            # Get the exception
            exc_info = hint.get("exc_info")
            if exc_info and not should_capture_error(exc_info[1]):
                return None

            # Add minimal context to save on event size
            if hasattr(g, "tenant"):
                event.setdefault("tags", {})
                event["tags"]["tenant_id"] = g.tenant.id
                event["tags"]["tenant_subdomain"] = g.tenant.subdomain

            if hasattr(g, "user"):
                event["user"] = {
                    "id": g.user.id,
                    "tenant_id": g.tenant.id if hasattr(g, "tenant") else None,
                }

            # Only include essential request info
            if request:
                event.setdefault("request", {})
                event["request"]["url"] = request.url
                event["request"]["method"] = request.method

            return event
        except Exception:
            return None  # If anything goes wrong, drop the event

    sentry_sdk.init(
        dsn=app.config["SENTRY_DSN"],
        integrations=[
            FlaskIntegration(transaction_style="url"),
            SqlalchemyIntegration(),
            RedisIntegration(),
        ],
        before_send=before_send,
        traces_sample_rate=0.01,  # Only sample 1% of transactions
        profiles_sample_rate=0.0,  # Disable profiling to save quota
        environment=app.config.get("FLASK_ENV", "production"),
        max_breadcrumbs=20,  # Reduce breadcrumbs to save space
        send_default_pii=False,  # Disable PII by default
        debug=False,  # Disable debug mode
    )


def capture_error(func):
    """Selective error capturing decorator"""

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if should_capture_error(e):
                with sentry_sdk.configure_scope() as scope:
                    # Add minimal context
                    if hasattr(g, "tenant"):
                        scope.set_tag("tenant_id", g.tenant.id)

                    if hasattr(g, "user"):
                        scope.set_user(
                            {
                                "id": g.user.id,
                                "tenant_id": g.tenant.id if hasattr(g, "tenant") else None,
                            }
                        )

                sentry_sdk.capture_exception(e)
            raise

    return wrapper
