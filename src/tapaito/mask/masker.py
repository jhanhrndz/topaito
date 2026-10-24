"""Enmascarado determinista con barrido de sesión (R16) y preservación de offsets (R15)."""

from __future__ import annotations

import re
from typing import Any

from tapaito.detect.merge import merge_spans
from tapaito.mask.session_store import SessionStore
from tapaito.schemas import PublicEntitySpan, Span

SYSTEM_TOKEN_INSTRUCTION: str = (
    "INSTRUCCIÓN DE PRIVACIDAD (TAPAITO): El texto contiene marcadores de posición con formato "
    "⟦TIPO_N⟧ (por ejemplo, ⟦PERSONA_1⟧, ⟦CEDULA_1⟧, ⟦CELULAR_1⟧). "
    "Debes conservar cada marcador exactamente igual en tu respuesta cuando hagas referencia a "
    "esa entidad: no los traduzcas, no modifiques los corchetes ⟦ ⟧, no cambies las mayúsculas "
    "ni alteres su numeración."
)


def inject_system_instruction(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Devuelve una nueva lista de mensajes con SYSTEM_TOKEN_INSTRUCTION en el rol system."""
    cloned: list[dict[str, Any]] = [dict(msg) for msg in messages]

    for msg in cloned:
        if msg.get("role") == "system":
            content = msg.get("content") or ""
            if isinstance(content, str):
                if SYSTEM_TOKEN_INSTRUCTION not in content:
                    msg["content"] = (
                        f"{SYSTEM_TOKEN_INSTRUCTION}\n\n{content}".strip()
                        if content.strip()
                        else SYSTEM_TOKEN_INSTRUCTION
                    )
            return cloned

    cloned.insert(0, {"role": "system", "content": SYSTEM_TOKEN_INSTRUCTION})
    return cloned


def sweep_session_known_entities(
    text: str,
    existing_spans: list[Span],
    session_id: str,
    store: SessionStore,
) -> list[Span]:
    """Mitigación R16 (Second-Pass Session Sweep):
    Registra primero las entidades de existing_spans en el store y luego busca en text
    apariciones adicionales no cubiertas de valores ya conocidos en esa sesión.
    """
    merged_initial = merge_spans(existing_spans)

    for span in merged_initial:
        surface = text[span.start : span.end] if not span.text else span.text
        store.get_or_create_token(session_id, span.entity_type, surface)

    known_values = store.get_known_values(session_id)
    if not known_values or not text:
        return merged_initial

    swept_spans: list[Span] = []
    for entity_type, surface, _token in known_values:
        candidate = surface.strip()
        if len(candidate) < 3:
            continue
        pattern = re.compile(rf"(?<!\w){re.escape(candidate)}(?!\w)", re.IGNORECASE)
        for match in pattern.finditer(text):
            start, end = match.span()
            swept_spans.append(
                Span(
                    start=start,
                    end=end,
                    entity_type=entity_type,
                    text=text[start:end],
                    source="session",
                    confidence=0.95,
                )
            )

    return merge_spans(merged_initial + swept_spans)


def mask_text(
    text: str,
    spans: list[Span],
    session_id: str,
    store: SessionStore,
    enable_session_sweep: bool = True,
) -> tuple[str, list[PublicEntitySpan]]:
    """Enmascara text reemplazando entidades por tokens ⟦TIPO_N⟧ preservando offsets originales."""
    if enable_session_sweep:
        final_spans = sweep_session_known_entities(text, spans, session_id, store)
    else:
        final_spans = merge_spans(spans)

    if not final_spans:
        return text, []

    # Paso 1: Asignar tokens en orden de izquierda a derecha para numeración determinista (_1, _2...)
    public_spans: list[PublicEntitySpan] = []
    for span in final_spans:
        raw_val = text[span.start : span.end]
        token = store.get_or_create_token(session_id, span.entity_type, raw_val)
        public_spans.append(
            PublicEntitySpan(
                start=span.start,
                end=span.end,
                entity_type=span.entity_type,
                token=token,
                source=span.source,
            )
        )

    # Paso 2 (Mitigación R15): Reemplazar de derecha a izquierda para no desplazar offsets previos
    masked_text = text
    for pub_span in reversed(public_spans):
        masked_text = (
            masked_text[: pub_span.start] + pub_span.token + masked_text[pub_span.end :]
        )

    return masked_text, public_spans
