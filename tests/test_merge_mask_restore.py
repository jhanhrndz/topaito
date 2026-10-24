"""Tests para fusión de spans, almacén de sesión, enmascarado y reinserción tolerante."""

from __future__ import annotations

import time

from tapaito.detect.merge import merge_spans
from tapaito.mask.masker import (
    SYSTEM_TOKEN_INSTRUCTION,
    inject_system_instruction,
    mask_text,
    sweep_session_known_entities,
)
from tapaito.mask.session_store import SessionStore, normalize_entity_value
from tapaito.restore.reinsert import reinsert_tokens
from tapaito.schemas import EntityType, Span

# --- 1. Tests de merge_spans ---


def test_merge_spans_filters_invalid_and_sorts() -> None:
    spans = [
        Span(start=20, end=30, entity_type=EntityType.CEDULA, text="1020304050", source="regex"),
        Span(start=10, end=10, entity_type=EntityType.PERSONA, text="", source="ner"),
        Span(start=15, end=12, entity_type=EntityType.PERSONA, text="", source="ner"),
        Span(start=0, end=8, entity_type=EntityType.PERSONA, text="Juan Paz", source="ner"),
    ]
    merged = merge_spans(spans)
    assert len(merged) == 2
    assert merged[0].start == 0
    assert merged[1].start == 20


def test_merge_spans_priority_regex_over_ner_and_session() -> None:
    # Solape donde regex es más corto pero tiene mayor prioridad de capa que ner y session
    s_ner = Span(
        start=0, end=25, entity_type=EntityType.ORGANIZACION, text="CC 1020304050 de Bogota", source="ner"
    )
    s_regex = Span(
        start=3, end=13, entity_type=EntityType.CEDULA, text="1020304050", source="regex"
    )
    s_session = Span(
        start=0, end=15, entity_type=EntityType.CEDULA, text="CC 1020304050 ", source="session"
    )
    merged = merge_spans([s_ner, s_regex, s_session])
    assert len(merged) == 1
    assert merged[0] == s_regex


def test_merge_spans_session_over_ner_and_length_tiebreaker() -> None:
    # Entre session y ner gana session
    s_ner = Span(start=10, end=22, entity_type=EntityType.PERSONA, text="Carlos Gomez", source="ner")
    s_session = Span(start=10, end=16, entity_type=EntityType.PERSONA, text="Carlos", source="session")
    merged = merge_spans([s_ner, s_session])
    assert merged == [s_session]

    # A igual prioridad de capa, gana el span más largo
    s_short = Span(start=0, end=6, entity_type=EntityType.PERSONA, text="Camila", source="ner")
    s_long = Span(start=0, end=15, entity_type=EntityType.PERSONA, text="Camila Restrepo", source="ner")
    merged_len = merge_spans([s_short, s_long])
    assert merged_len == [s_long]

    # A igual prioridad y longitud, gana el que empiece antes
    s_first = Span(start=0, end=10, entity_type=EntityType.PERSONA, text="Juan Perez", source="ner")
    s_second = Span(start=5, end=15, entity_type=EntityType.PERSONA, text="Perez Soto", source="ner")
    merged_pos = merge_spans([s_second, s_first])
    assert merged_pos == [s_first]


# --- 2. Tests de SessionStore y normalize_entity_value ---


def test_normalize_entity_value_coherence() -> None:
    # Celular con y sin +57
    assert normalize_entity_value(EntityType.CELULAR, "+57 310 456 7890") == "3104567890"
    assert normalize_entity_value(EntityType.CELULAR, "310-456-7890") == "3104567890"
    # Cédula con puntos y sin puntos
    assert normalize_entity_value(EntityType.CEDULA, "79.456.123") == "79456123"
    assert normalize_entity_value(EntityType.CEDULA, "79456123") == "79456123"
    # Persona con mayúsculas/minúsculas, tildes y espacios extra
    assert normalize_entity_value(EntityType.PERSONA, "  Juan   Carlos  Restrepo ") == (
        normalize_entity_value(EntityType.PERSONA, "juan carlos restrepo")
    )
    assert normalize_entity_value(EntityType.PERSONA, "María José Gómez") == (
        normalize_entity_value(EntityType.PERSONA, "maria jose gomez")
    )


def test_session_store_consistency_ttl_and_delete() -> None:
    store = SessionStore(ttl_seconds=1800)
    t1 = store.get_or_create_token("ses-1", EntityType.PERSONA, "Juan Carlos Restrepo")
    t2 = store.get_or_create_token("ses-1", EntityType.PERSONA, "juan carlos   restrepo")
    t3 = store.get_or_create_token("ses-1", EntityType.PERSONA, "Maria Fernanda Lopez")
    assert t1 == "⟦PERSONA_1⟧"
    assert t2 == "⟦PERSONA_1⟧"
    assert t3 == "⟦PERSONA_2⟧"

    c1 = store.get_or_create_token("ses-1", EntityType.CELULAR, "+57 310 456 7890")
    c2 = store.get_or_create_token("ses-1", EntityType.CELULAR, "3104567890")
    assert c1 == "⟦CELULAR_1⟧"
    assert c2 == "⟦CELULAR_1⟧"

    # Conserva la primera forma legible vista
    mapping = store.get_token_to_value_map("ses-1")
    assert mapping["⟦PERSONA_1⟧"] == "Juan Carlos Restrepo"
    assert mapping["⟦PERSONA_2⟧"] == "Maria Fernanda Lopez"
    assert mapping["⟦CELULAR_1⟧"] == "+57 310 456 7890"

    # Borrado explícito de sesión
    assert store.delete_session("ses-1") is True
    assert store.delete_session("ses-1") is False
    assert store.get_token_to_value_map("ses-1") == {}

    # Expiración por TTL
    short_store = SessionStore(ttl_seconds=0)
    short_store.get_or_create_token("ses-ttl", EntityType.CEDULA, "1020304050")
    time.sleep(0.01)
    assert short_store.get_token_to_value_map("ses-ttl") == {}


# --- 3. Tests de mask_text, offsets e inyección de instrucción ---


def test_mask_text_preserves_original_offsets_and_deterministic_numbering() -> None:
    text = (
        "El ciudadano Juan Carlos Restrepo identificado con CC 79.456.123 "
        "y celular +57 310 456 7890 solicita respuesta."
    )
    idx_persona = text.index("Juan Carlos Restrepo")
    idx_cedula = text.index("79.456.123")
    idx_celular = text.index("+57 310 456 7890")

    spans = [
        Span(
            start=idx_celular,
            end=idx_celular + len("+57 310 456 7890"),
            entity_type=EntityType.CELULAR,
            text="+57 310 456 7890",
            source="regex",
        ),
        Span(
            start=idx_persona,
            end=idx_persona + len("Juan Carlos Restrepo"),
            entity_type=EntityType.PERSONA,
            text="Juan Carlos Restrepo",
            source="ner",
        ),
        Span(
            start=idx_cedula,
            end=idx_cedula + len("79.456.123"),
            entity_type=EntityType.CEDULA,
            text="79.456.123",
            source="regex",
        ),
    ]

    store = SessionStore()
    masked, public_spans = mask_text(text, spans, session_id="ses-offset", store=store)

    assert masked == (
        "El ciudadano ⟦PERSONA_1⟧ identificado con CC ⟦CEDULA_1⟧ "
        "y celular ⟦CELULAR_1⟧ solicita respuesta."
    )
    assert len(public_spans) == 3
    # Verificar que original[s.start:s.end] coincide siempre con cada entidad original
    expected_texts = ["Juan Carlos Restrepo", "79.456.123", "+57 310 456 7890"]
    for pub_span, expected in zip(public_spans, expected_texts, strict=True):
        assert text[pub_span.start : pub_span.end] == expected


def test_second_pass_session_sweep_r16() -> None:
    text = (
        "Señor Juan Carlos Restrepo con CC 79.456.123. "
        "Más adelante el documento menciona 79456123 sin prefijo y también a juan carlos restrepo."
    )
    idx_p1 = text.index("Juan Carlos Restrepo")
    idx_c1 = text.index("79.456.123")

    # Solo se detectaron las primeras apariciones con contexto
    initial_spans = [
        Span(
            start=idx_p1,
            end=idx_p1 + len("Juan Carlos Restrepo"),
            entity_type=EntityType.PERSONA,
            text="Juan Carlos Restrepo",
            source="ner",
        ),
        Span(
            start=idx_c1,
            end=idx_c1 + len("79.456.123"),
            entity_type=EntityType.CEDULA,
            text="79.456.123",
            source="regex",
        ),
    ]

    store = SessionStore()
    swept = sweep_session_known_entities(text, initial_spans, "ses-r16", store)
    assert len(swept) == 4

    masked, public_spans = mask_text(
        text, initial_spans, session_id="ses-r16", store=store, enable_session_sweep=True
    )
    assert "79456123" not in masked
    assert "juan carlos restrepo" not in masked
    assert masked.count("⟦PERSONA_1⟧") == 2
    assert masked.count("⟦CEDULA_1⟧") == 2
    assert len(public_spans) == 4
    assert any(s.source == "session" for s in public_spans)


def test_inject_system_instruction_does_not_mutate() -> None:
    msgs = [{"role": "user", "content": "Hola ⟦PERSONA_1⟧"}]
    res = inject_system_instruction(msgs)
    assert len(msgs) == 1
    assert len(res) == 2
    assert res[0]["role"] == "system"
    assert SYSTEM_TOKEN_INSTRUCTION in res[0]["content"]

    # Si ya existe system, lo conserva y añade la instrucción sin duplicarla si se vuelve a llamar
    res2 = inject_system_instruction(res)
    assert len(res2) == 2
    assert res2[0]["content"].count(SYSTEM_TOKEN_INSTRUCTION) == 1


# --- 4. Tests de reinsert_tokens ---


def test_reinsert_tokens_exact_tolerant_unknown_ambiguous_missing() -> None:
    session_mapping = {
        "⟦PERSONA_1⟧": "Juan Carlos Restrepo",
        "⟦CEDULA_1⟧": "79.456.123",
        "⟦CELULAR_1⟧": "+57 310 456 7890",
        "⟦CORREO_1⟧": "juan.restrepo@ejemplo.co",
    }
    expected_tokens = set(session_mapping.keys())

    # Respuesta hostil del LLM:
    # - [persona_1] (variación corchetes + minúsculas)
    # - ⟦ CEDULA-1 ⟧ (espacios + guion)
    # - ((CELULAR_1)) (doble paréntesis)
    # - ⟦PERSONA_99⟧ (token con formato válido pero desconocido en la sesión)
    # - [PERSONA] (token ambiguo sin índice)
    # - ⟦CORREO_1⟧ fue omitido por el LLM -> debe ir a faltantes
    hostile_response = (
        "Estimado [persona_1], su documento ⟦ CEDULA-1 ⟧ y línea ((CELULAR_1)) "
        "fueron validados junto con ⟦PERSONA_99⟧ y el titular [PERSONA]."
    )

    restored_text, report = reinsert_tokens(
        hostile_response,
        session_mapping=session_mapping,
        expected_tokens=expected_tokens,
    )

    assert "Juan Carlos Restrepo" in restored_text
    assert "79.456.123" in restored_text
    assert "+57 310 456 7890" in restored_text
    # El desconocido NO se sustituye
    assert "⟦PERSONA_99⟧" in restored_text
    # El ambiguo NO se sustituye
    assert "[PERSONA]" in restored_text

    assert set(report.restaurados) == {"⟦PERSONA_1⟧", "⟦CEDULA_1⟧", "⟦CELULAR_1⟧"}
    assert report.faltantes == ["⟦CORREO_1⟧"]
    assert report.desconocidos == ["⟦PERSONA_99⟧"]
    assert report.ambiguos == ["[PERSONA]"]
    assert report.tasa_restauracion == 0.75
