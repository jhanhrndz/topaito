"""Pruebas unitarias y de integración para el generador PII-CO, métricas y utilidad (Fase 3)."""

from __future__ import annotations

from pathlib import Path

from bench.generator.generate import (
    SEED_DEV,
    SEED_TEST,
    generate_all_splits,
    generate_split_cases,
)
from bench.metrics import (
    evaluate_corpus,
    evaluate_predictions,
    verify_test_split_integrity,
)
from bench.utility_eval import run_utility_evaluation
from tapaito.detect.validators import validate_celular_co, validate_nit_dv, validate_radicado_co
from tapaito.schemas import EntityType, PublicEntitySpan, Span


def test_generator_determinism_and_exact_offsets() -> None:
    """Dos ejecuciones con la misma semilla producen casos idénticos y offsets 100 % exactos."""
    dev_a = generate_split_cases(seed=SEED_DEV, split="dev", count=30)
    dev_b = generate_split_cases(seed=SEED_DEV, split="dev", count=30)
    test_a = generate_split_cases(seed=SEED_TEST, split="test", count=50)

    assert len(dev_a) == 30
    assert len(test_a) == 50
    assert dev_a == dev_b

    # Verificar que dev y test no compartan textos idénticos
    dev_texts = {c["text"] for c in dev_a}
    test_texts = {c["text"] for c in test_a}
    assert dev_texts.isdisjoint(test_texts)

    expected_genres = {
        "historia_clinica",
        "epicrisis",
        "orden_medica",
        "tutela_salud",
        "seguimiento_paciente",
    }
    assert {c["genre"] for c in dev_a} == expected_genres
    assert {c["genre"] for c in test_a} == expected_genres

    for case in dev_a + test_a:
        text = case["text"]
        assert len(case["spans"]) > 0
        for sp in case["spans"]:
            s, e = sp["start"], sp["end"]
            assert 0 <= s < e <= len(text)
            assert text[s:e] == sp["text"], f"Offset desalineado en {case['id']}: {sp}"

            # Verificar validez estructural de NIT, RADICADO y CELULAR generados
            if sp["entity_type"] == EntityType.NIT.value:
                parts = sp["text"].split("-")
                assert len(parts) == 2
                assert validate_nit_dv(parts[0], parts[1]), f"NIT inválido: {sp['text']}"
            elif sp["entity_type"] == EntityType.RADICADO.value:
                assert validate_radicado_co(sp["text"]), f"Radicado inválido: {sp['text']}"
            elif sp["entity_type"] == EntityType.CELULAR.value:
                assert validate_celular_co(sp["text"]), f"Celular inválido: {sp['text']}"


def test_generator_hard_cases_and_quasi_identifiers_ratio() -> None:
    """Al menos 40 % de los casos en dev y test son difíciles y existen >= 6 cuasi-identificadores."""
    dev_cases = generate_split_cases(seed=SEED_DEV, split="dev", count=30)
    test_cases = generate_split_cases(seed=SEED_TEST, split="test", count=50)

    dev_hard_ratio = sum(1 for c in dev_cases if c["is_hard_case"]) / len(dev_cases)
    test_hard_ratio = sum(1 for c in test_cases if c["is_hard_case"]) / len(test_cases)

    assert dev_hard_ratio >= 0.40
    assert test_hard_ratio >= 0.40

    total_quasi = sum(1 for c in dev_cases + test_cases if c["has_quasi_identifier"])
    assert total_quasi >= 6


def test_evaluate_predictions_exact_overlap_structured_and_leaks() -> None:
    """Verifica el cálculo de TP/FP/FN, exact/overlap, structured_recall (CE2) y residual_leak_rate."""
    gold_spans = [
        {"start": 9, "end": 19, "entity_type": "PERSONA", "text": "Juan Perez"},
        {"start": 27, "end": 37, "entity_type": "CEDULA", "text": "1032456789"},
        {"start": 43, "end": 53, "entity_type": "CELULAR", "text": "3104567890"},
        {"start": 68, "end": 87, "entity_type": "PERSONA", "text": "luz marina betancur"},
    ]

    # Predicciones simuladas:
    # - Juan Perez detectado exacto
    # - 1032456789 detectado exacto
    # - 3104567890 detectado con 1 espacio extra al inicio (overlap sí, exact no)
    # - luz marina betancur NO detectada (FN y además queda visible en masked_text -> fuga residual)
    # - Un falso positivo en [0, 8] ("Paciente")
    pred_spans = [
        PublicEntitySpan(
            start=0,
            end=8,
            entity_type=EntityType.PERSONA,
            token="⟦PERSONA_99⟧",
            source="ner",
        ),
        PublicEntitySpan(
            start=9,
            end=19,
            entity_type=EntityType.PERSONA,
            token="⟦PERSONA_1⟧",
            source="ner",
        ),
        Span(
            start=27,
            end=37,
            entity_type=EntityType.CEDULA,
            text="1032456789",
            source="regex",
        ),
        PublicEntitySpan(
            start=42,
            end=53,
            entity_type=EntityType.CELULAR,
            token="⟦CELULAR_1⟧",
            source="regex",
        ),
    ]
    masked_text = (
        "⟦PERSONA_99⟧ ⟦PERSONA_1⟧ con CC ⟦CEDULA_1⟧, cel⟦CELULAR_1⟧ "
        "y acompañante luz marina betancur."
    )

    res = evaluate_predictions(gold_spans, pred_spans, masked_text)

    # Exact match: 2 TP (Juan Perez, 1032456789), 2 FP (Paciente, cel+espacio), 2 FN (celular exacto, luz marina)
    assert res["exact"]["tp"] == 2
    assert res["exact"]["fp"] == 2
    assert res["exact"]["fn"] == 2
    assert res["exact"]["precision"] == 0.5
    assert res["exact"]["recall"] == 0.5
    assert res["exact"]["f1"] == 0.5

    # Overlap match: 3 TP (Juan Perez, 1032456789, 3104567890), 1 FP (Paciente), 1 FN (luz marina)
    assert res["overlap"]["tp"] == 3
    assert res["overlap"]["fp"] == 1
    assert res["overlap"]["fn"] == 1
    assert res["overlap"]["precision"] == 0.75
    assert res["overlap"]["recall"] == 0.75
    assert res["overlap"]["f1"] == 0.75

    # Structured (CEDULA y CELULAR): en overlap ambos fueron detectados -> recall 1.0
    assert res["structured"]["overlap"]["tp"] == 2
    assert res["structured"]["overlap"]["fn"] == 0
    assert res["structured"]["overlap"]["recall"] == 1.0
    assert res["structured"]["exact"]["tp"] == 1
    assert res["structured"]["exact"]["fn"] == 1
    assert res["structured"]["exact"]["recall"] == 0.5

    # Fugas residuales: de 4 entidades gold, solo "luz marina betancur" sigue en masked_text (1/4 = 0.25)
    assert res["leaked_entities_count"] == 1
    assert res["total_gold_entities"] == 4
    assert res["residual_leak_rate"] == 0.25
    assert res["by_type"]["PERSONA"]["residual_leak_rate"] == 0.5
    assert res["by_type"]["CEDULA"]["residual_leak_rate"] == 0.0

    # Corpus aggregation
    corpus_res = evaluate_corpus([res], latencies_ms=[10.0, 20.0, 30.0])
    assert corpus_res["global"]["overlap"]["recall"] == 0.75
    assert corpus_res["structured"]["overlap"]["recall"] == 1.0
    assert corpus_res["residual_leak_rate"] == 0.25
    assert corpus_res["latency_ms"]["p50"] == 20.0


def test_verify_test_split_integrity(tmp_path: Path) -> None:
    """Verifica el hash SHA-256 del split test y detecta modificaciones no autorizadas."""
    dev_dir = tmp_path / "dev"
    test_dir = tmp_path / "test"
    generate_all_splits(dev_dir=dev_dir, test_dir=test_dir)

    assert (dev_dir / "dataset.jsonl").exists()
    assert (test_dir / "dataset.jsonl").exists()
    assert (test_dir / "sha256.txt").exists()

    assert verify_test_split_integrity(test_dir) is True

    # Si se adultera un carácter del conjunto test, la verificación debe fallar
    dataset_path = test_dir / "dataset.jsonl"
    original_content = dataset_path.read_text(encoding="utf-8")
    dataset_path.write_text(original_content + "\n", encoding="utf-8")
    assert verify_test_split_integrity(test_dir) is False


def test_utility_evaluation_meets_ce4(tmp_path: Path) -> None:
    """Ejecuta la evaluación de utilidad sobre 12 casos y comprueba CE4 (tasa >= 0.95)."""
    out_file = tmp_path / "utility_results.json"
    summary = run_utility_evaluation(output_path=out_file)

    assert out_file.exists()
    assert summary["num_cases"] == 12
    assert summary["mean_reinsertion_rate"] >= 0.95
    assert summary["ce4_passed"] is True
    assert summary["clinical_field_preservation_rate"] >= 0.95
