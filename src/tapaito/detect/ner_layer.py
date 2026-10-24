"""Capa 2 de detección: NER con spaCy (es_core_news_md) y filtros clínicos."""

from __future__ import annotations

import re
import unicodedata
from typing import TYPE_CHECKING

import spacy

from tapaito.schemas import EntityType, Span

if TYPE_CHECKING:
    from spacy.language import Language

_NLP_INSTANCE: Language | None = None

MEDICAL_STOPLIST: frozenset[str] = frozenset(
    {
        # Fármacos comunes POS/PBS
        "acetaminofen",
        "paracetamol",
        "losartan",
        "metformina",
        "enalapril",
        "omeprazol",
        "ibuprofeno",
        "amoxicilina",
        "atorvastatina",
        "levotiroxina",
        "amlodipino",
        "hidroclorotiazida",
        "furosemida",
        "insulina",
        "dipirona",
        "naproxeno",
        "cefalexina",
        "ciprofloxacino",
        "azitromicina",
        "salbutamol",
        "prednisona",
        "dexametasona",
        "warfarina",
        "clopidogrel",
        "asa",
        "captopril",
        "valsartan",
        "carvedilol",
        "metoprolol",
        "espironolactona",
        "ranitidina",
        "fluoxetina",
        "sertralina",
        "clonazepam",
        "tramadol",
        "morfina",
        "vancomicina",
        "meropenem",
        "ringer",
        "hartmann",
        "lactato de ringer",
        "solucion salina",
        # Epónimos, escalas y términos clínicos
        "glasgow",
        "babinski",
        "apgar",
        "silverman",
        "blumberg",
        "murphy",
        "rovsing",
        "epigastrio",
        "hipocondrio",
        "torax",
        "abdomen",
        "urgencias",
        "uci",
        "uce",
        "hospitalizacion",
        "consulta externa",
        "epicrisis",
        "evolucion",
        "anamnesis",
        "examen fisico",
        "diagnostico",
        "conducta",
        "plan",
        "paciente",
        "acompanante",
        "medico",
        "doctor",
        "doctora",
        "enfermera",
        "enfermero",
        "cie-10",
        "cie10",
        "cups",
        "invima",
        "pos",
        "pbs",
        "soat",
        "fosyga",
        "adres",
        "sisben",
        # Encabezados y etiquetas documentales clínicas/jurídicas colombianas
        "historia clinica",
        "historia clinica de evolucion",
        "epicrisis de egreso",
        "orden medica",
        "orden medica ambulatoria",
        "medica ambulatoria",
        "solicitud de cumplimiento",
        "cumplimiento de",
        "tutela",
        "tutela en salud",
        "salud",
        "radicado",
        "asegurador",
        "entidad",
        "egreso",
        "ingreso",
        "cuadro",
        "atendido",
        "continuar",
        "prescripcion",
        "seguimiento",
        "reembolso",
        "nota de seguimiento",
        "c.c",
        "cc",
        "nit",
        "telefono",
        "celular",
        "correo",
        "direccion",
    }
)

_CLINICAL_NON_NAME_WORDS: frozenset[str] = frozenset(
    {
        "masculino",
        "femenino",
        "estable",
        "consciente",
        "orientado",
        "orientada",
        "hidratado",
        "hidratada",
        "afebril",
        "ingresa",
        "acude",
        "presenta",
        "refiere",
        "niega",
        "manifiesta",
        "consulta",
        "remitido",
        "remitida",
        "hospitalizado",
        "hospitalizada",
        "alerta",
        "colaborador",
        "colaboradora",
        "asintomatico",
        "asintomatica",
        "dolor",
        "fiebre",
        "servicio",
        "evolucion",
        "medica",
        "clinica",
        "historia",
        "nota",
        "turno",
        "control",
        "valoracion",
        "edad",
        "anos",
        "quien",
        "que",
        "con",
        "sin",
        "por",
        "para",
        "en",
        "al",
        "del",
        "se",
        "le",
        "fue",
        "es",
        "esta",
        "tiene",
        "como",
        "tras",
        "hacia",
        "desde",
        "hasta",
        "negativo",
        "positivo",
        "normal",
        "pendiente",
        "actual",
        "unico",
        "unica",
        "titular",
        "municipal",
        "departamental",
        "alcalde",
        "alcaldesa",
        "personero",
        "personera",
        "juez",
        "jueza",
        "rector",
        "rectora",
        "director",
        "directora",
        "continuar",
        "iniciar",
        "suspender",
        "administrar",
        "formular",
        "ordenar",
        "ambulatoria",
        "ambulatorio",
        "cumplimiento",
        "solicitud",
        "asegurador",
        "egreso",
        "atendido",
        "cuadro",
    }
)

_SPACY_LABEL_MAP: dict[str, EntityType] = {
    "PER": EntityType.PERSONA,
    "LOC": EntityType.UBICACION,
    "GPE": EntityType.UBICACION,
    "ORG": EntityType.ORGANIZACION,
}

_PREFIX_STRIP_RE = re.compile(
    r"^(?:(?:el|la)\s+)?(?:paciente|acompañante|acompanante|familiar|"
    r"dr\.?|dra\.?|doctor|doctora|médico|medico|enfermero|enfermera|"
    r"sr\.?|sra\.?|señor|señora|don|doña)\s*[:\-]?\s+",
    re.IGNORECASE,
)

_DOSE_OR_SCALE_RE = re.compile(
    r"\b\d+\s*(?:mg|mcg|g|gr|ml|cc|ui|unidades|gotas|tab|caps|amp|%)\b|\b\d{1,2}\s*/\s*\d{1,2}\b",
    re.IGNORECASE,
)

_LABELED_NAME_RE = re.compile(
    r"(?:Paciente|Acompañante|Acompanante|Familiar|Dr\.|Dra\.|Médico|Medico|"
    r"Enfermero|Enfermera|Atendido\s+por|Nombre)\s*[:\-]?\s*"
    r"([A-ZÁÉÍÓÚÑa-záéíóúñ]{2,}(?:\s+[A-ZÁÉÍÓÚÑa-záéíóúñ]{2,}){1,3})",
    re.IGNORECASE,
)


def normalize_clinical_term(text: str) -> str:
    """Convierte a minúsculas, elimina tildes y colapsa espacios."""
    decomposed = unicodedata.normalize("NFD", text.lower())
    without_accents = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return " ".join(without_accents.split())


def _get_nlp() -> Language:
    """Retorna la instancia singleton perezosa de es_core_news_md."""
    global _NLP_INSTANCE
    if _NLP_INSTANCE is None:
        _NLP_INSTANCE = spacy.load(
            "es_core_news_md",
            disable=["parser", "lemmatizer", "attribute_ruler"],
        )
    return _NLP_INSTANCE


def is_filtered_clinical_span(raw_text: str) -> bool:
    """Retorna True si el texto corresponde a un término clínico, dosis o token enmascarado."""
    if not raw_text or "⟦" in raw_text or "⟧" in raw_text:
        return True
    if _DOSE_OR_SCALE_RE.search(raw_text):
        return True

    norm = normalize_clinical_term(raw_text.strip(" .,:;-()[]"))
    if not norm or len(norm) < 3:
        return True
    if norm in MEDICAL_STOPLIST or norm in _CLINICAL_NON_NAME_WORDS:
        return True

    tokens = norm.split()
    if tokens[0] in MEDICAL_STOPLIST:
        return True
    if tokens[0] in _CLINICAL_NON_NAME_WORDS and tokens[0] not in ("clinica", "hospital", "centro", "fundacion"):
        return True
    if norm.startswith("historia clinica"):
        return True
    if all(tok in MEDICAL_STOPLIST or tok in _CLINICAL_NON_NAME_WORDS for tok in tokens):
        return True

    return False


def _overlaps_any(start: int, end: int, spans: list[Span]) -> bool:
    return any(start < existing.end and end > existing.start for existing in spans)


def _clean_span_bounds(text: str, start: int, end: int, entity_type: EntityType) -> tuple[int, int] | None:
    """Limpia prefijos clínicos/títulos y espacios/puntuación sobrantes ajustando offsets."""
    sub = text[start:end]

    if entity_type == EntityType.PERSONA:
        m = _PREFIX_STRIP_RE.match(sub)
        if m:
            start += m.end()
            sub = text[start:end]

    # Limpiar espacios o saltos de línea al inicio/final
    while start < end and (text[start].isspace() or text[start] in ".,:;-()[]{}"):
        start += 1
    while end > start and (text[end - 1].isspace() or text[end - 1] in ".,:;-()[]{}"):
        end -= 1

    if start >= end:
        return None

    # En caso de que tras limpiar puntuación aún quede un prefijo
    if entity_type == EntityType.PERSONA:
        sub = text[start:end]
        m = _PREFIX_STRIP_RE.match(sub)
        if m:
            start += m.end()
            while start < end and text[start].isspace():
                start += 1

    if start >= end:
        return None
    return start, end


def detect_ner(text: str) -> list[Span]:
    """Detecta nombres, ubicaciones y organizaciones usando spaCy + heurísticas clínicas."""
    if not text or not text.strip():
        return []

    nlp = _get_nlp()
    doc = nlp(text)
    spans: list[Span] = []

    for ent in doc.ents:
        entity_type = _SPACY_LABEL_MAP.get(ent.label_)
        if entity_type is None:
            continue

        cleaned = _clean_span_bounds(text, ent.start_char, ent.end_char, entity_type)
        if cleaned is None:
            continue
        s, e = cleaned
        candidate_text = text[s:e]

        if is_filtered_clinical_span(candidate_text):
            continue
        if _overlaps_any(s, e, spans):
            continue

        spans.append(
            Span(
                start=s,
                end=e,
                entity_type=entity_type,
                text=candidate_text,
                source="ner",
                confidence=0.85,
            )
        )

    # Detector complementario para nombres tras etiquetas clínicas (incluyendo minúsculas)
    for match in _LABELED_NAME_RE.finditer(text):
        cand_start, cand_end = match.span(1)
        raw_cand = text[cand_start:cand_end]

        # Dividir en palabras con sus offsets relativos para recortar verbos/adjetivos clínicos al final
        word_matches = list(re.finditer(r"[A-ZÁÉÍÓÚÑa-záéíóúñ]{2,}", raw_cand))
        if not word_matches:
            continue

        # Si la primera palabra es un verbo/adjetivo clínico o stoplist, descartar
        first_norm = normalize_clinical_term(word_matches[0].group(0))
        if first_norm in _CLINICAL_NON_NAME_WORDS or first_norm in MEDICAL_STOPLIST:
            continue

        valid_words = []
        for wm in word_matches:
            w_norm = normalize_clinical_term(wm.group(0))
            if w_norm in _CLINICAL_NON_NAME_WORDS or w_norm in MEDICAL_STOPLIST:
                break
            valid_words.append(wm)

        if len(valid_words) < 2:
            continue

        s = cand_start + valid_words[0].start()
        e = cand_start + valid_words[-1].end()
        candidate_text = text[s:e]

        if is_filtered_clinical_span(candidate_text):
            continue
        if _overlaps_any(s, e, spans):
            continue

        spans.append(
            Span(
                start=s,
                end=e,
                entity_type=EntityType.PERSONA,
                text=candidate_text,
                source="ner",
                confidence=0.85,
            )
        )

    spans.sort(key=lambda sp: (sp.start, -(sp.end - sp.start)))
    return spans
