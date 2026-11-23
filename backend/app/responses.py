"""Egységes válaszburok: status, message, data; hibánál status=error és üzenet."""
from __future__ import annotations

import logging
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger(__name__)

# A keretrendszer angol alapüzenetei helyett.
_FRAMEWORK_MESSAGES = {404: "Nincs ilyen végpont.", 405: "A végpont ezt a metódust nem támogatja."}


def success(data: dict[str, Any], message: str = "") -> dict[str, Any]:
    return {"status": "success", "message": message, "data": data}


def error(status_code: int, message: str) -> JSONResponse:
    return JSONResponse({"status": "error", "message": message}, status_code=status_code)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        default = exc.detail == HTTPStatus(exc.status_code).phrase
        message = _FRAMEWORK_MESSAGES[exc.status_code] if default and exc.status_code in _FRAMEWORK_MESSAGES else str(exc.detail)
        return error(exc.status_code, message)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        fields = sorted({str(e["loc"][-1]) for e in exc.errors()})
        return error(422, f"Érvénytelen vagy hiányzó paraméter: {', '.join(fields)}")

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, _: Exception) -> JSONResponse:
        log.exception("Váratlan hiba: %s %s", request.method, request.url.path)
        return error(500, "Váratlan szerverhiba történt.")
