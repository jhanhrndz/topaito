"""Configuracion centralizada de Tapaito."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class Settings:
    host: str = "127.0.0.1"
    port: int = 8080
    upstream_base_url: str = "mock"
    upstream_api_key: str = "mock-key"
    upstream_model: str = "tapaito-mock"
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen3:4b"
    verifier_timeout_s: float = 20.0
    max_verify_chars: int = 1800
    session_ttl_seconds: int = 1800
    audit_log_path: Path = Path("audit.jsonl")

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            host=os.getenv("TAPAITO_HOST", "127.0.0.1"),
            port=int(os.getenv("TAPAITO_PORT", "8080")),
            upstream_base_url=os.getenv("UPSTREAM_BASE_URL", "mock"),
            upstream_api_key=os.getenv("UPSTREAM_API_KEY", "mock-key"),
            upstream_model=os.getenv("UPSTREAM_MODEL", "tapaito-mock"),
            ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
            ollama_model=os.getenv("OLLAMA_MODEL", "qwen3:4b"),
            verifier_timeout_s=float(os.getenv("TAPAITO_VERIFIER_TIMEOUT_S", "20.0")),
            max_verify_chars=int(os.getenv("TAPAITO_MAX_VERIFY_CHARS", "1800")),
            session_ttl_seconds=int(os.getenv("TAPAITO_SESSION_TTL_S", "1800")),
            audit_log_path=Path(os.getenv("TAPAITO_AUDIT_LOG_PATH", "audit.jsonl")),
        )


settings = Settings.from_env()
