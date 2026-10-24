"""Fusión y resolución de solapes de spans detectados entre capas."""

from __future__ import annotations

from tapaito.schemas import Span

SOURCE_PRIORITY: dict[str, int] = {
    "regex": 3,
    "session": 2,
    "ner": 1,
    "llm": 1,
}


def _span_rank_key(span: Span) -> tuple[int, int, int, float]:
    """Clave de ordenamiento por prioridad descendente:
    1. Prioridad de capa (regex=3 > session=2 > ner=1 >= llm=1)
    2. Longitud del span (end - start mayor)
    3. Inicio más temprano (-start mayor => start menor)
    4. Confianza como desempate final
    """
    priority = SOURCE_PRIORITY.get(span.source, 0)
    length = span.end - span.start
    return (priority, length, -span.start, span.confidence)


def _overlaps(a: Span, b: Span) -> bool:
    return a.start < b.end and b.start < a.end


def merge_spans(spans: list[Span]) -> list[Span]:
    """Fusiona una lista de spans eliminando inválidos y resolviendo solapes por prioridad."""
    valid_spans = [s for s in spans if s.start >= 0 and s.start < s.end]
    if not valid_spans:
        return []

    # Ordenamos candidatos de mayor a menor prioridad según las reglas de negocio
    candidates = sorted(valid_spans, key=_span_rank_key, reverse=True)
    accepted: list[Span] = []

    for candidate in candidates:
        if any(_overlaps(candidate, existing) for existing in accepted):
            continue
        accepted.append(candidate)

    accepted.sort(key=lambda s: (s.start, s.end))
    return accepted
