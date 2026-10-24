"""Tests E2E del esqueleto inicial y endpoints de Tapaito (incluyendo CE1 con SDK openai)."""

from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient
from openai import AsyncOpenAI

from tapaito.api.app import create_app


def test_healthz_and_models() -> None:
    app = create_app()
    client = TestClient(app)

    r_health = client.get("/healthz")
    assert r_health.status_code == 200
    assert r_health.json()["status"] == "ok"

    r_models = client.get("/v1/models")
    assert r_models.status_code == 200
    data = r_models.json()
    assert data["object"] == "list"
    assert any(m["id"] == "tapaito-mock" for m in data["data"])


def test_preview_and_session_delete_e2e() -> None:
    app = create_app()
    client = TestClient(app)

    sample_text = (
        "Paciente con CC 1.032.456.789 afiliado a EPS con NIT 800.197.268-4. "
        "Contacto celular +57 310 456 7890 y correo paciente.demo@clinica.co. "
        "Reside en Calle 45 # 12-34. Se ordena CUPS 890201 y Acetaminofen 500 mg."
    )
    resp = client.post(
        "/v1/tapaito/preview",
        json={"text": sample_text, "mode": "rapido", "session_id": "sess-test-1"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["mode"] == "rapido"
    assert body["session_id"] == "sess-test-1"
    masked = body["masked"]
    # Los datos originales NO deben estar en el texto enmascarado
    assert "1.032.456.789" not in masked
    assert "800.197.268-4" not in masked
    assert "310 456 7890" not in masked
    assert "paciente.demo@clinica.co" not in masked
    assert "Calle 45 # 12-34" not in masked
    # Los codigos clinicos NO deben ser enmascarados (R8)
    assert "890201" in masked
    assert "500 mg" in masked
    # Verificar invariante de offsets sobre original
    for ent in body["entities"]:
        s, e = ent["start"], ent["end"]
        assert 0 <= s < e <= len(sample_text)
        assert ent["token"] in masked

    # Borrar sesion explicitamente (RF5)
    del_resp = client.delete("/v1/tapaito/session/sess-test-1")
    assert del_resp.status_code == 200
    assert del_resp.json()["deleted"] is True


@pytest.mark.anyio
async def test_openai_sdk_client_works_changing_only_base_url_ce1() -> None:
    """CE1: Un cliente OpenAI existente funciona cambiando solo base_url."""
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as async_http:
        oa_client = AsyncOpenAI(
            base_url="http://testserver/v1",
            api_key="mock-key",
            http_client=async_http,
        )

        clinical_note = (
            "Historia clinica: Paciente con CC 79.456.123 y celular 314 567 8901, "
            "remitido por entidad NIT 899.999.068-1 con radicado 11001310300120240012300. "
            "Edad 54 años, diagnostico J189, recibe Losartan 50 mg."
        )

        completion = await oa_client.chat.completions.create(
            model="tapaito-mock",
            messages=[
                {"role": "system", "content": "Resume la nota clinica."},
                {"role": "user", "content": clinical_note},
            ],
            extra_headers={
                "X-Tapaito-Mode": "rapido",
                "X-Tapaito-Session": "sess-ce1",
            },
        )

    content = completion.choices[0].message.content or ""
    # El cliente final recibe los datos reales reinsertados
    assert "79.456.123" in content
    assert "314 567 8901" in content
    assert "899.999.068-1" in content
    assert "11001310300120240012300" in content

    # Y los metadatos de tapaito muestran que el upstream solo vio tokens
    dump = completion.model_dump()
    assert "tapaito" in dump
    tapaito_meta = dump["tapaito"]
    assert "79.456.123" not in tapaito_meta["masked_prompt"]
    assert "⟦CEDULA_1⟧" in tapaito_meta["masked_prompt"]
    assert "⟦CELULAR_1⟧" in tapaito_meta["masked_prompt"]
    assert "⟦NIT_1⟧" in tapaito_meta["masked_prompt"]
    assert "⟦RADICADO_1⟧" in tapaito_meta["masked_prompt"]
    assert tapaito_meta["reinsertion_report"]["tasa_restauracion"] >= 0.95

