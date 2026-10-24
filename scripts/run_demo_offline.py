"""Script de respaldo offline para reproducir la demo completa de 90 segundos (CE8).

Ejecuta los 4 escenarios del guion de demo (§15 de TAPAITO.md) sin depender de internet:
1. Caso clinico con identificadores colombianos (CC, NIT con DV DIAN, celular, correo, direccion y codigos medicos CUPS/medicamentos POS) en Modo Rapido -> Preview y Chat Completion con reinsercion.
2. Caso con residuo sutil (nombre en minusculas sin etiqueta estandar) + cuasi-identificador en Modo Estricto -> Verificador local Qwen3 4B (o simulacion determinista si Ollama no responde) atrapa el residuo, lo reenmascara y emite advertencia.
3. Caso con respuesta hostil del LLM (corchetes y minusculas alteradas + token desconocido) -> Reinsercion tolerante e informe explicito.
4. Caso de bloqueo por politica "Fallar Cerrado" (HTTP 422 TAPAITO_RESIDUO) + verificacion del Audit Log libre de valores originales (CE6).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from tapaito.api.app import create_app
from tapaito.config import settings


def _print_banner(title: str) -> None:
    print("\n" + "=" * 78)
    print(f"  {title}")
    print("=" * 78)


def run_offline_demo() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    # Usar un audit log dedicado para la demo
    demo_audit_path = Path("bench/results/demo_audit.jsonl")
    if demo_audit_path.exists():
        demo_audit_path.unlink()
    settings.audit_log_path = demo_audit_path
    settings.upstream_base_url = "mock"

    app = create_app()
    client = TestClient(app)

    _print_banner("BLOQUE 1 y 2 (0-30s): Historia Clínica Sintética -> Vista Previa (/preview)")
    clinical_text = (
        "HISTORIA CLÍNICA DE URGENCIAS. Paciente Juan Carlos Restrepo Gómez identificado "
        "con CC 1.032.456.789, afiliado a EPS Sanitas (NIT 800.251.440-6). "
        "Teléfono celular +57 314 567 8901, correo jrestrepo.demo@pacientes.co, "
        "dirección Calle 45 # 12-34 Apto 301 en Bogotá. "
        "Diagnóstico CIE-10 J189, se ordena procedimiento CUPS 890201 y se formula "
        "Losartán 50 mg cada 12 horas y Acetaminofén 500 mg."
    )
    r_prev = client.post(
        "/v1/tapaito/preview",
        json={"text": clinical_text, "mode": "rapido", "session_id": "demo-90s"},
    )
    assert r_prev.status_code == 200
    prev_data = r_prev.json()
    print(f"[Original]:   {prev_data['original'][:110]}...")
    print(f"[Enmascarado]: {prev_data['masked']}")
    print(f"[Entidades detectadas ({len(prev_data['entities'])})]: " + ", ".join(
        f"{e['entity_type']}->{e['token']} ({e['source']})" for e in prev_data["entities"]
    ))
    print(f"[Latencia Capas 1-2]: {prev_data['latency_ms']['layer1_2']} ms")

    _print_banner("BLOQUE 3 (30-50s): Envío a la Nube (Mock) + Reinserción e Informe")
    r_chat = client.post(
        "/v1/chat/completions",
        headers={"X-Tapaito-Mode": "rapido", "X-Tapaito-Session": "demo-90s"},
        json={
            "model": "tapaito-mock",
            "messages": [
                {"role": "system", "content": "Resume la nota clínica."},
                {"role": "user", "content": clinical_text},
            ],
        },
    )
    assert r_chat.status_code == 200
    chat_data = r_chat.json()
    tapaito_meta = chat_data["tapaito"]
    print(f"[Lo que vio la nube (raw_upstream_response)]:\n{tapaito_meta['raw_upstream_response']}\n")
    print(f"[Respuesta final reinsertada para el médico]:\n{chat_data['choices'][0]['message']['content']}\n")
    print(f"[Informe de Reinserción]: {json.dumps(tapaito_meta['reinsertion_report'], ensure_ascii=False)}")

    _print_banner("BLOQUE 4A (50-70s): Reinserción Tolerante ante Mutación Hostil del LLM")
    r_hostile = client.post(
        "/v1/chat/completions",
        headers={
            "X-Tapaito-Mode": "rapido",
            "X-Tapaito-Session": "demo-90s",
            "X-Tapaito-Mock-Hostile": "case_and_brackets",
        },
        json={
            "model": "tapaito-mock",
            "messages": [{"role": "user", "content": clinical_text}],
        },
    )
    assert r_hostile.status_code == 200
    h_data = r_hostile.json()
    print(f"[Respuesta hostil del upstream]: {h_data['tapaito']['raw_upstream_response']}")
    print(f"[Respuesta restaurada por Tapaito]: {h_data['choices'][0]['message']['content']}")
    print(f"[Tasa de restauración]: {h_data['tapaito']['reinsertion_report']['tasa_restauracion'] * 100:.1f}%")

    _print_banner("BLOQUE 4B (50-70s): Modo Estricto — Verificador Local Qwen3 4B / Fallar Cerrado")
    strict_text = (
        "SOLICITUD DE TUTELA EN SALUD. Radicado 11001-31-03-001-2024-00123-00. "
        "Paciente con CC 79.456.123. En caso de urgencia avisar en recepción a "
        "luz marina betancur. El paciente ejerce como único juez promiscuo municipal de Puerto Carreño."
    )
    r_strict = client.post(
        "/v1/chat/completions",
        headers={"X-Tapaito-Mode": "estricto", "X-Tapaito-Session": "demo-strict"},
        json={
            "model": "tapaito-mock",
            "messages": [{"role": "user", "content": strict_text}],
        },
    )
    print(f"[Status Modo Estricto]: HTTP {r_strict.status_code}")
    print(f"[Respuesta Modo Estricto]: {json.dumps(r_strict.json(), ensure_ascii=False)[:420]}...")

    _print_banner("BLOQUE 5 y 6 (70-90s): Verificación del Audit Log Local Sin Valores Originales (CE6)")
    r_audit = client.get("/v1/tapaito/audit?limit=5")
    assert r_audit.status_code == 200
    entries = r_audit.json()["entries"]
    print(f"[Entradas registradas en {demo_audit_path}]: {len(entries)}")
    if entries:
        print(f"[Última entrada de auditoría]:\n{json.dumps(entries[0], indent=2, ensure_ascii=False)}")

    raw_audit = demo_audit_path.read_text(encoding="utf-8")
    for secret in ("1.032.456.789", "1032456789", "Juan Carlos Restrepo", "314 567 8901", "800.251.440-6"):
        assert secret not in raw_audit, f"Fuga detectada en audit log: {secret}"
    if demo_audit_path.exists():
        demo_audit_path.unlink()
    print("\n[OK] Verificado CE6: 0 valores originales en el archivo de auditoría.")
    print("[OK] Demo offline de 90s completada con éxito (CE8).")
    return 0


if __name__ == "__main__":
    sys.exit(run_offline_demo())
