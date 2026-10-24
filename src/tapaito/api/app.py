"""Aplicación principal FastAPI de Tapaito."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from tapaito import __version__

logger = logging.getLogger("tapaito")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Tapaito Local Privacy Proxy",
        version=__version__,
        description="Proxy local compatible con OpenAI que reduce la exposicion de datos personales colombianos.",
    )

    # Sanitizar errores de validacion para que jamas devuelvan ni logueen el cuerpo/input sensible (R9 / CE6)
    @app.exception_handler(RequestValidationError)
    async def sanitized_validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        safe_errors = []
        for err in exc.errors():
            safe_errors.append(
                {
                    "loc": err.get("loc"),
                    "msg": err.get("msg"),
                    "type": err.get("type"),
                }
            )
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "TAPAITO_INVALID_REQUEST",
                    "message": "Estructura de peticion invalida (cuerpo omitido por privacidad).",
                    "details": safe_errors,
                }
            },
        )

    @app.exception_handler(Exception)
    async def sanitized_unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        logger.error("Unhandled internal error in %s (payload redacted): %s", request.url.path, type(exc).__name__)
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "TAPAITO_INTERNAL_ERROR",
                    "message": "Error interno procesando la peticion (datos protegidos).",
                }
            },
        )

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @app.get("/v1/models")
    async def list_models() -> dict[str, Any]:
        return {
            "object": "list",
            "data": [
                {
                    "id": "tapaito-mock",
                    "object": "model",
                    "created": int(time.time()),
                    "owned_by": "tapaito-local",
                },
                {
                    "id": "qwen3:4b",
                    "object": "model",
                    "created": int(time.time()),
                    "owned_by": "ollama-local",
                },
            ],
        }

    # Montaje de /ui y /ui/static para la interfaz de auditoría clínica
    ui_dir = Path(__file__).resolve().parent.parent / "ui"
    if ui_dir.exists():
        app.mount("/ui/static", StaticFiles(directory=str(ui_dir)), name="ui_static")

    @app.get("/ui", response_model=None)
    async def serve_ui() -> FileResponse | HTMLResponse:
        index_file = ui_dir / "index.html"
        if index_file.exists():
            return FileResponse(str(index_file))
        return HTMLResponse(
            content="<!doctype html><html><head><meta charset='utf-8'><title>Tapaito UI</title></head>"
            "<body><h1>Tapaito Proxy Activo</h1><p>Estación de auditoría clínica activa.</p></body></html>",
            status_code=200,
        )

    # Registrar routers si ya estan disponibles
    try:
        from tapaito.api.routes_openai import router as openai_router
        from tapaito.api.routes_tapaito import router as tapaito_router

        app.include_router(openai_router)
        app.include_router(tapaito_router)
    except ImportError:
        pass

    return app


app = create_app()
