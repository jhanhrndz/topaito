# Registro de Decisiones Arquitectónicas y Técnicas (`DECISIONS.md`)

> Toda decisión ante una ambigüedad de `TAPAITO.md` o hallazgo empírico se registra aquí con su contexto, decisión y alternativa descartada.

---

## D1 — Desactivación de "Thinking" y Configuración de Latencia de Qwen3 4B en Ollama (Spike F0.T1)

- **Fecha / Fase:** 2026-10-24 — Fase 0 (`F0.T1`)
- **Contexto (RNF2, RNF3, R3):** Se requiere verificar en la versión instalada de Ollama qué mecanismo desactiva el razonamiento largo (`thinking`) en `qwen3:4b` y medir la latencia real en la máquina con GPU de 4 GB VRAM.
- **Hallazgos empíricos verificados:**
  - **Entorno:** Windows, Python `3.13.14`, Ollama `0.35.1`, modelo `qwen3:4b` (ID `359d7dd4bcda`, 3.1 GB en memoria con `num_ctx=1536`, split `25% CPU / 75% GPU`).
  - **Causa raíz de latencia inicial:** Con el contexto por defecto de Qwen3, el KV cache excede los 4 GB de VRAM provocando offload pesado a CPU y carga en frío > 30 s. Al fijar `"options": {"num_ctx": 1536, "temperature": 0, "num_predict": 200}`, el modelo cabe en un 75 % en GPU.
  - **Desactivación de thinking verificada:** En Ollama `0.35.1`, pasar `"think": false` en el nivel raíz del JSON de `/api/chat` junto con `/no_think` al inicio del prompt de sistema produce `thinking_field_len = 0` (cero tokens de razonamiento oculto) y respeta estrictamente el `format` JSON Schema.
  - **Métricas reales del Spike (`scripts/spike_qwen.py`):**
    - Primera corrida con modelo cargado: `7127.98 ms` (~7.1 s)
    - 5 corridas cálidas consecutivas: `[7245.37, 7193.36, 8209.81, 6894.33, 6621.84] ms`
    - **Latencia p50:** `7193.36 ms` (~7.19 s)
    - **Latencia p95:** `8209.81 ms` (~8.21 s) — holgadamente dentro del presupuesto de timeout de `20.0 s` (RNF2).
    - **Calidad de salida en el spike:** Detectó ambos residuos (`"Maria Fernanda Gomez"`, `"311 456 7890"`), reportó el cuasi-identificador (`"unico cirujano pediatra del hospital de Leticia"`) y **no** marcó como residuo los medicamentos (`Losartan 50 mg`, `Acetaminofen 500 mg`).
- **Decisión:**
  1. Usar simultáneamente `"think": False` en el payload de Ollama y `/no_think` en el system prompt.
  2. Fijar `num_ctx: 1536`, `num_predict: 200`, `temperature: 0`, `keep_alive: "15m"` y `MAX_VERIFY_CHARS = 1800` (troceando si el texto es mayor).
- **Alternativa descartada:** Dejar `num_ctx` por defecto (4096/32768), lo cual desborda los 4 GB de VRAM y multiplica por >4x la latencia.

---

## D2 — Aislamiento de Archivos de UI para Desarrollo Paralelo con Agente Externo (Fase 5)

- **Fecha / Fase:** 2026-10-24 — Fase 0
- **Contexto:** Un segundo agente de IA construirá en paralelo la interfaz visual y el guion de demo (`src/tapaito/ui/index.html`, `src/tapaito/ui/styles.css`, `src/tapaito/ui/app.js`, `docs/DEMO.md`), que se integrarán mediante `git pull` al pasar de la Fase 4 a la Fase 5.
- **Decisión:** Congelar el contrato JSON de `/v1/tapaito/preview`, `/v1/chat/completions`, `/v1/tapaito/audit` y `DELETE /v1/tapaito/session/{id}` en `PLAN.md` y `docs/UI_AGENT_PROMPT.md`. En `src/tapaito/api/app.py`, servir `src/tapaito/ui/index.html` dinámicamente si existe en disco y un fallback en memoria mientras llega el `git pull` de Fase 5, evitando cualquier conflicto de merge.
- **Alternativa descartada:** Crear archivos placeholder en `src/tapaito/ui/` durante Fase 0, lo que produciría conflictos de `git pull` cuando el agente externo suba sus archivos.

---

## D3 — Trade-off Precisión/Recall en Cédula Colombiana + Barrido de Sesión (Fase 1)

- **Fecha / Fase:** 2026-10-24 — Fase 1 (`F1.T1` y `F1.T2`)
- **Contexto (§7 Notas Técnicas, R8, R16):** La cédula de ciudadanía colombiana (6 a 10 dígitos) no tiene dígito de verificación público. En textos clínicos abundan números de 6 a 10 dígitos que **no** son documentos de identidad (códigos CUPS de 6 dígitos como `890201`, registros INVIMA, números de lote, órdenes de laboratorio o dosis altas en `UI`/`ml`).
- **Decisión:**
  1. En `validators.py::has_cedula_context`, evaluar primero una ventana de **contexto negativo inmediato** (`CUPS`, `CIE-10`, `lote`, `INVIMA`, `orden #`, `cama`, `habitación`, y unidades pospuestas `mg`, `ml`, `mcg`, `UI`, `mmHg`, etc.).
  2. Exigir **contexto positivo** (`cédula`, `CC`, `C.C.`, `documento`, `identificación`, `portador`, `DNI`, `T.I.`) en una ventana de 45 caracteres previos / 25 posteriores (cortada en signos de puntuación `;`/`.` para no contaminar oraciones contiguas), **o** formato explícito con puntos de miles colombianos (`1.032.456.789` o `79.456.123`).
  3. Combinar lo anterior con el **Barrido de Sesión (*Second-Pass Session Sweep*)** en `masker.py`: una vez que la cédula se detecta con contexto al inicio del documento o sesión, cualquier aparición posterior del mismo número limpio (incluso sin `"CC"` ni puntos) se enmascara automáticamente con el mismo token `⟦CEDULA_1⟧`.
- **Alternativa descartada:** Enmascarar cualquier número de 6–10 dígitos sin contexto, lo cual destruye la utilidad clínica al ocultar códigos CUPS, lotes y valores de laboratorio.

