from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.services.errors import (
    ConflictError,
    InvalidInputError,
    PayloadTooLargeError,
    ResourceNotFoundError,
    ServiceError,
    UnsupportedMediaTypeError,
)

ERROR_STATUS: tuple[tuple[type[ServiceError], int], ...] = (
    (ResourceNotFoundError, status.HTTP_404_NOT_FOUND),
    (InvalidInputError, status.HTTP_400_BAD_REQUEST),
    (PayloadTooLargeError, 413),
    (UnsupportedMediaTypeError, status.HTTP_415_UNSUPPORTED_MEDIA_TYPE),
    (ConflictError, status.HTTP_409_CONFLICT),
)


async def service_error_handler(_request: Request, exc: ServiceError) -> JSONResponse:
    status_code = next(
        (
            mapped_status
            for error_type, mapped_status in ERROR_STATUS
            if isinstance(exc, error_type)
        ),
        status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
    return JSONResponse(status_code=status_code, content={"detail": str(exc)})


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ServiceError, service_error_handler)
