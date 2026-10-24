"""Motor de métricas por span (exacto y solape), recall estructurado (CE2) y fugas residuales (§10)."""

from __future__ import annotations

import hashlib
import math
from pathlib import Path
from typing import Any

from tapaito.schemas import EntityType, PublicEntitySpan, Span

BENCH_ENTITY_TYPES: tuple[str, ...] = (
    EntityType.CEDULA.value,
    EntityType.NIT.value,
    EntityType.CELULAR.value,
    EntityType.CORREO.value,
    EntityType.RADICADO.value,
    EntityType.PERSONA.value,
    EntityType.DIRECCION.value,
    EntityType.UBICACION.value,
    EntityType.ORGANIZACION.value,
    EntityType.FECHA_NAC.value,
    EntityType.CUENTA.value,
)

STRUCTURED_TYPES_SET: frozenset[str] = frozenset(
    {
        EntityType.CEDULA.value,
        EntityType.NIT.value,
        EntityType.CELULAR.value,
        EntityType.CORREO.value,
        EntityType.RADICADO.value,
    }
)


def _normalize_pred_span(sp: PublicEntitySpan | Span | dict[str, Any]) -> dict[str, Any]:
    if isinstance(sp, dict):
        etype = sp["entity_type"]
        return {
            "start": int(sp["start"]),
            "end": int(sp["end"]),
            "entity_type": etype.value if isinstance(etype, EntityType) else str(etype),
            "source": str(sp.get("source", "regex")),
        }
    return {
        "start": int(sp.start),
        "end": int(sp.end),
        "entity_type": sp.entity_type.value if isinstance(sp.entity_type, EntityType) else str(sp.entity_type),
        "source": str(sp.source),
    }


def _compute_prf(tp: int, fp: int, fn: int) -> dict[str, float | int]:
    precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0 if fn == 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0
    f1 = (
        (2 * precision * recall) / (precision + recall)
        if (precision + recall) > 0
        else 0.0
    )
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
    }


def _types_compatible_for_overlap(gold_type: str, pred_type: str) -> bool:
    if gold_type == pred_type:
        return True
    if pred_type == EntityType.RESIDUO.value:
        return True
    return False


def _match_spans_exact(
    golds: list[dict[str, Any]],
    preds: list[dict[str, Any]],
) -> tuple[set[int], set[int]]:
    matched_g: set[int] = set()
    matched_p: set[int] = set()
    for g_idx, g in enumerate(golds):
        for p_idx, p in enumerate(preds):
            if p_idx in matched_p:
                continue
            if (
                g["start"] == p["start"]
                and g["end"] == p["end"]
                and (
                    g["entity_type"] == p["entity_type"]
                    or p["entity_type"] == EntityType.RESIDUO.value
                )
            ):
                matched_g.add(g_idx)
                matched_p.add(p_idx)
                break
    return matched_g, matched_p


def _match_spans_overlap(
    golds: list[dict[str, Any]],
    preds: list[dict[str, Any]],
) -> tuple[set[int], set[int]]:
    matched_g: set[int] = set()
    matched_p: set[int] = set()

    # Emparejar primero los de mayor solape con tipo compatible
    candidates: list[tuple[int, int, int]] = []
    for g_idx, g in enumerate(golds):
        for p_idx, p in enumerate(preds):
            overlap = max(0, min(g["end"], p["end"]) - max(g["start"], p["start"]))
            if overlap > 0 and _types_compatible_for_overlap(g["entity_type"], p["entity_type"]):
                candidates.append((overlap, g_idx, p_idx))

    candidates.sort(key=lambda x: (-x[0], x[1], x[2]))
    for _ov, g_idx, p_idx in candidates:
        if g_idx not in matched_g and p_idx not in matched_p:
            matched_g.add(g_idx)
            matched_p.add(p_idx)

    return matched_g, matched_p


def evaluate_predictions(
    gold_spans: list[dict[str, Any]],
    pred_spans: list[PublicEntitySpan | Span | dict[str, Any]],
    masked_text: str,
) -> dict[str, Any]:
    """Evalúa un caso individual calculando métricas exactas, de solape, estructuradas y fugas."""
    norm_preds = [_normalize_pred_span(p) for p in pred_spans]
    norm_golds = [
        {
            "start": int(g["start"]),
            "end": int(g["end"]),
            "entity_type": str(g["entity_type"]),
            "text": str(g["text"]),
        }
        for g in gold_spans
    ]

    exact_g, exact_p = _match_spans_exact(norm_golds, norm_preds)
    overlap_g, overlap_p = _match_spans_overlap(norm_golds, norm_preds)

    # Fugas residuales: ¿sigue apareciendo gold["text"] visible dentro de masked_text?
    leaked_indices: set[int] = set()
    for idx, g in enumerate(norm_golds):
        surface = g["text"].strip()
        if surface and surface in masked_text:
            leaked_indices.add(idx)

    by_type: dict[str, dict[str, Any]] = {}
    for etype in BENCH_ENTITY_TYPES:
        g_indices = [i for i, g in enumerate(norm_golds) if g["entity_type"] == etype]
        p_indices = [i for i, p in enumerate(norm_preds) if p["entity_type"] == etype]

        tp_ex = sum(1 for i in g_indices if i in exact_g)
        fn_ex = len(g_indices) - tp_ex
        fp_ex = sum(1 for i in p_indices if i not in exact_p)

        tp_ov = sum(1 for i in g_indices if i in overlap_g)
        fn_ov = len(g_indices) - tp_ov
        fp_ov = sum(1 for i in p_indices if i not in overlap_p)

        leaked_t = sum(1 for i in g_indices if i in leaked_indices)
        total_t = len(g_indices)
        leak_rate_t = round(leaked_t / total_t, 4) if total_t > 0 else 0.0

        by_type[etype] = {
            "gold_count": total_t,
            "pred_count": len(p_indices),
            "exact": _compute_prf(tp_ex, fp_ex, fn_ex),
            "overlap": _compute_prf(tp_ov, fp_ov, fn_ov),
            "leaked_count": leaked_t,
            "residual_leak_rate": leak_rate_t,
        }

    # Global micro-average
    tp_ex_all = len(exact_g)
    fn_ex_all = len(norm_golds) - tp_ex_all
    fp_ex_all = len(norm_preds) - len(exact_p)

    tp_ov_all = len(overlap_g)
    fn_ov_all = len(norm_golds) - tp_ov_all
    fp_ov_all = len(norm_preds) - len(overlap_p)

    # Agregado de Identificadores Estructurados (CE2)
    struct_g_indices = [
        i for i, g in enumerate(norm_golds) if g["entity_type"] in STRUCTURED_TYPES_SET
    ]
    struct_p_indices = [
        i for i, p in enumerate(norm_preds) if p["entity_type"] in STRUCTURED_TYPES_SET
    ]
    tp_ex_st = sum(1 for i in struct_g_indices if i in exact_g)
    fn_ex_st = len(struct_g_indices) - tp_ex_st
    fp_ex_st = sum(1 for i in struct_p_indices if i not in exact_p)

    tp_ov_st = sum(1 for i in struct_g_indices if i in overlap_g)
    fn_ov_st = len(struct_g_indices) - tp_ov_st
    fp_ov_st = sum(1 for i in struct_p_indices if i not in overlap_p)

    leaked_struct = sum(1 for i in struct_g_indices if i in leaked_indices)
    total_struct = len(struct_g_indices)

    total_gold = len(norm_golds)
    leaked_total = len(leaked_indices)
    residual_leak_rate = round(leaked_total / total_gold, 4) if total_gold > 0 else 0.0

    return {
        "exact": _compute_prf(tp_ex_all, fp_ex_all, fn_ex_all),
        "overlap": _compute_prf(tp_ov_all, fp_ov_all, fn_ov_all),
        "structured": {
            "exact": _compute_prf(tp_ex_st, fp_ex_st, fn_ex_st),
            "overlap": _compute_prf(tp_ov_st, fp_ov_st, fn_ov_st),
            "leaked_count": leaked_struct,
            "total_gold": total_struct,
            "residual_leak_rate": round(leaked_struct / total_struct, 4)
            if total_struct > 0
            else 0.0,
        },
        "by_type": by_type,
        "leaked_entities_count": leaked_total,
        "total_gold_entities": total_gold,
        "residual_leak_rate": residual_leak_rate,
    }


def _percentile(sorted_vals: list[float], pct: float) -> float:
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return round(sorted_vals[0], 2)
    idx = (pct / 100.0) * (len(sorted_vals) - 1)
    lo = int(math.floor(idx))
    hi = int(math.ceil(idx))
    if lo == hi:
        return round(sorted_vals[lo], 2)
    weight = idx - lo
    return round(sorted_vals[lo] * (1.0 - weight) + sorted_vals[hi] * weight, 2)


def evaluate_corpus(
    case_results: list[dict[str, Any]],
    latencies_ms: list[float] | None = None,
) -> dict[str, Any]:
    """Agrega los resultados de múltiples casos en métricas globales, estructuradas y por tipo."""
    tp_ex = sum(int(r["exact"]["tp"]) for r in case_results)
    fp_ex = sum(int(r["exact"]["fp"]) for r in case_results)
    fn_ex = sum(int(r["exact"]["fn"]) for r in case_results)

    tp_ov = sum(int(r["overlap"]["tp"]) for r in case_results)
    fp_ov = sum(int(r["overlap"]["fp"]) for r in case_results)
    fn_ov = sum(int(r["overlap"]["fn"]) for r in case_results)

    st_tp_ex = sum(int(r["structured"]["exact"]["tp"]) for r in case_results)
    st_fp_ex = sum(int(r["structured"]["exact"]["fp"]) for r in case_results)
    st_fn_ex = sum(int(r["structured"]["exact"]["fn"]) for r in case_results)

    st_tp_ov = sum(int(r["structured"]["overlap"]["tp"]) for r in case_results)
    st_fp_ov = sum(int(r["structured"]["overlap"]["fp"]) for r in case_results)
    st_fn_ov = sum(int(r["structured"]["overlap"]["fn"]) for r in case_results)
    st_leaked = sum(int(r["structured"]["leaked_count"]) for r in case_results)
    st_total = sum(int(r["structured"]["total_gold"]) for r in case_results)

    by_type: dict[str, dict[str, Any]] = {}
    for etype in BENCH_ENTITY_TYPES:
        t_gold = sum(int(r["by_type"][etype]["gold_count"]) for r in case_results)
        t_pred = sum(int(r["by_type"][etype]["pred_count"]) for r in case_results)
        t_tp_ex = sum(int(r["by_type"][etype]["exact"]["tp"]) for r in case_results)
        t_fp_ex = sum(int(r["by_type"][etype]["exact"]["fp"]) for r in case_results)
        t_fn_ex = sum(int(r["by_type"][etype]["exact"]["fn"]) for r in case_results)

        t_tp_ov = sum(int(r["by_type"][etype]["overlap"]["tp"]) for r in case_results)
        t_fp_ov = sum(int(r["by_type"][etype]["overlap"]["fp"]) for r in case_results)
        t_fn_ov = sum(int(r["by_type"][etype]["overlap"]["fn"]) for r in case_results)
        t_leaked = sum(int(r["by_type"][etype]["leaked_count"]) for r in case_results)

        by_type[etype] = {
            "gold_count": t_gold,
            "pred_count": t_pred,
            "exact": _compute_prf(t_tp_ex, t_fp_ex, t_fn_ex),
            "overlap": _compute_prf(t_tp_ov, t_fp_ov, t_fn_ov),
            "leaked_count": t_leaked,
            "residual_leak_rate": round(t_leaked / t_gold, 4) if t_gold > 0 else 0.0,
        }

    total_gold = sum(int(r["total_gold_entities"]) for r in case_results)
    leaked_total = sum(int(r["leaked_entities_count"]) for r in case_results)
    residual_leak_rate = round(leaked_total / total_gold, 4) if total_gold > 0 else 0.0

    sorted_lats = sorted(latencies_ms or [])
    mean_lat = round(sum(sorted_lats) / len(sorted_lats), 2) if sorted_lats else 0.0

    return {
        "num_cases": len(case_results),
        "global": {
            "exact": _compute_prf(tp_ex, fp_ex, fn_ex),
            "overlap": _compute_prf(tp_ov, fp_ov, fn_ov),
        },
        "structured": {
            "exact": _compute_prf(st_tp_ex, st_fp_ex, st_fn_ex),
            "overlap": _compute_prf(st_tp_ov, st_fp_ov, st_fn_ov),
            "leaked_count": st_leaked,
            "total_gold": st_total,
            "residual_leak_rate": round(st_leaked / st_total, 4) if st_total > 0 else 0.0,
        },
        "by_type": by_type,
        "leaked_entities_count": leaked_total,
        "total_gold_entities": total_gold,
        "residual_leak_rate": residual_leak_rate,
        "latency_ms": {
            "p50": _percentile(sorted_lats, 50.0),
            "p95": _percentile(sorted_lats, 95.0),
            "mean": mean_lat,
        },
    }


def verify_test_split_integrity(test_dir: Path = Path("bench/data/test")) -> bool:
    """Verifica que el SHA-256 actual de bench/data/test/dataset.jsonl coincida con sha256.txt."""
    dataset_path = test_dir / "dataset.jsonl"
    sha_path = test_dir / "sha256.txt"
    if not dataset_path.exists() or not sha_path.exists():
        return False

    expected_sha = sha_path.read_text(encoding="utf-8").strip().lower()
    actual_sha = hashlib.sha256(dataset_path.read_bytes()).hexdigest().lower()
    return bool(expected_sha) and (actual_sha == expected_sha)
