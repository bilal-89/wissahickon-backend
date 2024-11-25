class TenantError(Exception):
    """Base exception for tenant-related errors"""
    pass

class TenantNotFoundError(Exception):
    """Raised when a tenant cannot be found"""
    pass

class InactiveTenantError(Exception):
    """Raised when a tenant is not active"""
    pass

class PermissionDenied(Exception):
    """Raised when a user doesn't have required permission"""
    def __init__(self, message="Permission denied"):
        self.message = message
        super().__init__(self.message)

    def __str__(self):
        return self.message