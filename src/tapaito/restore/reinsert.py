"""Reinserción exacta y tolerante de tokens en respuestas del LLM (RF7, R2)."""

from __future__ import annotations

import re

from tapaito.schemas import EntityType, ReinsertionReport

VALID_ENTITY_TYPES: frozenset[str] = frozenset(e.value for e in EntityType)

# Patrón que captura distintos estilos de delimitadores usados o alterados por el LLM:
# ⟦...⟧, [[...]], [...], ((...)), (...), {{...}}, {...}, <<...>>
_TOKEN_CANDIDATE_RE = re.compile(
    r"(?:"
    r"⟦+\s*(?P<b1>[A-Za-z_]+(?:[\s_-]+\d+)?)\s*⟧+"
    r"|\[\[\s*(?P<b2>[A-Za-z_]+(?:[\s_-]+\d+)?)\s*\]\]"
    r"|\[\s*(?P<b3>[A-Za-z_]+(?:[\s_-]+\d+)?)\s*\]"
    r"|\(\(\s*(?P<b4>[A-Za-z_]+(?:[\s_-]+\d+)?)\s*\)\)"
    r"|\(\s*(?P<b5>[A-Za-z_]+(?:[\s_-]+\d+)?)\s*\)"
    r"|\{\{\s*(?P<b6>[A-Za-z_]+(?:[\s_-]+\d+)?)\s*\}\}"
    r"|\{\s*(?P<b7>[A-Za-z_]+(?:[\s_-]+\d+)?)\s*\}"
    r"|<<\s*(?P<b8>[A-Za-z_]+(?:[\s_-]+\d+)?)\s*>>"
    r")"
)

_INNER_BODY_RE = re.compile(r"^(?P<etype>[A-Za-z_]+?)(?:[\s_-]+(?P<idx>\d+))?$")


def _append_unique(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)


def reinsert_tokens(
    response_text: str,
    session_mapping: dict[str, str],
    expected_tokens: set[str] | None = None,
) -> tuple[str, ReinsertionReport]:
    """Reinserta los valores originales en la respuesta del LLM y genera ReinsertionReport."""
    expected = set(session_mapping.keys()) if expected_tokens is None else set(expected_tokens)

    restaurados: list[str] = []
    desconocidos: list[str] = []
    ambiguos: list[str] = []

    def _replace_match(match: re.Match[str]) -> str:
        full_match = match.group(0)
        inner = next((v for v in match.groupdict().values() if v is not None), "")
        body_match = _INNER_BODY_RE.match(inner.strip())
        if body_match is None:
            return full_match

        etype_upper = body_match.group("etype").upper()
        idx = body_match.group("idx")
        is_tapaito_bracket = full_match.startswith("⟦") and full_match.endswith("⟧")

        # Caso 1 y 2: Tiene índice numérico (ej. PERSONA_1, persona-1, PERSONA 99)
        if idx is not None:
            canonical = f"⟦{etype_upper}_{idx}⟧"
            if canonical in session_mapping:
                _append_unique(restaurados, canonical)
                return session_mapping[canonical]

            if etype_upper in VALID_ENTITY_TYPES or is_tapaito_bracket:
                _append_unique(desconocidos, canonical)
            return full_match

        # Caso 3: Sin índice numérico -> token ambiguo (ej. ⟦PERSONA⟧ o [PERSONA])
        if etype_upper in VALID_ENTITY_TYPES:
            _append_unique(ambiguos, full_match)
        return full_match

    restored_text = _TOKEN_CANDIDATE_RE.sub(_replace_match, response_text)

    restored_set = set(restaurados)
    faltantes = sorted(expected - restored_set)

    if expected:
        restored_expected_count = len(expected & restored_set)
        tasa_restauracion = round(restored_expected_count / len(expected), 4)
    else:
        tasa_restauracion = 1.0

    report = ReinsertionReport(
        restaurados=restaurados,
        faltantes=faltantes,
        desconocidos=desconocidos,
        ambiguos=ambiguos,
        tasa_restauracion=tasa_restauracion,
    )
    return restored_text, report
