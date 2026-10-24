"""Suite de auditoria y pruebas de seguridad y privacidad (CE5, CE6, R5, R9, RF8, RF9)."""

from __future__ import annotations

import json
import logging
import sys
import types
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

import tapaito.api.routes_openai as routes_openai_mod
import tapaito.policy.pipeline as pipeline_mod
from tapaito.api.app import app
from tapaito.config import Settings, settings
from tapaito.mask.session_store import SessionStore
from tapaito.schemas import ResidualItem, VerifierOutput


def _ensure_verifier_module(monkeypatch: pytest.MonkeyPatch) -> tuple[Any, type[Exception]]:
    """Obtiene el modulo real `tapaito.detect.llm_verifier` o inyecta un stub compatible si aun no existe."""
    try:
        import tapaito.detect.llm_verifier as real_mod

        return real_mod, real_mod.VerifierFailedError
    except ImportError:

        class _StubVerifierFailedError(RuntimeError):
            """Excepcion stub para fallos del verificador."""

        stub_mod = types.ModuleType("tapaito.detect.llm_verifier")
        stub_mod.VerifierFailedError = _StubVerifierFailedError  # type: ignore[attr-defined]

        def _default_verify(masked_text: str, timeout_s: float = 20.0) -> VerifierOutput:
            return VerifierOutput(residuos=[], advertencias=[])

        stub_mod.verify_masked_text = _default_verify  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "tapaito.detect.llm_verifier", stub_mod)
        return stub_mod, _StubVerifierFailedError


# =====================================================================
# 1. CE5 — Politica "Fallar Cerrado" en Modo Estricto (RF8, §9)
# =====================================================================


def test_strict_mode_blocks_on_verifier_error_or_timeout_ce5(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CE5: Error o timeout del verificador en modo estricto bloquea con HTTP 422 y 0 llamadas al upstream."""
    audit_file = tmp_path / "audit_ce5_err.jsonl"
    monkeypatch.setattr(settings, "audit_log_path", audit_file)
    monkeypatch.setattr(pipeline_mod, "session_store", SessionStore())

    verifier_mod, verifier_err_cls = _ensure_verifier_module(monkeypatch)

    def _failing_verifier(masked_text: str, timeout_s: float = 20.0) -> VerifierOutput:
        raise verifier_err_cls("Timeout simulado en Qwen3 tras 20s o JSON invalido en 2 intentos")

    monkeypatch.setattr(verifier_mod, "verify_masked_text", _failing_verifier)

    upstream_calls: list[dict[str, Any]] = []

    async def _spy_upstream(**kwargs: Any) -> dict[str, Any]:
        upstream_calls.append(kwargs)
        return {}

    monkeypatch.setattr(routes_openai_mod, "call_upstream_chat", _spy_upstream)

    client = TestClient(app)

    # 1) Probar en POST /v1/chat/completions con header X-Tapaito-Mode: estricto
    resp_chat = client.post(
        "/v1/chat/completions",
        headers={"X-Tapaito-Mode": "estricto", "X-Tapaito-Session": "sec-ce5-1"},
        json={
            "model": "tapaito-mock",
            "messages": [
                {
                    "role": "user",
                    "content": "Paciente con CC 1.020.304.050 solicita historia clinica.",
                }
            ],
        },
    )
    assert resp_chat.status_code == 422
    chat_err = resp_chat.json()["error"]
    assert chat_err["code"] == "TAPAITO_VERIFIER_ERROR"
    assert chat_err["mode"] == "estricto"
    assert len(upstream_calls) == 0

    # 2) Probar en POST /v1/tapaito/preview con mode="estricto"
    resp_prev = client.post(
        "/v1/tapaito/preview",
        json={
            "text": "Paciente con CC 1.020.304.050 solicita historia clinica.",
            "mode": "estricto",
            "session_id": "sec-ce5-2",
        },
    )
    assert resp_prev.status_code == 422
    prev_err = resp_prev.json()["error"]
    assert prev_err["code"] == "TAPAITO_VERIFIER_ERROR"
    assert prev_err["mode"] == "estricto"
    assert len(upstream_calls) == 0

    # 3) Verificar que el audit log registro ambos bloqueos sin valores originales
    raw_audit = audit_file.read_text(encoding="utf-8")
    assert "1.020.304.050" not in raw_audit
    assert "1020304050" not in raw_audit
    lines = [json.loads(line) for line in raw_audit.splitlines() if line.strip()]
    assert len(lines) == 2
    for entry in lines:
        assert entry["result"] == "bloqueado"
        assert entry["error_code"] == "TAPAITO_VERIFIER_ERROR"
        assert entry["mode"] == "estricto"


def test_strict_mode_reenmasks_once_and_succeeds_if_clean(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """RF8 / CE5: Si el 1er pase de Qwen reporta un residuo y tras 1 reenmascarado queda limpio, se envia."""
    audit_file = tmp_path / "audit_ce5_reenmask.jsonl"
    monkeypatch.setattr(settings, "audit_log_path", audit_file)
    monkeypatch.setattr(pipeline_mod, "session_store", SessionStore())
    # Simular que Capa 2 (NER) omitio el nombre para ejercitar el reenmascarado de Capa 3
    monkeypatch.setattr(pipeline_mod, "_run_ner_if_available", lambda _text: [])

    verifier_mod, _ = _ensure_verifier_module(monkeypatch)
    verifier_inputs: list[str] = []

    def _two_pass_verifier(masked_text: str, timeout_s: float = 20.0) -> VerifierOutput:
        verifier_inputs.append(masked_text)
        if len(verifier_inputs) == 1:
            return VerifierOutput(
                residuos=[
                    ResidualItem(
                        texto="Maria Fernanda Gomez",
                        tipo="persona",
                        confianza=0.95,
                    )
                ],
                advertencias=[],
            )
        return VerifierOutput(
            residuos=[],
            advertencias=["Cargo unico en municipio"],
        )

    monkeypatch.setattr(verifier_mod, "verify_masked_text", _two_pass_verifier)

    upstream_payloads: list[list[dict[str, Any]]] = []

    async def _spy_upstream(
        messages: list[dict[str, Any]],
        model: str | None = None,
        temperature: float | None = 0.0,
        max_tokens: int | None = None,
        hostile_mode: str | None = None,
    ) -> dict[str, Any]:
        upstream_payloads.append(messages)
        return {
            "id": "chatcmpl-test",
            "object": "chat.completion",
            "created": 1234567890,
            "model": model or "tapaito-mock",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "Caso de ⟦PERSONA_1⟧ revisado correctamente.",
                    },
                    "finish_reason": "stop",
                }
            ],
        }

    monkeypatch.setattr(routes_openai_mod, "call_upstream_chat", _spy_upstream)

    client = TestClient(app)
    resp = client.post(
        "/v1/chat/completions",
        headers={"X-Tapaito-Mode": "estricto", "X-Tapaito-Session": "sec-reenmask"},
        json={
            "model": "tapaito-mock",
            "messages": [
                {
                    "role": "user",
                    "content": "Solicito revisar historia de Maria Fernanda Gomez en el hospital.",
                }
            ],
        },
    )

    assert resp.status_code == 200
    assert len(verifier_inputs) == 2
    assert "Maria Fernanda Gomez" in verifier_inputs[0]
    assert "Maria Fernanda Gomez" not in verifier_inputs[1]
    assert "⟦PERSONA_1⟧" in verifier_inputs[1]

    # El upstream recibio exactamente 1 llamada y con el nombre enmascarado
    assert len(upstream_payloads) == 1
    sent_text = json.dumps(upstream_payloads[0], ensure_ascii=False)
    assert "Maria Fernanda Gomez" not in sent_text
    assert "⟦PERSONA_1⟧" in sent_text

    body = resp.json()
    assert "Maria Fernanda Gomez" in body["choices"][0]["message"]["content"]
    assert "Cargo unico en municipio" in body["tapaito"]["warnings"]
    assert "⟦PERSONA_1⟧" in body["tapaito"]["masked_prompt"]


def test_strict_mode_blocks_when_residual_persists_after_remasking_ce5(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CE5: Si tras 1 ciclo de reenmascarado el verificador sigue reportando un residuo presente, bloquea con 422."""
    audit_file = tmp_path / "audit_ce5_persist.jsonl"
    monkeypatch.setattr(settings, "audit_log_path", audit_file)
    monkeypatch.setattr(pipeline_mod, "session_store", SessionStore())
    monkeypatch.setattr(pipeline_mod, "_run_ner_if_available", lambda _text: [])

    verifier_mod, _ = _ensure_verifier_module(monkeypatch)
    call_count = 0

    def _persistent_residual_verifier(masked_text: str, timeout_s: float = 20.0) -> VerifierOutput:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return VerifierOutput(
                residuos=[ResidualItem(texto="Maria Fernanda Gomez", tipo="persona", confianza=0.95)],
                advertencias=["Posible identificacion indirecta"],
            )
        # Segunda llamada: reporta otro residuo que aun persiste en el texto enmascarado
        return VerifierOutput(
            residuos=[ResidualItem(texto="Carlos Alberto Ruiz", tipo="persona", confianza=0.90)],
            advertencias=["Persiste segundo nombre propio en texto"],
        )

    monkeypatch.setattr(verifier_mod, "verify_masked_text", _persistent_residual_verifier)

    upstream_calls: list[Any] = []

    async def _spy_upstream(**kwargs: Any) -> dict[str, Any]:
        upstream_calls.append(kwargs)
        return {}

    monkeypatch.setattr(routes_openai_mod, "call_upstream_chat", _spy_upstream)

    client = TestClient(app)
    resp = client.post(
        "/v1/chat/completions",
        headers={"X-Tapaito-Mode": "estricto", "X-Tapaito-Session": "sec-persist"},
        json={
            "model": "tapaito-mock",
            "messages": [
                {
                    "role": "user",
                    "content": "Paciente Maria Fernanda Gomez fue atendida por Carlos Alberto Ruiz.",
                }
            ],
        },
    )

    assert resp.status_code == 422
    assert call_count == 2
    assert len(upstream_calls) == 0
    err = resp.json()["error"]
    assert err["code"] == "TAPAITO_RESIDUO"
    assert err["mode"] == "estricto"
    assert "Posible identificacion indirecta" in err["warnings"]
    assert "Persiste segundo nombre propio en texto" in err["warnings"]

    entries = [json.loads(line) for line in audit_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(entries) == 1
    assert entries[0]["result"] == "bloqueado"
    assert entries[0]["error_code"] == "TAPAITO_RESIDUO"


# =====================================================================
# 2. CE6 — Cero Valores Originales en Audit Log y Trazas (RF9, R9, §9)
# =====================================================================


def test_audit_log_never_contains_original_values_ce6(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CE6: Ni audit.jsonl ni GET /v1/tapaito/audit contienen jamas valores canarios originales."""
    audit_file = tmp_path / "audit.jsonl"
    monkeypatch.setattr(settings, "audit_log_path", audit_file)
    monkeypatch.setattr(pipeline_mod, "session_store", SessionStore())

    verifier_mod, verifier_err_cls = _ensure_verifier_module(monkeypatch)

    def _fail_strict(masked_text: str, timeout_s: float = 20.0) -> VerifierOutput:
        raise verifier_err_cls("Fallo simulado del verificador")

    monkeypatch.setattr(verifier_mod, "verify_masked_text", _fail_strict)

    canary_prompt = (
        "El ciudadano Crisostomo Nepomuceno Aristizabal identificado con CC 1.098.765.432, "
        "representante de la clinica con NIT 800.197.268-4, celular +57 314 888 9900, "
        "correo crisostomo.secreto@clinicaficticia.co y direccion Calle 123 # 45-67 "
        "presento derecho de peticion."
    )
    forbidden_canaries = [
        "Crisostomo Nepomuceno Aristizabal",
        "Crisostomo",
        "Nepomuceno",
        "Aristizabal",
        "1.098.765.432",
        "1098765432",
        "800.197.268-4",
        "800197268",
        "+57 314 888 9900",
        "314 888 9900",
        "3148889900",
        "crisostomo.secreto@clinicaficticia.co",
        "clinicaficticia.co",
        "Calle 123 # 45-67",
        "45-67",
    ]

    client = TestClient(app)

    # 1) Peticion exitosa en modo rapido
    resp_ok = client.post(
        "/v1/chat/completions",
        headers={"X-Tapaito-Mode": "rapido", "X-Tapaito-Session": "sess-ce6-ok"},
        json={
            "model": "tapaito-mock",
            "messages": [{"role": "user", "content": canary_prompt}],
        },
    )
    assert resp_ok.status_code == 200

    # 2) Peticion bloqueada en modo estricto
    resp_blocked = client.post(
        "/v1/chat/completions",
        headers={"X-Tapaito-Mode": "estricto", "X-Tapaito-Session": "sess-ce6-block"},
        json={
            "model": "tapaito-mock",
            "messages": [{"role": "user", "content": canary_prompt}],
        },
    )
    assert resp_blocked.status_code == 422

    # Verificar archivo crudo audit.jsonl
    assert audit_file.exists()
    raw_content = audit_file.read_text(encoding="utf-8")
    for canary in forbidden_canaries:
        assert canary not in raw_content, f"Valor canario filtrado en audit.jsonl: {canary}"
        assert canary.lower() not in raw_content.lower(), f"Valor canario (lower) en audit.jsonl: {canary}"

    # Verificar endpoint GET /v1/tapaito/audit
    resp_audit = client.get("/v1/tapaito/audit?limit=20")
    assert resp_audit.status_code == 200
    audit_json_text = resp_audit.text
    for canary in forbidden_canaries:
        assert canary not in audit_json_text, f"Valor canario filtrado en GET /v1/tapaito/audit: {canary}"
        assert canary.lower() not in audit_json_text.lower()

    entries = resp_audit.json()["entries"]
    assert len(entries) == 2
    results = {e["result"] for e in entries}
    assert results == {"enviado", "bloqueado"}

    for entry in entries:
        assert "counts_by_type" in entry
        assert entry["counts_by_type"]["CEDULA"] >= 1
        assert entry["counts_by_type"]["NIT"] >= 1
        assert entry["counts_by_type"]["CELULAR"] >= 1
        assert entry["counts_by_type"]["CORREO"] >= 1
        assert "spans" in entry and len(entry["spans"]) >= 4
        for span in entry["spans"]:
            assert set(span.keys()) == {"start", "end", "entity_type", "source"}
        assert "latency_ms" in entry
        assert "total" in entry["latency_ms"]


def test_error_traces_and_validation_errors_do_not_echo_sensitive_payload_r9(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """R9 / CE6: Errores de validacion (422) y excepciones internas (500) no reflejan payloads ni valores canarios."""
    canary = "Crisostomo Nepomuceno Aristizabal CC 1098765432"
    client = TestClient(app, raise_server_exceptions=False)

    with caplog.at_level(logging.INFO):
        # 1) Error de validacion Pydantic (messages no es una lista sino un string con el canario)
        resp_val = client.post(
            "/v1/chat/completions",
            json={
                "model": "tapaito-mock",
                "messages": canary,
                "extra_secret": canary,
            },
        )
        assert resp_val.status_code == 422
        assert resp_val.json()["error"]["code"] == "TAPAITO_INVALID_REQUEST"
        assert "Crisostomo" not in resp_val.text
        assert "1098765432" not in resp_val.text

        # 2) Excepcion interna no controlada dentro de la ruta conteniendo el canario en el mensaje de error
        def _boom_pipeline(*args: Any, **kwargs: Any) -> Any:
            raise RuntimeError(f"Error inesperado procesando a {canary}")

        monkeypatch.setattr(routes_openai_mod, "process_text_pipeline", _boom_pipeline)

        resp_500 = client.post(
            "/v1/chat/completions",
            json={
                "model": "tapaito-mock",
                "messages": [{"role": "user", "content": canary}],
            },
        )
        assert resp_500.status_code == 500
        assert resp_500.json()["error"]["code"] == "TAPAITO_INTERNAL_ERROR"
        assert "Crisostomo" not in resp_500.text
        assert "1098765432" not in resp_500.text

    # Verificar que los logs de Python tampoco contienen el canario
    logged_text = "\n".join(record.getMessage() for record in caplog.records)
    assert "Crisostomo" not in logged_text
    assert "1098765432" not in logged_text


# =====================================================================
# 3. Privacidad de Memoria y Configuracion por Defecto (§9)
# =====================================================================


def test_default_host_is_localhost_and_session_only_in_memory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """§9 / R9: El host por defecto es 127.0.0.1 y SessionStore opera 100% en RAM sin crear archivos."""
    monkeypatch.delenv("TAPAITO_HOST", raising=False)
    fresh_settings = Settings.from_env()
    assert fresh_settings.host == "127.0.0.1"
    assert settings.host == "127.0.0.1"

    monkeypatch.chdir(tmp_path)
    store = SessionStore(ttl_seconds=1800)
    from tapaito.schemas import EntityType

    tok = store.get_or_create_token("sesion-ram", EntityType.PERSONA, "Crisostomo Aristizabal")
    assert tok == "⟦PERSONA_1⟧"
    assert store.get_token_to_value_map("sesion-ram") == {"⟦PERSONA_1⟧": "Crisostomo Aristizabal"}
    assert store.delete_session("sesion-ram") is True
    assert store.get_token_to_value_map("sesion-ram") == {}

    # Cero archivos creados en el directorio de trabajo por SessionStore
    assert list(tmp_path.iterdir()) == []


# =====================================================================
# 4. R5 — Lenguaje Legal Prudente en Todo el Repositorio
# =====================================================================


def test_no_forbidden_legal_phrases_in_docs_or_code_r5() -> None:
    """R5: Ningun archivo de codigo o documentacion de usuario contiene promesas legales prohibidas."""
    repo_root = Path(__file__).resolve().parent.parent

    # Construimos las frases mediante concatenacion para no escribirlas literalmente ni siquiera en el test
    forbidden_phrases = [
        "cumple " + "la ley 1581",
        "cumple " + "la ley",
        "100 " + "% seguro",
        "100" + "% seguro",
        "anoni" + "miza",
    ]

    candidate_paths: list[Path] = []
    for rel_file in ("README.md", "docs/LIMITS.md", "docs/COMPARISON.md", "docs/DEMO.md"):
        p = repo_root / rel_file
        if p.exists() and p.is_file():
            candidate_paths.append(p)

    src_dir = repo_root / "src"
    if src_dir.exists():
        for p in src_dir.rglob("*"):
            if p.is_file() and p.suffix in {".py", ".html", ".css", ".js", ".md"}:
                candidate_paths.append(p)

    violations: list[str] = []
    for file_path in candidate_paths:
        content = file_path.read_text(encoding="utf-8", errors="ignore").lower()
        for phrase in forbidden_phrases:
            if phrase in content:
                rel = file_path.relative_to(repo_root)
                violations.append(f"{rel}: contiene frase prohibida '{phrase}'")

    assert not violations, "Violaciones de lenguaje legal prudente (R5):\n" + "\n".join(violations)
