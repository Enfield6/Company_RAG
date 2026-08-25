class ServiceError(Exception):
    """Base class for expected application-service failures."""


class ResourceNotFoundError(ServiceError):
    pass


class InvalidInputError(ServiceError):
    pass


class PayloadTooLargeError(ServiceError):
    pass


class UnsupportedMediaTypeError(ServiceError):
    pass


class ConflictError(ServiceError):
    pass
