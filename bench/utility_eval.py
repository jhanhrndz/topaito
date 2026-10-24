"""Evaluación de utilidad clínica y reinserción de tokens en 12 casos sintéticos (CE4 / §10)."""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Any

from bench.generator.generate import SEED_DEV, generate_split_cases
from tapaito.detect.merge import merge_spans
from tapaito.detect.ner_layer import detect_ner
from tapaito.detect.regex_layer import detect_regex
from tapaito.mask.masker import inject_system_instruction, mask_text
from tapaito.mask.session_store import SessionStore
from tapaito.restore.reinsert import reinsert_tokens
from tapaito.upstream.client import call_upstream_chat

DEFAULT_UTILITY_OUTPUT: Path = Path("bench/results/utility_results.json")


def _extract_expected_clinical_fields(text: str, spans: list[dict[str, Any]]) -> dict[str, Any]:
    age_match = re.search(r"\b(\d{1,3})\s*a[ñn]os\b", text, flags=re.IGNORECASE)
    cie10_matches = list(dict.fromkeys(re.findall(r"\b[A-Z]\d{2,3}(?:\.\d)?\b", text)))
    med_matches = list(
        dict.fromkeys(
            re.findall(
                r"\b(?:Losart[aá]n|Acetaminof[eé]n|Metformina|Enalapril|Omeprazol|"
                r"Ibuprofeno|Amoxicilina|Atorvastatina)\b",
                text,
                flags=re.IGNORECASE,
            )
        )
    )
    return {
        "age": age_match.group(1) if age_match else None,
        "cie10": cie10_matches[0] if cie10_matches else None,
        "medication": med_matches[0] if med_matches else None,
        "entities": [sp["text"] for sp in spans],
    }


async def _evaluate_single_utility_case(
    case: dict[str, Any],
) -> dict[str, Any]:
    text = case["text"]
    session_id = f"util-{case['id']}"
    store = SessionStore(ttl_seconds=1800)

    expected_fields = _extract_expected_clinical_fields(text, case["spans"])

    # 1. Respuesta directa sin enmascarar (línea base)
    raw_messages = [
        {
            "role": "system",
            "content": "Resume la nota clínica extrayendo edad, código CIE-10 y medicamento.",
        },
        {"role": "user", "content": text},
    ]
    baseline_resp = await call_upstream_chat(messages=raw_messages)
    baseline_content = str(
        baseline_resp.get("choices", [{}])[0].get("message", {}).get("content", "")
    )

    # 2. Flujo Tapaito: Detectar (Capas 1+2) -> Enmascarar -> Upstream -> Reinsertar
    spans = merge_spans(detect_regex(text) + detect_ner(text))
    masked_text, pub_spans = mask_text(
        text=text,
        spans=spans,
        session_id=session_id,
        store=store,
        enable_session_sweep=True,
    )
    masked_messages = inject_system_instruction(
        [
            {
                "role": "system",
                "content": "Resume la nota clínica extrayendo edad, código CIE-10 y medicamento.",
            },
            {"role": "user", "content": masked_text},
        ]
    )
    upstream_resp = await call_upstream_chat(messages=masked_messages)
    masked_reply = str(
        upstream_resp.get("choices", [{}])[0].get("message", {}).get("content", "")
    )

    session_map = store.get_token_to_value_map(session_id)
    expected_tokens = {sp.token for sp in pub_spans}
    restored_reply, report = reinsert_tokens(
        response_text=masked_reply,
        session_mapping=session_map,
        expected_tokens=expected_tokens,
    )

    # Verificar rúbrica de 4 campos clínicos clave
    age_val = expected_fields["age"]
    cie10_val = expected_fields["cie10"]
    med_val = expected_fields["medication"]

    age_preserved = bool(age_val and age_val in restored_reply)
    cie10_preserved = bool(cie10_val and cie10_val in restored_reply)
    med_preserved = bool(med_val and med_val.lower() in restored_reply.lower())
    identifiers_restored = report.tasa_restauracion >= 0.95 and all(
        val in restored_reply for val in session_map.values()
    )

    rubric_score = (
        int(age_preserved)
        + int(cie10_preserved)
        + int(med_preserved)
        + int(identifiers_restored)
    ) / 4.0

    return {
        "case_id": case["id"],
        "genre": case["genre"],
        "entities_masked": len(pub_spans),
        "reinsertion_rate": report.tasa_restauracion,
        "rubric": {
            "age_preserved": age_preserved,
            "cie10_preserved": cie10_preserved,
            "medication_preserved": med_preserved,
            "identifiers_restored": identifiers_restored,
            "score": round(rubric_score, 4),
        },
        "baseline_excerpt": baseline_content[:140],
        "restored_excerpt": restored_reply[:140],
    }


def run_utility_evaluation(
    output_path: Path = DEFAULT_UTILITY_OUTPUT,
    num_cases: int = 12,
) -> dict[str, Any]:
    """Ejecuta la prueba de utilidad en 12 casos clínicos y escribe utility_results.json."""
    dev_cases = generate_split_cases(seed=SEED_DEV, split="dev", count=30)
    # Seleccionar 12 casos con medicamento POS estándar para evaluar los 4 campos de la rúbrica
    selected: list[dict[str, Any]] = []
    for c in dev_cases:
        fields = _extract_expected_clinical_fields(c["text"], c["spans"])
        if fields["age"] and fields["cie10"] and fields["medication"]:
            selected.append(c)
        if len(selected) == num_cases:
            break

    async def _run_all() -> list[dict[str, Any]]:
        results = []
        for c in selected:
            res = await _evaluate_single_utility_case(c)
            results.append(res)
        return results

    case_evals = asyncio.run(_run_all())

    mean_reinsertion = round(
        sum(float(r["reinsertion_rate"]) for r in case_evals) / len(case_evals), 4
    )
    mean_rubric_score = round(
        sum(float(r["rubric"]["score"]) for r in case_evals) / len(case_evals), 4
    )
    age_rate = round(
        sum(1 for r in case_evals if r["rubric"]["age_preserved"]) / len(case_evals), 4
    )
    cie10_rate = round(
        sum(1 for r in case_evals if r["rubric"]["cie10_preserved"]) / len(case_evals), 4
    )
    med_rate = round(
        sum(1 for r in case_evals if r["rubric"]["medication_preserved"]) / len(case_evals), 4
    )
    id_rate = round(
        sum(1 for r in case_evals if r["rubric"]["identifiers_restored"]) / len(case_evals), 4
    )

    summary: dict[str, Any] = {
        "num_cases": len(case_evals),
        "mean_reinsertion_rate": mean_reinsertion,
        "ce4_passed": mean_reinsertion >= 0.95,
        "clinical_field_preservation_rate": mean_rubric_score,
        "rubric_breakdown": {
            "age_preservation_rate": age_rate,
            "cie10_preservation_rate": cie10_rate,
            "medication_preservation_rate": med_rate,
            "identifiers_restoration_rate": id_rate,
        },
        "cases": case_evals,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return summary


def main() -> None:
    summary = run_utility_evaluation()
    print(
        json.dumps(
            {
                "num_cases": summary["num_cases"],
                "mean_reinsertion_rate": summary["mean_reinsertion_rate"],
                "ce4_passed": summary["ce4_passed"],
                "clinical_field_preservation_rate": summary["clinical_field_preservation_rate"],
                "rubric_breakdown": summary["rubric_breakdown"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
