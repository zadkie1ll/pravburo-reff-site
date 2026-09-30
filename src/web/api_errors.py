"""Uniform JSON error format for the React frontend's API.

Every error looks like ``{"error": {"code": ..., "message": ..., "fields": {...}}}``
so the client can branch on ``code`` and show ``message`` / per-field errors.
"""

from fastapi import HTTPException, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response


class ApiError(HTTPException):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        fields: dict[str, str] | None = None,
    ) -> None:
        super().__init__(status_code=status_code, detail=message)
        self.code = code
        self.message = message
        self.fields = fields or {}


def unauthorized() -> ApiError:
    return ApiError(401, "unauthorized", "Требуется вход")


def forbidden() -> ApiError:
    return ApiError(403, "forbidden", "Недостаточно прав")


async def api_error_handler(_: Request, exception: ApiError) -> JSONResponse:
    return JSONResponse(
        status_code=exception.status_code,
        content={
            "error": {
                "code": exception.code,
                "message": exception.message,
                "fields": exception.fields,
            }
        },
    )


API_PREFIX = "/api/"


async def validation_error_handler(request: Request, exception: RequestValidationError) -> Response:
    """Malformed API payloads use the uniform format; form pages keep FastAPI's default."""
    if not request.url.path.startswith(API_PREFIX):
        return await request_validation_exception_handler(request, exception)
    fields = {
        str(error["loc"][-1]): str(error["msg"]) for error in exception.errors() if error["loc"]
    }
    return await api_error_handler(
        request, ApiError(422, "validation_error", "Проверьте введённые данные", fields)
    )
