"""Ruta compatible con OpenAI: POST /v1/chat/completions."""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse

from tapaito.audit.logger import audit_logger
from tapaito.mask.masker import inject_system_instruction
from tapaito.policy.pipeline import PolicyBlockedError, process_text_pipeline, session_store
from tapaito.restore.reinsert import reinsert_tokens
from tapaito.schemas import ChatCompletionRequest, Mode, PublicEntitySpan
from tapaito.upstream.client import call_upstream_chat

router = APIRouter(prefix="/v1", tags=["openai"])


def _parse_mode(raw_mode: str | None) -> Mode:
    if raw_mode and raw_mode.strip().lower() == Mode.ESTRICTO.value:
        return Mode.ESTRICTO
    return Mode.RAPIDO


@router.post("/chat/completions", response_model=None)
async def create_chat_completion(
    req: ChatCompletionRequest,
    x_tapaito_mode: str | None = Header(default=None, alias="X-Tapaito-Mode"),
    x_tapaito_session: str | None = Header(default=None, alias="X-Tapaito-Session"),
    x_tapaito_mock_hostile: str | None = Header(default=None, alias="X-Tapaito-Mock-Hostile"),
) -> dict[str, Any] | JSONResponse:
    """Intercepta mensajes OpenAI, enmascara PII colombiana, consulta upstream y reinserta."""
    t_total_start = time.perf_counter()
    mode = _parse_mode(x_tapaito_mode)
    session_id = (x_tapaito_session or "default").strip() or "default"

    masked_messages: list[dict[str, Any]] = []
    all_entities: list[PublicEntitySpan] = []
    all_warnings: list[str] = []
    masked_user_prompts: list[str] = []
    layer1_2_ms_acc = 0.0
    layer3_ms_acc = 0.0

    for msg in req.messages:
        msg_dict = msg.model_dump()
        content = msg_dict.get("content")
        role = msg_dict.get("role", "user")

        if isinstance(content, str) and content.strip() and role in ("user", "assistant", "system"):
            try:
                pipe_res = process_text_pipeline(
                    text=content,
                    mode=mode,
                    session_id=session_id,
                    store=session_store,
                )
            except PolicyBlockedError as exc:
                audit_logger.log_event(
                    mode=mode,
                    session_id=session_id,
                    entities=all_entities + exc.entities,
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
                            "mode": mode.value,
                            "warnings": exc.warnings,
                        }
                    },
                )

            msg_dict["content"] = pipe_res.masked_text
            if role != "system":
                masked_user_prompts.append(pipe_res.masked_text)
            all_entities.extend(pipe_res.entities)
            for w in pipe_res.warnings:
                if w not in all_warnings:
                    all_warnings.append(w)
            layer1_2_ms_acc += pipe_res.latency_ms.get("layer1_2", 0.0)
            layer3_ms_acc += pipe_res.latency_ms.get("layer3", 0.0)

        masked_messages.append(msg_dict)

    # Inyectar instruccion de sistema para conservar tokens literalmente (RF6)
    messages_for_upstream = inject_system_instruction(masked_messages)

    # Llamar al upstream (OpenAI-compatible o mock local)
    t_up = time.perf_counter()
    upstream_resp = await call_upstream_chat(
        messages=messages_for_upstream,
        model=req.model,
        temperature=req.temperature,
        max_tokens=req.max_tokens,
        hostile_mode=x_tapaito_mock_hostile,
    )
    upstream_ms = round((time.perf_counter() - t_up) * 1000.0, 2)

    # Extraer respuesta cruda del upstream y ejecutar reinsercion tolerante (RF7)
    choices = upstream_resp.get("choices", [])
    raw_upstream_text = ""
    if choices and isinstance(choices[0], dict):
        raw_upstream_text = str(choices[0].get("message", {}).get("content", ""))

    token_map = session_store.get_token_to_value_map(session_id)
    expected_tokens = {ent.token for ent in all_entities}
    restored_text, reinsertion_report = reinsert_tokens(
        response_text=raw_upstream_text,
        session_mapping=token_map,
        expected_tokens=expected_tokens,
    )

    if choices and isinstance(choices[0], dict) and "message" in choices[0]:
        choices[0]["message"]["content"] = restored_text

    total_ms = round((time.perf_counter() - t_total_start) * 1000.0, 2)
    latency_summary = {
        "layer1_2": round(layer1_2_ms_acc, 2),
        "layer3": round(layer3_ms_acc, 2),
        "upstream": upstream_ms,
        "total": total_ms,
    }

    # Registrar en audit log local sin valores originales (RF9 / CE6)
    audit_logger.log_event(
        mode=mode,
        session_id=session_id,
        entities=all_entities,
        result="enviado",
        latency_ms=latency_summary,
    )

    upstream_resp["tapaito"] = {
        "mode": mode.value,
        "session_id": session_id,
        "masked_prompt": "\n".join(masked_user_prompts),
        "raw_upstream_response": raw_upstream_text,
        "entities_masked": [ent.model_dump(mode="json") for ent in all_entities],
        "warnings": all_warnings,
        "reinsertion_report": reinsertion_report.model_dump(mode="json"),
        "latency_ms": latency_summary,
    }
    return upstream_resp
