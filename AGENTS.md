# AGENTS.md — Guía Operativa para Subagentes de Tapaito

> **Fuente de verdad:** [`TAPAITO.md`](./TAPAITO.md) y [`PLAN.md`](./PLAN.md).

## Reglas Innegociables
1. **Solo datos sintéticos:** Prohibido usar datos personales reales en código, tests o ejemplos.
2. **Lenguaje legal prudente:** Prohibido escribir `"cumple la Ley 1581"`, `"cumple la ley"`, `"100 % seguro"`, `"100% seguro"`, `"anonimiza"`. Usa `"reduce la exposición de datos personales"`.
3. **Privacidad del sistema (CE6):** El audit log (`audit.jsonl`) y las trazas de error nunca contienen valores originales ni cuerpos de peticiones.
4. **Fallar cerrado (CE5):** En modo `estricto`, cualquier error/timeout del verificador Qwen3 o residuo persistente tras 1 reenmascarado bloquea con HTTP 422 (`TAPAITO_RESIDUO` o `TAPAITO_VERIFIER_ERROR`).
5. **Aislamiento de UI (Fase 5):** No crear ni modificar `src/tapaito/ui/index.html`, `src/tapaito/ui/styles.css`, `src/tapaito/ui/app.js` ni `docs/DEMO.md` (reservados para el Agente Externo de UI y sincronizados mediante `git pull` en Fase 5).
6. **Codificación UTF-8:** En Windows, toda lectura/escritura de archivos debe especificar `encoding="utf-8"`.
