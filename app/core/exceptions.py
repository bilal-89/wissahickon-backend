class TenantError(Exception):
    """Base exception for tenant-related errors"""
    pass

class TenantNotFoundError(TenantError):
    """Raised when a tenant cannot be found"""
    pass

class InactiveTenantError(TenantError):
    """Raised when attempting to access an inactive tenant"""
    pass