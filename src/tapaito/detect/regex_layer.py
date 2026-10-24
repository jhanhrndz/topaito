"""Capa 1 de detección: expresiones regulares y validadores colombianos."""

from __future__ import annotations

import re

from tapaito.detect.validators import (
    has_cedula_context,
    validate_celular_co,
    validate_nit_dv,
    validate_radicado_co,
)
from tapaito.schemas import EntityType, Span

# 1. RADICADO JUDICIAL (23 dígitos continuos o separados por guiones/espacios por bloque CSJ)
_RADICADO_RE = re.compile(
    r"(?<!\d)(?:"
    r"\d{23}"
    r"|\d{5}[\s\-]\d{2}[\s\-]\d{2}[\s\-]\d{3}[\s\-]\d{4}[\s\-]\d{5}[\s\-]\d{2}"
    r")(?!\d)"
)

# 2. NIT EMPRESARIAL (8 a 10 dígitos, con o sin puntos de miles, seguido de guion y DV)
_NIT_RE = re.compile(
    r"(?<!\d)(?P<digits>\d{1,3}(?:\.\d{3}){2}|\d{8,10})\s*-\s*(?P<dv>\d)(?!\d)"
)

# 3. CORREO ELECTRÓNICO
_CORREO_RE = re.compile(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b")

# 4. CELULAR COLOMBIANO (con o sin +57 / (+57) / 57 y separadores de espacio, punto o guion)
_CELULAR_RE = re.compile(
    r"(?<!\d)(?:\(\+57\)\s*|\+57[\s\-.]*|57[\s\-.]+)?"
    r"3[0-5]\d(?:[\s\-.]*\d){7}(?!\d)"
)

# 5. DIRECCIONES COLOMBIANAS (urbanas y rurales)
_DIRECCION_URBANA_RE = re.compile(
    r"\b(?:Calle|Cll\.?|Carrera|Cra\.?|Cr\.?|Diagonal|Diag\.?|Dg\.?|"
    r"Transversal|Transv\.?|Tv\.?|Avenida|Av\.?)\s+"
    r"[A-Za-z0-9ÁÉÍÓÚáéíóúÑñ]+(?:\s+[A-Za-z0-9ÁÉÍÓÚáéíóúÑñ]+){0,3}\s*"
    r"(?:#|No\.?|Nro\.?|n[úu]mero)\s*"
    r"\d+[A-Za-z]?(?:\s*(?:Bis|Sur|Norte|Este|Oeste))?\s*-\s*\d+[A-Za-z]?"
    r"(?:\s*(?:,?\s*(?:Apto\.?|Apartamento|Int\.?|Interior|Consultorio|Cons\.?|"
    r"Oficina|Of\.?|Torre|Bloque|Casa|Piso|Local)\s+[A-Za-z0-9\-]+))*",
    re.IGNORECASE,
)

_DIRECCION_RURAL_RE = re.compile(
    r"\b(?:Vereda|Vda\.?|Corregimiento|Kil[oó]metro|Km\.?)\s+"
    r"[A-Za-z0-9ÁÉÍÓÚáéíóúÑñ]+(?:\s+[A-Za-z0-9ÁÉÍÓÚáéíóúÑñ]+){0,4}"
    r"(?:\s+(?:Km\.?|Kil[oó]metro|Finca|Parcela|Lote|Sector)\s+[A-Za-z0-9\-]+)?",
    re.IGNORECASE,
)

# 6. FECHA DE NACIMIENTO (requiere contexto cercano explícito)
_FECHA_CANDIDATE_RE = re.compile(
    r"\b(?:"
    r"\d{1,2}[/\-]\d{1,2}[/\-](?:19|20)\d{2}"
    r"|(?:19|20)\d{2}[/\-]\d{1,2}[/\-]\d{1,2}"
    r"|\d{1,2}\s+de\s+(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|"
    r"septiembre|octubre|noviembre|diciembre)\s+de(?:l)?\s+(?:19|20)\d{2}"
    r")\b",
    re.IGNORECASE,
)

_FECHA_NAC_CONTEXT_RE = re.compile(
    r"(?:fecha\s+de\s+nacimiento|f\.?\s*nac(?:imiento)?\.?|fnac|"
    r"naci[oó]\s+el|nacida?\s+el|nacimiento\s*:?)",
    re.IGNORECASE,
)

# 7. CUENTA BANCARIA / PÓLIZA (precedida por contexto explícito)
_CUENTA_WITH_CONTEXT_RE = re.compile(
    r"(?:cuenta\s+de\s+ahorros|cuenta\s+corriente|cuenta\s+bancaria|cta\.?(?:\s+de\s+ahorros|\s+corriente)?|iban)"
    r"[\s:#.\-]*(?:No\.?\s*|Nro\.?\s*|#\s*)?"
    r"(?P<account>[A-Z]{0,2}\d{2,6}(?:[\s\-]?\d{1,6}){1,5})",
    re.IGNORECASE,
)

# 8. CANDIDATOS A CÉDULA (con puntos de miles o 6-10 dígitos continuos)
_CEDULA_CANDIDATE_RE = re.compile(
    r"(?<![\d.])(?:\d{1,3}(?:\.\d{3}){2,3}|\d{6,10})(?!(?:\.\d)|\d)"
)


def _overlaps_any(start: int, end: int, spans: list[Span]) -> bool:
    """Retorna True si el intervalo [start, end) se solapa con algún Span existente."""
    return any(start < existing.end and end > existing.start for existing in spans)


def detect_regex(text: str) -> list[Span]:
    """Detecta entidades estructuradas colombianas mediante regex y validadores."""
    if not text:
        return []

    spans: list[Span] = []

    # 1. Radicados judiciales (23 dígitos) - prioridad máxima sobre secuencias largas
    for match in _RADICADO_RE.finditer(text):
        raw = match.group(0)
        if validate_radicado_co(raw):
            s, e = match.span()
            spans.append(
                Span(
                    start=s,
                    end=e,
                    entity_type=EntityType.RADICADO,
                    text=text[s:e],
                    source="regex",
                    confidence=1.0,
                )
            )

    # 2. NIT con validación estricta de dígito de verificación DIAN
    for match in _NIT_RE.finditer(text):
        s, e = match.span()
        if _overlaps_any(s, e, spans):
            continue
        digits = match.group("digits")
        dv = match.group("dv")
        if validate_nit_dv(digits, dv):
            spans.append(
                Span(
                    start=s,
                    end=e,
                    entity_type=EntityType.NIT,
                    text=text[s:e],
                    source="regex",
                    confidence=1.0,
                )
            )

    # 3. Correos electrónicos
    for match in _CORREO_RE.finditer(text):
        s, e = match.span()
        if _overlaps_any(s, e, spans):
            continue
        spans.append(
            Span(
                start=s,
                end=e,
                entity_type=EntityType.CORREO,
                text=text[s:e],
                source="regex",
                confidence=1.0,
            )
        )

    # 4. Direcciones físicas (urbanas y rurales)
    for pattern in (_DIRECCION_URBANA_RE, _DIRECCION_RURAL_RE):
        for match in pattern.finditer(text):
            s, e = match.span()
            if _overlaps_any(s, e, spans):
                continue
            spans.append(
                Span(
                    start=s,
                    end=e,
                    entity_type=EntityType.DIRECCION,
                    text=text[s:e],
                    source="regex",
                    confidence=0.95,
                )
            )

    # 5. Cuentas bancarias con contexto explícito
    for match in _CUENTA_WITH_CONTEXT_RE.finditer(text):
        s, e = match.span("account")
        if _overlaps_any(s, e, spans):
            continue
        spans.append(
            Span(
                start=s,
                end=e,
                entity_type=EntityType.CUENTA,
                text=text[s:e],
                source="regex",
                confidence=0.95,
            )
        )

    # 6. Fechas de nacimiento con contexto cercano
    for match in _FECHA_CANDIDATE_RE.finditer(text):
        s, e = match.span()
        if _overlaps_any(s, e, spans):
            continue
        window_before = text[max(0, s - 45) : s]
        if _FECHA_NAC_CONTEXT_RE.search(window_before):
            spans.append(
                Span(
                    start=s,
                    end=e,
                    entity_type=EntityType.FECHA_NAC,
                    text=text[s:e],
                    source="regex",
                    confidence=0.95,
                )
            )

    # 7. Teléfonos celulares colombianos (validando que no sean sub-segmento de radicado)
    for match in _CELULAR_RE.finditer(text):
        s, e = match.span()
        if _overlaps_any(s, e, spans):
            continue
        raw = match.group(0)
        if validate_celular_co(raw):
            spans.append(
                Span(
                    start=s,
                    end=e,
                    entity_type=EntityType.CELULAR,
                    text=text[s:e],
                    source="regex",
                    confidence=1.0,
                )
            )

    # 8. Cédulas de ciudadanía (6–10 dígitos o formato con puntos + validador de contexto)
    for match in _CEDULA_CANDIDATE_RE.finditer(text):
        s, e = match.span()
        if _overlaps_any(s, e, spans):
            continue
        if has_cedula_context(text, s, e):
            spans.append(
                Span(
                    start=s,
                    end=e,
                    entity_type=EntityType.CEDULA,
                    text=text[s:e],
                    source="regex",
                    confidence=0.95,
                )
            )

    spans.sort(key=lambda sp: (sp.start, -(sp.end - sp.start)))
    return spans
