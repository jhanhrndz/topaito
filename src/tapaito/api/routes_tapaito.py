"""Rutas propias de Tapaito: /v1/tapaito/preview, /v1/tapaito/audit, DELETE /v1/tapaito/session/{id}."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from tapaito.audit.logger import audit_logger
from tapaito.policy.pipeline import PolicyBlockedError, process_text_pipeline, session_store
from tapaito.schemas import PreviewRequest, PreviewResponse

router = APIRouter(prefix="/v1/tapaito", tags=["tapaito"])


@router.post("/preview", response_model=None)
async def preview_masking(req: PreviewRequest) -> PreviewResponse | JSONResponse:
    """Devuelve texto original, texto enmascarado, entidades con offsets y advertencias sin llamar al upstream."""
    try:
        res = process_text_pipeline(
            text=req.text,
            mode=req.mode,
            session_id=req.session_id,
        )
    except PolicyBlockedError as exc:
        audit_logger.log_event(
            mode=req.mode,
            session_id=req.session_id,
            entities=exc.entities,
            result="bloqueado",
            latency_ms=exc.latency_ms,
            error_code=exc.code,
        )
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "mode": req.mode.value,
                    "warnings": exc.warnings,
                }
            },
        )

    return PreviewResponse(
        original=res.original_text,
        masked=res.masked_text,
        mode=res.mode,
        session_id=res.session_id,
        entities=res.entities,
        warnings=res.warnings,
        latency_ms=res.latency_ms,
    )


@router.get("/audit")
async def get_audit_entries(limit: int = Query(default=20, ge=1, le=200)) -> dict[str, Any]:
    """Devuelve las ultimas entradas del audit log JSONL (sin valores originales)."""
    return {"entries": audit_logger.read_recent(limit=limit)}


@router.delete("/session/{session_id}")
async def delete_session_endpoint(session_id: str) -> dict[str, Any]:
    """Borra explicitamente el mapa valor <-> token de la sesion en memoria."""
    deleted = session_store.delete_session(session_id)
    return {"deleted": deleted, "session_id": session_id}
