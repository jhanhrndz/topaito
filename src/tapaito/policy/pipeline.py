"""Orquestador de deteccion, enmascarado, verificacion Qwen y politica fallar cerrado."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

from tapaito.config import settings
from tapaito.detect.merge import merge_spans
from tapaito.detect.regex_layer import detect_regex
from tapaito.mask.masker import mask_text
from tapaito.mask.session_store import SessionStore
from tapaito.schemas import EntityType, Mode, PublicEntitySpan, Span

# Instancia global en memoria para el proceso FastAPI
session_store = SessionStore(ttl_seconds=settings.session_ttl_seconds)


class PolicyBlockedError(Exception):
    """Excepcion lanzada cuando el modo estricto bloquea el envio (CE5 / RF8)."""

    def __init__(
        self,
        code: str,
        message: str,
        warnings: list[str] | None = None,
        entities: list[PublicEntitySpan] | None = None,
        latency_ms: dict[str, float] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.warnings = warnings or []
        self.entities = entities or []
        self.latency_ms = latency_ms or {}


@dataclass
class MaskPipelineResult:
    original_text: str
    masked_text: str
    mode: Mode
    session_id: str
    entities: list[PublicEntitySpan] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    latency_ms: dict[str, float] = field(default_factory=dict)


def _run_ner_if_available(text: str) -> list[Span]:
    try:
        from tapaito.detect.ner_layer import detect_ner

        return detect_ner(text)
    except ImportError:
        return []


def _map_residual_type(raw_tipo: str) -> EntityType:
    low = raw_tipo.strip().lower()
    if any(k in low for k in ("nombre", "persona", "paciente", "medico", "acompanante", "per")):
        return EntityType.PERSONA
    if any(k in low for k in ("cedula", "documento", "cc", "identificacion", "ti", "dni")):
        return EntityType.CEDULA
    if "nit" in low:
        return EntityType.NIT
    if any(k in low for k in ("tel", "cel", "movil")):
        return EntityType.CELULAR
    if any(k in low for k in ("correo", "email", "mail")):
        return EntityType.CORREO
    if "radicado" in low:
        return EntityType.RADICADO
    if any(k in low for k in ("dir", "calle", "carrera", "domicilio", "residencia")):
        return EntityType.DIRECCION
    if any(k in low for k in ("ubicacion", "ciudad", "municipio", "loc")):
        return EntityType.UBICACION
    if any(k in low for k in ("org", "eps", "ips", "clinica", "hospital", "empresa")):
        return EntityType.ORGANIZACION
    return EntityType.RESIDUO


def _find_residual_spans_in_original(
    original_text: str,
    existing_spans: list[Span],
    residuals: list[tuple[str, EntityType, float]],
) -> list[Span]:
    """Busca los textos residuales reportados por Qwen dentro del texto original."""
    extra_spans: list[Span] = []
    for res_text, etype, conf in residuals:
        cleaned = res_text.strip()
        if len(cleaned) < 3 or "⟦" in cleaned or "⟧" in cleaned:
            continue
        for match in re.finditer(re.escape(cleaned), original_text, flags=re.IGNORECASE):
            s, e = match.span()
            extra_spans.append(
                Span(
                    start=s,
                    end=e,
                    entity_type=etype,
                    text=original_text[s:e],
                    source="llm",
                    confidence=conf,
                )
            )
    return merge_spans(existing_spans + extra_spans)


def process_text_pipeline(
    text: str,
    mode: Mode = Mode.RAPIDO,
    session_id: str = "default",
    store: SessionStore | None = None,
    enable_ner: bool = True,
) -> MaskPipelineResult:
    """Ejecuta las capas de deteccion y enmascarado segun el modo (`rapido` o `estricto`)."""
    active_store = store or session_store
    t_start = time.perf_counter()

    # Capas 1 y 2
    t_l12 = time.perf_counter()
    regex_spans = detect_regex(text)
    ner_spans = _run_ner_if_available(text) if enable_ner else []
    base_spans = merge_spans(regex_spans + ner_spans)
    masked_text, public_spans = mask_text(
        text=text,
        spans=base_spans,
        session_id=session_id,
        store=active_store,
        enable_session_sweep=True,
    )
    layer1_2_ms = round((time.perf_counter() - t_l12) * 1000.0, 2)
    layer3_ms = 0.0
    warnings: list[str] = []

    if mode == Mode.ESTRICTO:
        t_l3 = time.perf_counter()
        try:
            from tapaito.detect.llm_verifier import VerifierFailedError, verify_masked_text
        except ImportError as exc:
            layer3_ms = round((time.perf_counter() - t_l3) * 1000.0, 2)
            total_ms = round((time.perf_counter() - t_start) * 1000.0, 2)
            raise PolicyBlockedError(
                code="TAPAITO_VERIFIER_ERROR",
                message="El verificador local Qwen3 no esta disponible en modo estricto.",
                entities=public_spans,
                latency_ms={"layer1_2": layer1_2_ms, "layer3": layer3_ms, "total": total_ms},
            ) from exc

        try:
            v_out_1 = verify_masked_text(masked_text, timeout_s=settings.verifier_timeout_s)
        except VerifierFailedError as exc:
            layer3_ms = round((time.perf_counter() - t_l3) * 1000.0, 2)
            total_ms = round((time.perf_counter() - t_start) * 1000.0, 2)
            raise PolicyBlockedError(
                code="TAPAITO_VERIFIER_ERROR",
                message=f"Peticion bloqueada en modo estricto (fallar cerrado): {exc}",
                entities=public_spans,
                latency_ms={"layer1_2": layer1_2_ms, "layer3": layer3_ms, "total": total_ms},
            ) from exc

        warnings = list(dict.fromkeys(v_out_1.advertencias))

        # Filtrar hallazgos que ya sean tokens o demasiado cortos
        valid_residuals = [
            (item.texto, _map_residual_type(item.tipo), item.confianza)
            for item in v_out_1.residuos
            if item.texto.strip()
            and "⟦" not in item.texto
            and "⟧" not in item.texto
            and item.texto.strip() in masked_text
        ]

        if valid_residuals:
            # 1 ciclo de reenmascarado + reverificacion (RF8)
            updated_spans = _find_residual_spans_in_original(text, base_spans, valid_residuals)
            masked_text_2, public_spans_2 = mask_text(
                text=text,
                spans=updated_spans,
                session_id=session_id,
                store=active_store,
                enable_session_sweep=True,
            )
            # Si algun residuo no pudo mapearse por offset en original, reemplazar directo en masked_text_2
            for res_str, etype, _conf in valid_residuals:
                if res_str in masked_text_2:
                    tok = active_store.get_or_create_token(session_id, etype, res_str)
                    masked_text_2 = masked_text_2.replace(res_str, tok)

            masked_text = masked_text_2
            public_spans = public_spans_2

            try:
                v_out_2 = verify_masked_text(masked_text, timeout_s=settings.verifier_timeout_s)
            except VerifierFailedError as exc:
                layer3_ms = round((time.perf_counter() - t_l3) * 1000.0, 2)
                total_ms = round((time.perf_counter() - t_start) * 1000.0, 2)
                raise PolicyBlockedError(
                    code="TAPAITO_VERIFIER_ERROR",
                    message=f"Peticion bloqueada en reverificacion (fallar cerrado): {exc}",
                    warnings=warnings,
                    entities=public_spans,
                    latency_ms={"layer1_2": layer1_2_ms, "layer3": layer3_ms, "total": total_ms},
                ) from exc

            for w in v_out_2.advertencias:
                if w not in warnings:
                    warnings.append(w)

            persisting = [
                item.texto
                for item in v_out_2.residuos
                if item.texto.strip()
                and "⟦" not in item.texto
                and "⟧" not in item.texto
                and item.texto.strip() in masked_text
            ]
            if persisting:
                layer3_ms = round((time.perf_counter() - t_l3) * 1000.0, 2)
                total_ms = round((time.perf_counter() - t_start) * 1000.0, 2)
                raise PolicyBlockedError(
                    code="TAPAITO_RESIDUO",
                    message="Peticion bloqueada en modo estricto: persisten posibles datos sensibles tras reenmascarado.",
                    warnings=warnings,
                    entities=public_spans,
                    latency_ms={"layer1_2": layer1_2_ms, "layer3": layer3_ms, "total": total_ms},
                )

        layer3_ms = round((time.perf_counter() - t_l3) * 1000.0, 2)

    total_ms = round((time.perf_counter() - t_start) * 1000.0, 2)
    return MaskPipelineResult(
        original_text=text,
        masked_text=masked_text,
        mode=mode,
        session_id=session_id,
        entities=public_spans,
        warnings=warnings,
        latency_ms={"layer1_2": layer1_2_ms, "layer3": layer3_ms, "total": total_ms},
    )
