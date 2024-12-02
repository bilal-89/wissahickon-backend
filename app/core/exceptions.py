class BaseAPIException(Exception):
    """Base exception class for API errors"""

    def __init__(self, message, status_code=400):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class TenantNotFoundError(BaseAPIException):
    """Raised when tenant is not found"""

    def __init__(self, message="Tenant not found", status_code=404):
        super().__init__(message, status_code)


class InactiveTenantError(BaseAPIException):
    """Raised when tenant is inactive"""

    def __init__(self, message="Tenant is inactive", status_code=403):
        super().__init__(message, status_code)


class RateLimitExceededError(BaseAPIException):
    """Raised when rate limit is exceeded"""

    def __init__(self, message="Rate limit exceeded", status_code=429):
        super().__init__(message, status_code)


class SecurityViolationError(BaseAPIException):
    """Raised when a security violation is detected"""

    def __init__(self, message="Security violation detected", status_code=403):
        super().__init__(message, status_code)


class PermissionDenied(BaseAPIException):
    """Raised when user doesn't have required permissions"""

    def __init__(self, message="Permission denied", status_code=403):
        super().__init__(message, status_code)
