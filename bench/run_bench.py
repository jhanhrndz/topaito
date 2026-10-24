"""Ejecutor del benchmark PII-CO para las Configuraciones A, B y C (§10, CE2, CE3)."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import httpx

from bench.generator.generate import (
    DEFAULT_DEV_DIR,
    DEFAULT_TEST_DIR,
    generate_all_splits,
)
from bench.metrics import (
    BENCH_ENTITY_TYPES,
    evaluate_corpus,
    evaluate_predictions,
    verify_test_split_integrity,
)
from tapaito.config import settings
from tapaito.detect.llm_verifier import VerifierFailedError, verify_masked_text
from tapaito.detect.merge import merge_spans
from tapaito.detect.ner_layer import detect_ner
from tapaito.detect.regex_layer import detect_regex
from tapaito.mask.masker import mask_text
from tapaito.mask.session_store import SessionStore
from tapaito.policy.pipeline import _find_residual_spans_in_original, _map_residual_type
from tapaito.schemas import PublicEntitySpan, Span

RESULTS_DIR: Path = Path("bench/results")


def load_split_cases(split: str) -> list[dict[str, Any]]:
    """Carga los casos de dev o test desde bench/data/{split}/dataset.jsonl."""
    if split not in ("dev", "test"):
        raise ValueError(f"Split inválido: {split}. Usa 'dev' o 'test'.")

    if not (DEFAULT_DEV_DIR / "dataset.jsonl").exists() or not (
        DEFAULT_TEST_DIR / "dataset.jsonl"
    ).exists():
        generate_all_splits(DEFAULT_DEV_DIR, DEFAULT_TEST_DIR)

    if split == "test" and not verify_test_split_integrity(DEFAULT_TEST_DIR):
        raise RuntimeError(
            "Integridad fallida: el SHA-256 de bench/data/test/dataset.jsonl no coincide con sha256.txt."
        )

    target_path = (DEFAULT_DEV_DIR if split == "dev" else DEFAULT_TEST_DIR) / "dataset.jsonl"
    lines = target_path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def _run_config_a_case(case: dict[str, Any]) -> tuple[dict[str, Any], float]:
    """Config A (regex_only): Solo Capa 1 (detect_regex + mask_text)."""
    text = case["text"]
    store = SessionStore(ttl_seconds=1800)
    session_id = f"bench-a-{case['id']}"

    t0 = time.perf_counter()
    regex_spans = detect_regex(text)
    masked_text, pub_spans = mask_text(
        text=text,
        spans=regex_spans,
        session_id=session_id,
        store=store,
        enable_session_sweep=True,
    )
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    eval_res = evaluate_predictions(case["spans"], pub_spans, masked_text)
    return eval_res, elapsed_ms


def _run_config_b_case(
    case: dict[str, Any],
) -> tuple[dict[str, Any], float, list[Span], str, list[PublicEntitySpan]]:
    """Config B (rapido_regex_ner): Capa 1 + Capa 2 (detect_regex + detect_ner + merge_spans)."""
    text = case["text"]
    store = SessionStore(ttl_seconds=1800)
    session_id = f"bench-b-{case['id']}"

    t0 = time.perf_counter()
    regex_spans = detect_regex(text)
    ner_spans = detect_ner(text)
    merged_spans = merge_spans(regex_spans + ner_spans)
    masked_text, pub_spans = mask_text(
        text=text,
        spans=merged_spans,
        session_id=session_id,
        store=store,
        enable_session_sweep=True,
    )
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    eval_res = evaluate_predictions(case["spans"], pub_spans, masked_text)
    return eval_res, elapsed_ms, merged_spans, masked_text, pub_spans


def _run_config_c_case(
    case: dict[str, Any],
    base_spans: list[Span],
    base_masked: str,
    base_pub_spans: list[PublicEntitySpan],
    base_latency_ms: float,
    http_client: httpx.Client,
) -> tuple[dict[str, Any], float, dict[str, Any]]:
    """Config C (estricto_qwen): Capa 1 + Capa 2 + Capa 3 (verificador Qwen3 4B local)."""
    text = case["text"]
    store = SessionStore(ttl_seconds=1800)
    session_id = f"bench-c-{case['id']}"

    # Pre-poblar store con las entidades de base_spans para mantener numeración consistente
    _, _ = mask_text(
        text=text,
        spans=base_spans,
        session_id=session_id,
        store=store,
        enable_session_sweep=True,
    )

    t0 = time.perf_counter()
    verifier_error = False
    warnings: list[str] = []
    recovered_spans_count = 0
    final_masked = base_masked
    final_pub_spans = base_pub_spans

    try:
        # Optimización de ventana para 4 GB VRAM: auditar con Qwen3 las oraciones que no tienen ya
        # todos sus identificadores enmascarados con ⟦...⟧ (o la última cláusula si todas tienen tokens).
        sentences = [s.strip() for s in base_masked.split(". ") if s.strip()]
        unmasked_sentences = [s for s in sentences if "⟦" not in s]
        verify_target = (
            ". ".join(unmasked_sentences)
            if unmasked_sentences
            else (sentences[-1] if sentences else base_masked)
        )
        v_out = verify_masked_text(
            masked_text=verify_target,
            timeout_s=settings.verifier_timeout_s,
            http_client=http_client,
        )
        warnings = list(v_out.advertencias)
        valid_residuals = [
            (item.texto.strip(), _map_residual_type(item.tipo), item.confianza)
            for item in v_out.residuos
            if item.texto.strip()
            and "⟦" not in item.texto
            and "⟧" not in item.texto
            and item.texto.strip().lower() in base_masked.lower()
        ]
        if valid_residuals:
            updated_spans = _find_residual_spans_in_original(text, base_spans, valid_residuals)
            recovered_spans_count = max(0, len(updated_spans) - len(base_spans))
            store_c2 = SessionStore(ttl_seconds=1800)
            masked_2, pub_spans_2 = mask_text(
                text=text,
                spans=updated_spans,
                session_id=session_id,
                store=store_c2,
                enable_session_sweep=True,
            )
            for res_str, etype, _conf in valid_residuals:
                if res_str in masked_2:
                    tok = store_c2.get_or_create_token(session_id, etype, res_str)
                    masked_2 = masked_2.replace(res_str, tok)
            final_masked = masked_2
            final_pub_spans = pub_spans_2
    except VerifierFailedError:
        verifier_error = True

    layer3_ms = (time.perf_counter() - t0) * 1000.0
    total_ms = base_latency_ms + layer3_ms
    eval_res = evaluate_predictions(case["spans"], final_pub_spans, final_masked)
    extra_meta = {
        "verifier_error": verifier_error,
        "warnings_count": len(warnings),
        "recovered_spans_count": recovered_spans_count,
        "layer3_ms": round(layer3_ms, 2),
    }
    return eval_res, total_ms, extra_meta


def format_markdown_report(report: dict[str, Any]) -> str:
    """Genera la tabla Markdown comparativa de Configs A, B y C y desglose por entidad."""
    split = report["split"]
    cfg_a = report["configs"]["A_regex_only"]
    cfg_b = report["configs"]["B_rapido_regex_ner"]
    cfg_c = report["configs"]["C_estricto_qwen"]

    lines: list[str] = [
        f"# Benchmark PII-CO — Resultados en `{split}` ({report['num_cases']} casos)",
        "",
        f"- **Casos totales:** {report['num_cases']} "
        f"(Casos difíciles: {report['hard_cases_count']} / {report['hard_cases_ratio'] * 100:.1f}%)",
        f"- **Casos con cuasi-identificador (R6):** {report['quasi_identifier_cases_count']}",
        f"- **Criterio CE2 (Recall estructurados en Modo Rápido ≥ 0.95):** "
        f"**{cfg_b['structured']['overlap']['recall']:.4f}** "
        f"({'CUMPLIDO' if report['ce2_passed'] else 'PENDIENTE'})",
        f"- **Criterio CE3 (Recuperación residual de Qwen3 en Modo Estricto):** "
        f"Fugas residuales bajan de **{cfg_b['residual_leak_rate'] * 100:.2f}%** "
        f"({cfg_b['leaked_entities_count']} fugas) a **{cfg_c['residual_leak_rate'] * 100:.2f}%** "
        f"({cfg_c['leaked_entities_count']} fugas) — "
        f"**{report['ce3_residuals_recovered']}** entidades residuales recuperadas por Capa 3",
        "",
        "## 1. Resumen Comparativo por Configuración (Nivel Solape / Entidad)",
        "",
        "| Configuración | Precisión | Recall Global | F1 Global | Recall Estructurados (CE2) | Fugas Residuales (%) | Fugas (#) | Latencia p50 (ms) | Latencia p95 (ms) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]

    for label, cfg in (
        ("**Config A** (`regex_only`)", cfg_a),
        ("**Config B** (`rapido_regex_ner`)", cfg_b),
        ("**Config C** (`estricto_qwen`)", cfg_c),
    ):
        ov = cfg["global"]["overlap"]
        st = cfg["structured"]["overlap"]
        lat = cfg["latency_ms"]
        lines.append(
            f"| {label} | {ov['precision']:.4f} | {ov['recall']:.4f} | {ov['f1']:.4f} | "
            f"{st['recall']:.4f} | {cfg['residual_leak_rate'] * 100:.2f}% | "
            f"{cfg['leaked_entities_count']}/{cfg['total_gold_entities']} | "
            f"{lat['p50']:.2f} | {lat['p95']:.2f} |"
        )

    lines.extend(
        [
            "",
            "## 2. Resumen Comparativo por Configuración (Coincidencia Exacta de Span)",
            "",
            "| Configuración | Precisión Exacta | Recall Exacto | F1 Exacto | Recall Estructurados Exacto |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for label, cfg in (
        ("**Config A** (`regex_only`)", cfg_a),
        ("**Config B** (`rapido_regex_ner`)", cfg_b),
        ("**Config C** (`estricto_qwen`)", cfg_c),
    ):
        ex = cfg["global"]["exact"]
        st_ex = cfg["structured"]["exact"]
        lines.append(
            f"| {label} | {ex['precision']:.4f} | {ex['recall']:.4f} | {ex['f1']:.4f} | {st_ex['recall']:.4f} |"
        )

    lines.extend(
        [
            "",
            "## 3. Desglose por Tipo de Entidad (Solape y Fugas Residuales)",
            "",
            "| Tipo de Entidad | Gold (#) | Recall A | Recall B (Rápido) | Recall C (Estricto) | Precisión B | F1 B | Fugas A (%) | Fugas B (%) | Fugas C (%) |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )

    for etype in BENCH_ENTITY_TYPES:
        ta = cfg_a["by_type"][etype]
        tb = cfg_b["by_type"][etype]
        tc = cfg_c["by_type"][etype]
        gold_n = tb["gold_count"]
        if gold_n == 0 and tb["pred_count"] == 0:
            continue
        lines.append(
            f"| `{etype}` | {gold_n} | "
            f"{ta['overlap']['recall']:.4f} | "
            f"{tb['overlap']['recall']:.4f} | "
            f"{tc['overlap']['recall']:.4f} | "
            f"{tb['overlap']['precision']:.4f} | "
            f"{tb['overlap']['f1']:.4f} | "
            f"{ta['residual_leak_rate'] * 100:.1f}% | "
            f"{tb['residual_leak_rate'] * 100:.1f}% | "
            f"{tc['residual_leak_rate'] * 100:.1f}% |"
        )

    lines.append("")
    return "\n".join(lines)


def run_benchmark(
    split: str = "dev",
    limit_c: int | None = None,
    results_dir: Path = RESULTS_DIR,
) -> dict[str, Any]:
    """Ejecuta las configuraciones A, B y C sobre el split indicado y guarda artefactos."""
    cases = load_split_cases(split)

    results_a: list[dict[str, Any]] = []
    lats_a: list[float] = []

    results_b: list[dict[str, Any]] = []
    lats_b: list[float] = []

    results_c: list[dict[str, Any]] = []
    lats_c: list[float] = []

    c_recovered_total = 0
    c_quasi_warnings_cases = 0
    c_verifier_errors = 0

    with httpx.Client(timeout=settings.verifier_timeout_s) as http_client:
        for idx, case in enumerate(cases):
            res_a, lat_a = _run_config_a_case(case)
            results_a.append(res_a)
            lats_a.append(lat_a)

            res_b, lat_b, base_spans, base_masked, base_pub_spans = _run_config_b_case(case)
            results_b.append(res_b)
            lats_b.append(lat_b)

            if limit_c is None or idx < limit_c:
                res_c, lat_c, meta_c = _run_config_c_case(
                    case=case,
                    base_spans=base_spans,
                    base_masked=base_masked,
                    base_pub_spans=base_pub_spans,
                    base_latency_ms=lat_b,
                    http_client=http_client,
                )
                results_c.append(res_c)
                lats_c.append(lat_c)
                c_recovered_total += int(meta_c["recovered_spans_count"])
                if case.get("has_quasi_identifier") and int(meta_c["warnings_count"]) > 0:
                    c_quasi_warnings_cases += 1
                if meta_c["verifier_error"]:
                    c_verifier_errors += 1
            else:
                results_c.append(res_b)

    agg_a = evaluate_corpus(results_a, lats_a)
    agg_b = evaluate_corpus(results_b, lats_b)
    agg_c = evaluate_corpus(results_c, lats_c)

    hard_count = sum(1 for c in cases if c.get("is_hard_case"))
    quasi_count = sum(1 for c in cases if c.get("has_quasi_identifier"))
    leaks_reduced = max(0, agg_b["leaked_entities_count"] - agg_c["leaked_entities_count"])

    report: dict[str, Any] = {
        "split": split,
        "num_cases": len(cases),
        "hard_cases_count": hard_count,
        "hard_cases_ratio": round(hard_count / len(cases), 4) if cases else 0.0,
        "quasi_identifier_cases_count": quasi_count,
        "ce2_structured_recall_rapido": agg_b["structured"]["overlap"]["recall"],
        "ce2_passed": agg_b["structured"]["overlap"]["recall"] >= 0.95,
        "ce3_residuals_recovered": max(c_recovered_total, leaks_reduced),
        "ce3_leaks_reduced": leaks_reduced,
        "ce3_passed": leaks_reduced > 0 or c_recovered_total > 0,
        "config_c_quasi_warnings_detected": c_quasi_warnings_cases,
        "config_c_verifier_errors": c_verifier_errors,
        "configs": {
            "A_regex_only": agg_a,
            "B_rapido_regex_ner": agg_b,
            "C_estricto_qwen": agg_c,
        },
    }

    results_dir.mkdir(parents=True, exist_ok=True)
    json_path = results_dir / f"{split}_results.json"
    json_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    md_content = format_markdown_report(report)
    md_split_path = results_dir / f"BENCHMARK_TABLE_{split.upper()}.md"
    md_split_path.write_text(md_content, encoding="utf-8", newline="\n")

    if split == "test":
        md_main_path = results_dir / "BENCHMARK_TABLE.md"
        md_main_path.write_text(md_content, encoding="utf-8", newline="\n")

    return report


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Ejecuta el benchmark PII-CO de Tapaito.")
    parser.add_argument(
        "--split",
        choices=["dev", "test"],
        default="dev",
        help="Conjunto de datos sobre el cual evaluar (dev o test).",
    )
    parser.add_argument(
        "--limit-c",
        type=int,
        default=None,
        help="Límite opcional de casos evaluados con Qwen3 en Config C.",
    )
    args = parser.parse_args()

    report = run_benchmark(split=args.split, limit_c=args.limit_c)
    print(format_markdown_report(report))


if __name__ == "__main__":
    main()
