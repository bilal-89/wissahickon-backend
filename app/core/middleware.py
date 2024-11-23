# app/core/middleware.py

from functools import wraps
from flask import request, g, current_app
from app.models import Tenant
from app.core.exceptions import TenantNotFoundError, InactiveTenantError


class TenantMiddleware:
    @staticmethod
    def get_tenant_from_request():
        """Extract tenant from request hostname or headers"""
        if current_app.debug:
            # In development, first try to get from header
            tenant_id = request.headers.get('X-Tenant-ID')
            if tenant_id:
                tenant = Tenant.query.get(tenant_id)
                if tenant:
                    return tenant

            # For development, if no tenant header, get the first active tenant
            # This is just for development convenience
            tenant = Tenant.query.filter_by(is_active=True).first()
            if tenant:
                return tenant

            # If no tenants exist in development, create a default one
            if not Tenant.query.first():
                from app.extensions import db
                default_tenant = Tenant(
                    name="Development Tenant",
                    subdomain="development",
                    is_active=True
                )
                db.session.add(default_tenant)
                db.session.commit()
                return default_tenant

        # Production tenant resolution via subdomain
        hostname = request.headers.get('Host', '')
        if hostname:
            # Strip port number if present
            subdomain = hostname.split(':')[0].split('.')[0]
            if subdomain not in ['localhost', 'www', 'api']:
                return Tenant.query.filter_by(subdomain=subdomain, is_active=True).first()

        return None

    @staticmethod
    def tenant_required(f):
        """Decorator to enforce tenant context for routes"""

        @wraps(f)
        def decorated(*args, **kwargs):
            tenant = TenantMiddleware.get_tenant_from_request()

            if not tenant:
                if current_app.debug:
                    raise TenantNotFoundError(
                        "No valid tenant found. In development, either: "
                        "1) Set X-Tenant-ID header, or "
                        "2) Create a tenant in the database"
                    )
                return {'error': 'Invalid tenant'}, 404

            if not tenant.is_active:
                if current_app.debug:
                    raise InactiveTenantError(f"Tenant {tenant.name} is not active")
                return {'error': 'Invalid tenant'}, 404

            g.tenant = tenant
            return f(*args, **kwargs)

        return decorated

    @staticmethod
    def get_current_tenant():
        """Helper to get current tenant from context"""
        return getattr(g, 'tenant', None)