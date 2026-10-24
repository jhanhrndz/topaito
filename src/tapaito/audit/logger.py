"""Audit log local en formato JSONL garantizando cero valores originales (RF9, CE6, R9)."""

from __future__ import annotations

import json
import uuid
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tapaito.config import settings
from tapaito.schemas import AuditSpanRecord, Mode, PublicEntitySpan


class AuditLogger:
    """Registra eventos de enmascarado/bloqueo en audit.jsonl sin guardar jamas textos ni valores."""

    def __init__(self, log_path: Path | None = None) -> None:
        self._custom_path = log_path

    @property
    def log_path(self) -> Path:
        return self._custom_path if self._custom_path is not None else settings.audit_log_path

    def log_event(
        self,
        *,
        mode: Mode,
        session_id: str,
        entities: list[PublicEntitySpan],
        result: str,
        latency_ms: dict[str, float],
        request_id: str | None = None,
        error_code: str | None = None,
    ) -> dict[str, Any]:
        """Construye y escribe una entrada JSONL estrictamente libre de valores originales."""
        req_id = request_id or f"req_{uuid.uuid4().hex[:10]}"
        counts = Counter(ent.entity_type.value for ent in entities)
        safe_spans = [
            AuditSpanRecord(
                start=ent.start,
                end=ent.end,
                entity_type=ent.entity_type,
                source=ent.source,
            ).model_dump(mode="json")
            for ent in entities
        ]

        entry: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "request_id": req_id,
            "session_id": session_id,
            "mode": mode.value,
            "result": result,  # "enviado" | "bloqueado" | "preview"
            "counts_by_type": dict(counts),
            "spans": safe_spans,
            "latency_ms": {k: round(float(v), 2) for k, v in latency_ms.items()},
        }
        if error_code:
            entry["error_code"] = error_code

        path = self.log_path
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")

        return entry

    def read_recent(self, limit: int = 20) -> list[dict[str, Any]]:
        """Lee las ultimas `limit` entradas del audit log en orden cronologico inverso."""
        path = self.log_path
        if not path.exists():
            return []
        lines = path.read_text(encoding="utf-8").splitlines()
        entries: list[dict[str, Any]] = []
        for line in reversed(lines):
            line_str = line.strip()
            if not line_str:
                continue
            try:
                entries.append(json.loads(line_str))
            except json.JSONDecodeError:
                continue
            if len(entries) >= max(1, limit):
                break
        return entries


audit_logger = AuditLogger()
