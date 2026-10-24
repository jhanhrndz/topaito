"""Validadores de identificadores colombianos para la Capa 1 de Tapaito.

Incluye:
- Algoritmo de dígito de verificación (DV) de la DIAN para NIT empresariales.
- Validador de teléfonos celulares colombianos (prefijos 300-359).
- Validador de radicados judiciales de 23 dígitos (acuerdo CSJ).
- Validador contextual y estructural de cédulas de ciudadanía para evitar
  falsos positivos con códigos clínicos (CUPS, CIE-10, lotes, dosis).
"""

from __future__ import annotations

import re

# Pesos primos oficiales de la DIAN aplicados de derecha a izquierda
_DIAN_PRIME_WEIGHTS: tuple[int, ...] = (
    3,
    7,
    13,
    17,
    19,
    23,
    29,
    37,
    41,
    43,
    47,
    53,
    59,
    67,
    71,
)

_CLEAN_NIT_RE = re.compile(r"[\s.]")
_CLEAN_PHONE_RE = re.compile(r"[\s\-.()]")
_CELULAR_LOCAL_RE = re.compile(r"^3[0-5]\d{8}$")
_CLEAN_RADICADO_RE = re.compile(r"[\s\-]")
_DOTTED_THOUSANDS_RE = re.compile(r"^\d{1,3}(?:\.\d{3}){2,3}$")

# Contexto negativo previo (evita falsos positivos en historias clínicas - R8)
_NEGATIVE_BEFORE_RE = re.compile(
    r"\b(?:"
    r"cups|cie-10|cie10|cie|lote|invima|radicado|nit|"
    r"orden\s*#|orden\s+no\.?|cama|habitaci[oó]n|tel(?:[eé]fono)?|celular|cel"
    r")\b[\s:#.\-]*$",
    re.IGNORECASE,
)

# Contexto negativo posterior (unidades de medida o clínicas inmediatas)
_NEGATIVE_AFTER_RE = re.compile(
    r"^\s*(?:mg|ml|mcg|ui|g/dl|mmhg|lpm|rpm|a[ñn]os|kg|cm|%)(?=\b|\s|[.,;)]|$)",
    re.IGNORECASE,
)

# Contexto positivo para documentos de identidad en ventana cercana
_POSITIVE_CEDULA_CONTEXT_RE = re.compile(
    r"(?:"
    r"\bc[eé]dula\b|"
    r"\bc\.?\s*c\.?(?=\s|:|#|\.|-|\d|$)|"
    r"\bdocumento\b|"
    r"\bdoc\.?(?=\s|:|#|-|\d|$)|"
    r"\bidentificaci[oó]n\b|"
    r"\bid(?:\s*:|\s+)|"
    r"\bdni\b|"
    r"\bt\.?\s*i\.?(?=\s|:|#|\.|-|\d|$)|"
    r"\bpaciente\s+con\b|"
    r"\bportador(?:a)?\b"
    r")",
    re.IGNORECASE,
)


def compute_dian_dv(nit_digits: str) -> int:
    """Calcula el dígito de verificación de la DIAN para un NIT colombiano.

    Aplica de derecha a izquierda los pesos primos oficiales sobre los dígitos
    limpios. ``residuo = suma % 11``; si es 0 o 1 retorna ``residuo``, de lo
    contrario retorna ``11 - residuo``.
    """
    clean = _CLEAN_NIT_RE.sub("", nit_digits)
    if not clean.isdigit() or not (8 <= len(clean) <= 15):
        raise ValueError("nit_digits debe contener entre 8 y 15 dígitos numéricos.")

    total = sum(
        int(digit) * _DIAN_PRIME_WEIGHTS[idx]
        for idx, digit in enumerate(reversed(clean))
    )
    remainder = total % 11
    return remainder if remainder in (0, 1) else 11 - remainder


def validate_nit_dv(nit_digits: str, dv: str) -> bool:
    """Valida que un NIT colombiano (8–10 dígitos) coincida con su dígito verificador."""
    clean_nit = _CLEAN_NIT_RE.sub("", nit_digits)
    clean_dv = dv.strip()
    if not clean_nit.isdigit() or not clean_dv.isdigit() or len(clean_dv) != 1:
        return False
    if not (8 <= len(clean_nit) <= 10):
        return False
    return int(clean_dv) == compute_dian_dv(clean_nit)


def validate_celular_co(raw: str) -> bool:
    """Valida si una cadena corresponde a un número celular colombiano.

    Acepta prefijo opcional ``+57`` o ``57`` (cuando la longitud total es 12 dígitos)
    y verifica que el número local tenga 10 dígitos y coincida con ``^3[0-5]\\d{8}$``.
    """
    cleaned = _CLEAN_PHONE_RE.sub("", raw.strip())
    if cleaned.startswith("+57"):
        cleaned = cleaned[3:]
    elif len(cleaned) == 12 and cleaned.startswith("57"):
        cleaned = cleaned[2:]
    elif cleaned.startswith("+"):
        return False

    return bool(_CELULAR_LOCAL_RE.match(cleaned))


def validate_radicado_co(raw: str) -> bool:
    """Valida un número de radicación judicial colombiano de 23 dígitos.

    Estructura CSJ: 5 DANE + 2 corp + 2 esp + 3 desp (12 dígitos) + 4 año
    (posiciones 12:16, o 9:13 si viene con variante abreviada) + 5 consecutivo + 2 recurso.
    """
    cleaned = _CLEAN_RADICADO_RE.sub("", raw.strip())
    if len(cleaned) != 23 or not cleaned.isdigit():
        return False
    year_std = int(cleaned[12:16])
    year_alt = int(cleaned[9:13])
    return (1990 <= year_std <= 2035) or (1990 <= year_alt <= 2035)


def has_cedula_context(text: str, start: int, end: int) -> bool:
    """Determina si el candidato ``text[start:end]`` tiene contexto de cédula colombiana.

    1. Evalúa primero contexto negativo inmediato (códigos clínicos CUPS/CIE-10,
       lotes, INVIMA, camas, teléfonos o unidades médicas pospuestas).
    2. Evalúa contexto positivo en la ventana cercana o formato explícito con puntos
       de miles colombianos (``1.032.456.789`` o ``79.456.123``) dentro de rango.
    """
    candidate = text[start:end].strip()
    digits_only = candidate.replace(".", "")
    if not digits_only.isdigit() or not (6 <= len(digits_only) <= 10):
        return False

    before_immediate = text[max(0, start - 25) : start]
    after_immediate = text[end : min(len(text), end + 12)]

    if _NEGATIVE_BEFORE_RE.search(before_immediate):
        return False
    if _NEGATIVE_AFTER_RE.search(after_immediate):
        return False

    window_before = text[max(0, start - 45) : start]
    window_after = text[end : min(len(text), end + 25)]
    # Cortar la ventana posterior si inicia una cláusula ajena (p. ej. ". Se realiza CUPS")
    clause_break = re.search(r"[.;\n]", window_after)
    if clause_break:
        window_after = window_after[: clause_break.start()]

    if _POSITIVE_CEDULA_CONTEXT_RE.search(window_before) or _POSITIVE_CEDULA_CONTEXT_RE.search(
        window_after
    ):
        return True

    if _DOTTED_THOUSANDS_RE.match(candidate):
        numeric_value = int(digits_only)
        if 1_000_000 <= numeric_value <= 1_999_999_999:
            return True

    return False
