"""Custom exception classes for the OpenStack VM API."""



class OpenStackAPIError(Exception):
    """Base exception for OpenStack API errors."""

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        error_code: str = "INTERNAL_ERROR",
        details: dict | None = None,
    ):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.details = details or {}
        super().__init__(message)


class VMNotFoundError(OpenStackAPIError):
    def __init__(self, vm_id: str):
        super().__init__(
            message=f"VM '{vm_id}' not found",
            status_code=404,
            error_code="VM_NOT_FOUND",
        )


class VMConflictError(OpenStackAPIError):
    def __init__(self, message: str):
        super().__init__(
            message=message,
            status_code=409,
            error_code="VM_CONFLICT",
        )


class InvalidVMStateError(OpenStackAPIError):
    def __init__(self, vm_id: str, current_state: str, required_state: str):
        super().__init__(
            message=f"VM '{vm_id}' is in state '{current_state}', requires '{required_state}'",
            status_code=409,
            error_code="INVALID_VM_STATE",
        )


class FlavorNotFoundError(OpenStackAPIError):
    def __init__(self, flavor_id: str):
        super().__init__(
            message=f"Flavor '{flavor_id}' not found",
            status_code=404,
            error_code="FLAVOR_NOT_FOUND",
        )


class ImageNotFoundError(OpenStackAPIError):
    def __init__(self, image_id: str):
        super().__init__(
            message=f"Image '{image_id}' not found",
            status_code=404,
            error_code="IMAGE_NOT_FOUND",
        )


class AuthenticationError(OpenStackAPIError):
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(
            message=message,
            status_code=401,
            error_code="AUTHENTICATION_ERROR",
        )


class QuotaExceededError(OpenStackAPIError):
    def __init__(self, resource: str):
        super().__init__(
            message=f"Quota exceeded for resource: {resource}",
            status_code=403,
            error_code="QUOTA_EXCEEDED",
        )


class OpenStackConnectionError(OpenStackAPIError):
    def __init__(self, message: str = "Failed to connect to OpenStack"):
        super().__init__(
            message=message,
            status_code=503,
            error_code="OPENSTACK_UNAVAILABLE",
        )
