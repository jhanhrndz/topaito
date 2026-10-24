"""Upstream Mock determinista y offline para pruebas E2E, utilidad y respaldo de demo."""

from __future__ import annotations

import re
import time
import uuid
from typing import Any

TOKEN_RE = re.compile(r"⟦[A-Z_]+_\d+⟧")


def generate_mock_completion(
    messages: list[dict[str, Any]],
    model: str = "tapaito-mock",
    hostile_mode: str | None = None,
) -> dict[str, Any]:
    """Genera una respuesta compatible con OpenAI ChatCompletion sin red externa.

    Conserva literalmente los tokens `⟦TIPO_N⟧` presentes en los mensajes de entrada
    para tareas cerradas (resumen clinico, extraccion de campos, plantilla de respuesta),
    salvo que se indique `hostile_mode` para tests de reinsercion tolerante (R2 / CE4).
    """
    user_texts = [
        str(m.get("content", ""))
        for m in messages
        if m.get("role") in ("user", "assistant") and isinstance(m.get("content"), str)
    ]
    combined = "\n".join(user_texts)
    tokens_found = list(dict.fromkeys(TOKEN_RE.findall(combined)))

    # Extraer datos clinicos no sensibles (edad, CIE-10, medicamentos, motivo) para utilidad
    cie10_matches = re.findall(r"\b[A-Z]\d{2,3}(?:\.\d)?\b", combined)
    med_matches = re.findall(
        r"\b(?:Losart[aá]n|Acetaminof[eé]n|Metformina|Enalapril|Omeprazol|Ibuprofeno|Amoxicilina|Atorvastatina)\b(?:\s+\d+\s*(?:mg|ml|mcg))?",
        combined,
        flags=re.IGNORECASE,
    )
    age_match = re.search(r"\b(\d{1,3})\s*a[ñn]os\b", combined, flags=re.IGNORECASE)

    if hostile_mode == "case_and_brackets":
        # Altera mayusculas, espacios y corchetes para probar reinsercion tolerante
        mutated = []
        for idx, tok in enumerate(tokens_found):
            inner = tok.strip("⟦⟧")
            if idx % 3 == 0:
                mutated.append(f"[{inner.lower()}]")
            elif idx % 3 == 1:
                mutated.append(f"⟦ {inner.lower()} ⟧")
            else:
                mutated.append(f"(({inner}))")
        content = "Resumen clinico procesado: " + ", ".join(mutated)
    elif hostile_mode == "invented_and_missing":
        kept = tokens_found[:-1] if len(tokens_found) > 1 else []
        content = (
            "Resumen clinico: "
            + ", ".join(kept)
            + " referenciado por ⟦PERSONA_99⟧ con nota ambigua [PERSONA]."
        )
    else:
        # Tarea cerrada estandar: resumen estructurado preservando todos los tokens
        tokens_str = ", ".join(tokens_found) if tokens_found else "sin identificadores enmascarados"
        parts = [f"Resumen Clínico Automatizado (Entidades vinculadas: {tokens_str})."]
        if age_match:
            parts.append(f"- Edad registrada: {age_match.group(1)} años.")
        if cie10_matches:
            parts.append(f"- Diagnósticos CIE-10: {', '.join(dict.fromkeys(cie10_matches))}.")
        if med_matches:
            parts.append(f"- Conducta farmacológica: {', '.join(dict.fromkeys(med_matches))}.")
        parts.append(
            f"- Síntesis del caso: Se procesó la nota preservando {len(tokens_found)} token(s): "
            + (" | ".join(tokens_found) if tokens_found else "ninguno")
            + "."
        )
        content = "\n".join(parts)

    return {
        "id": f"chatcmpl-mock-{uuid.uuid4().hex[:10]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": content,
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": max(1, len(combined) // 4),
            "completion_tokens": max(1, len(content) // 4),
            "total_tokens": max(2, (len(combined) + len(content)) // 4),
        },
    }
