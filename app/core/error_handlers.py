# app/core/error_handlers.py
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from .exceptions import BaseAPIException


class ErrorResponse(BaseModel):
    detail: str
    code: str


def setup_exception_handlers(app: FastAPI):
    @app.exception_handler(BaseAPIException)
    async def http_exception_handler(request: Request, exc: BaseAPIException):
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(
                detail=exc.detail, code=exc.headers.get("X-Error-Code", "unknown_error")
            ).model_dump(),
            headers=exc.headers,
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "code": "internal_error"},
        )
