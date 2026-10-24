"""Generador determinista de los splits dev (30 casos) y test (50 casos) para PII-CO."""

from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path
from typing import Any

from bench.generator.templates import GENRES, build_clinical_case

SEED_DEV: int = 202601
SEED_TEST: int = 202602

DEFAULT_DEV_DIR: Path = Path("bench/data/dev")
DEFAULT_TEST_DIR: Path = Path("bench/data/test")


def generate_split_cases(seed: int, split: str, count: int) -> list[dict[str, Any]]:
    """Genera una lista determinista de casos sintéticos para el split indicado."""
    rng = random.Random(seed)
    cases: list[dict[str, Any]] = []

    # Al menos 50 % son casos difíciles (>= 40 % requerido por R4 / §10)
    # ~23-24 % incluyen nombre difícil en minúsculas sin etiqueta estándar (Subtipo B - CE3)
    # Al menos 4 en dev y 6 en test incluyen cuasi-identificador (Subtipo C - R6)
    num_hard = max(int(count * 0.50), 1)
    num_lowercase_hard = max(int(round(count * 0.24)), 1)
    num_quasi = 4 if split == "dev" else 6

    for idx in range(count):
        genre = GENRES[idx % len(GENRES)]
        is_hard_case = idx < num_hard
        include_hard_lowercase = idx < num_lowercase_hard
        has_quasi = (num_lowercase_hard <= idx < num_lowercase_hard + num_quasi)

        case = build_clinical_case(
            rng=rng,
            case_index=idx,
            split=split,
            genre=genre,
            is_hard_case=is_hard_case,
            include_hard_lowercase_name=include_hard_lowercase,
            has_quasi_identifier=has_quasi,
        )
        cases.append(case)

    return cases


def compute_file_sha256(path: Path) -> str:
    """Calcula el hash SHA-256 hexadecimal de los bytes exactos de un archivo."""
    raw_bytes = path.read_bytes()
    return hashlib.sha256(raw_bytes).hexdigest()


def write_jsonl_cases(path: Path, cases: list[dict[str, Any]]) -> None:
    """Escribe la lista de casos en formato JSONL UTF-8 con saltos de línea LF estables."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(c, ensure_ascii=False) for c in cases]
    content = "\n".join(lines) + "\n"
    path.write_text(content, encoding="utf-8", newline="\n")


def generate_all_splits(
    dev_dir: Path = DEFAULT_DEV_DIR,
    test_dir: Path = DEFAULT_TEST_DIR,
) -> dict[str, Any]:
    """Genera dev/dataset.jsonl, test/dataset.jsonl y test/sha256.txt."""
    dev_cases = generate_split_cases(seed=SEED_DEV, split="dev", count=30)
    test_cases = generate_split_cases(seed=SEED_TEST, split="test", count=50)

    dev_path = dev_dir / "dataset.jsonl"
    test_path = test_dir / "dataset.jsonl"
    sha_path = test_dir / "sha256.txt"

    write_jsonl_cases(dev_path, dev_cases)
    write_jsonl_cases(test_path, test_cases)

    test_sha256 = compute_file_sha256(test_path)
    sha_path.write_text(f"{test_sha256}\n", encoding="utf-8", newline="\n")

    return {
        "dev_count": len(dev_cases),
        "test_count": len(test_cases),
        "dev_hard_cases": sum(1 for c in dev_cases if c["is_hard_case"]),
        "test_hard_cases": sum(1 for c in test_cases if c["is_hard_case"]),
        "test_sha256": test_sha256,
    }


def main() -> None:
    summary = generate_all_splits()
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
