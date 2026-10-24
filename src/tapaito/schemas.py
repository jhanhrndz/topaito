"""Esquemas y tipos compartidos de Tapaito."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Mode(StrEnum):
    RAPIDO = "rapido"
    ESTRICTO = "estricto"


class EntityType(StrEnum):
    CEDULA = "CEDULA"
    NIT = "NIT"
    CELULAR = "CELULAR"
    CORREO = "CORREO"
    RADICADO = "RADICADO"
    CUENTA = "CUENTA"
    FECHA_NAC = "FECHA_NAC"
    PERSONA = "PERSONA"
    DIRECCION = "DIRECCION"
    UBICACION = "UBICACION"
    ORGANIZACION = "ORGANIZACION"
    RESIDUO = "RESIDUO"


STRUCTURED_ENTITY_TYPES: frozenset[EntityType] = frozenset(
    {
        EntityType.CEDULA,
        EntityType.NIT,
        EntityType.CELULAR,
        EntityType.CORREO,
        EntityType.RADICADO,
    }
)


class Span(BaseModel):
    """Span interno detectado en un texto. `text` nunca se escribe en audit logs."""

    model_config = ConfigDict(frozen=True)

    start: int
    end: int
    entity_type: EntityType
    text: str = Field(repr=False, exclude=True)
    source: str = "regex"  # "regex" | "ner" | "llm" | "session"
    confidence: float = 1.0


class PublicEntitySpan(BaseModel):
    """Representacion publica de una entidad enmascarada para /preview y campo tapaito."""

    start: int
    end: int
    entity_type: EntityType
    token: str
    source: str


class AuditSpanRecord(BaseModel):
    """Representacion estricta para audit.jsonl (jamas incluye valor ni texto original)."""

    start: int
    end: int
    entity_type: EntityType
    source: str


class ReinsertionReport(BaseModel):
    """Informe de reinsercion de tokens por respuesta."""

    restaurados: list[str] = Field(default_factory=list)
    faltantes: list[str] = Field(default_factory=list)
    desconocidos: list[str] = Field(default_factory=list)
    ambiguos: list[str] = Field(default_factory=list)
    tasa_restauracion: float = 1.0


class ResidualItem(BaseModel):
    """Hallazgo residual reportado por el verificador local Qwen3 4B."""

    texto: str
    tipo: str
    confianza: float = 0.8


class VerifierOutput(BaseModel):
    """Esquema JSON fijo de salida de la Capa 3 (Qwen3 4B)."""

    residuos: list[ResidualItem] = Field(default_factory=list)
    advertencias: list[str] = Field(default_factory=list)


class PreviewRequest(BaseModel):
    text: str
    mode: Mode = Mode.RAPIDO
    session_id: str = "default"


class PreviewResponse(BaseModel):
    original: str
    masked: str
    mode: Mode
    session_id: str
    entities: list[PublicEntitySpan] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    latency_ms: dict[str, float] = Field(default_factory=dict)


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="allow")

    role: str
    content: str | list[dict[str, Any]] | None = ""


class ChatCompletionRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    model: str = "tapaito-mock"
    messages: list[ChatMessage]
    temperature: float | None = 0.0
    max_tokens: int | None = None
    stream: bool = False
