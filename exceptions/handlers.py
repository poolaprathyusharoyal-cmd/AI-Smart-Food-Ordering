import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


def install_exception_handlers(app: FastAPI):
    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException):
        message = exc.detail if isinstance(exc.detail, str) else "Request could not be completed"
        return JSONResponse(status_code=exc.status_code, content={"code": "request_error", "message": message, "request_id": getattr(request.state, "request_id", "unknown")}, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        errors = [{"field": ".".join(str(part) for part in error["loc"]), "message": error["msg"]} for error in exc.errors()]
        return JSONResponse(status_code=422, content={"code": "validation_error", "message": "Request validation failed", "details": errors, "request_id": getattr(request.state, "request_id", "unknown")})

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception):
        logger.exception("Unhandled request error (request_id=%s)", getattr(request.state, "request_id", "unknown"))
        return JSONResponse(status_code=500, content={"code": "internal_error", "message": "An unexpected error occurred", "request_id": getattr(request.state, "request_id", "unknown")})
