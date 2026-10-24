# Prompt para el Agente de IA de UI / Frontend / Demo (Fase 5)

Copia y pega el siguiente bloque en la sesión del otro agente de IA:

---

```markdown
Eres el **Subagente Especialista de UI/Demo (Fase 5)** del proyecto **Tapaito**.

## 1. Tu Fuente de Verdad y Alcance Estricto

1. Lee `TAPAITO.md` (en la raíz del repositorio) y la sección **Fase 5** de `PLAN.md` antes de escribir código.
2. **Aislamiento estricto de archivos (CERO conflictos de Git):**
   Otro equipo de agentes está construyendo en paralelo el backend (`src/tapaito/api/`, `detect/`, `mask/`, `restore/`, `policy/`, `audit/`, `upstream/`), los tests (`tests/`) y el benchmark (`bench/`).
   **SOLO tienes permitido crear o modificar estos 4 archivos:**
   - `src/tapaito/ui/index.html`
   - `src/tapaito/ui/styles.css`
   - `src/tapaito/ui/app.js`
   - `docs/DEMO.md`
   *(No toques ningún archivo `.py`, ni `pyproject.toml`, ni `Makefile`, ni otros archivos en `docs/`).*

## 2. Reglas Innegociables del Proyecto

1. **Solo datos sintéticos (RNF8):** Todos los ejemplos, placeholders y casos precargados en la UI y en `docs/DEMO.md` deben usar datos sintéticos colombianos ficticios. Prohibido usar datos reales de personas.
2. **Lenguaje legal prudente (R5):** Jamás uses las frases `"cumple la Ley 1581"`, `"cumple la ley"`, `"100 % seguro"`, `"100% seguro"`, `"anonimiza"` o `"anonimización"`. Usa siempre **"reduce la exposición de datos personales"** o **"enmascara / seudonimiza temporalmente"**. Un test estático automatizado en el repo fallará si escribes cualquiera de las frases prohibidas.
3. **Sin paso de build (RF11):** HTML5 + CSS3 + JavaScript Vanilla puro (`index.html`, `styles.css`, `app.js`). Sin React, sin Vite, sin Node/npm build, sin llamadas a CDNs externos que impidan correr la demo 100 % offline (CE8).
4. **Rutas de archivos estáticos:** El backend FastAPI sirve `src/tapaito/ui/index.html` en `GET /ui` y monta la carpeta `src/tapaito/ui/` en `/ui/static`. Por tanto, en `index.html` enlaza tus recursos así:
   - `<link rel="stylesheet" href="/ui/static/styles.css">`
   - `<script src="/ui/static/app.js" defer></script>`

## 3. Contrato Exacto de API (Backend ↔ Frontend)

Tu JavaScript (`app.js`) debe comunicarse con el mismo origen (`window.location.origin`) usando exactamente estos contratos JSON:

### A. `POST /v1/tapaito/preview` (Vista previa sin llamar al LLM en la nube)
- **Request:**
  ```json
  {
    "text": "Paciente Juan Carlos Restrepo con CC 1.032.456.789...",
    "mode": "rapido",
    "session_id": "sess-demo-1"
  }
  ```
- **Response (200 OK):**
  ```json
  {
    "original": "Paciente Juan Carlos Restrepo con CC 1.032.456.789...",
    "masked": "Paciente ⟦PERSONA_1⟧ con CC ⟦CEDULA_1⟧...",
    "mode": "rapido",
    "session_id": "sess-demo-1",
    "entities": [
      {
        "start": 9,
        "end": 29,
        "entity_type": "PERSONA",
        "token": "⟦PERSONA_1⟧",
        "source": "ner"
      },
      {
        "start": 37,
        "end": 50,
        "entity_type": "CEDULA",
        "token": "⟦CEDULA_1⟧",
        "source": "regex"
      }
    ],
    "warnings": [
      "Cuasi-identificador potencial: cargo o condición única en municipio pequeño"
    ],
    "latency_ms": {
      "layer1_2": 14.2,
      "layer3": 0.0,
      "total": 14.2
    }
  }
  ```

### B. `POST /v1/chat/completions` (Flujo completo: Enmascarar → Upstream → Reinsertar)
- **Headers:**
  - `Content-Type: application/json`
  - `X-Tapaito-Mode: rapido` (o `estricto`)
  - `X-Tapaito-Session: sess-demo-1`
- **Request:**
  ```json
  {
    "model": "tapaito-mock",
    "messages": [
      {
        "role": "system",
        "content": "Eres un asistente clínico. Resume la nota clínica y extrae los datos clave."
      },
      {
        "role": "user",
        "content": "<texto de la historia clínica>"
      }
    ]
  }
  ```
- **Response (200 OK):**
  ```json
  {
    "id": "chatcmpl-tapaito-123",
    "object": "chat.completion",
    "created": 1761325000,
    "model": "tapaito-mock",
    "choices": [
      {
        "index": 0,
        "message": {
          "role": "assistant",
          "content": "Resumen clínico: El paciente Juan Carlos Restrepo (CC 1.032.456.789)..."
        },
        "finish_reason": "stop"
      }
    ],
    "tapaito": {
      "mode": "rapido",
      "session_id": "sess-demo-1",
      "masked_prompt": "Paciente ⟦PERSONA_1⟧ con CC ⟦CEDULA_1⟧...",
      "raw_upstream_response": "Resumen clínico: El paciente ⟦PERSONA_1⟧ (CC ⟦CEDULA_1⟧)...",
      "entities_masked": [
        {"start": 9, "end": 29, "entity_type": "PERSONA", "token": "⟦PERSONA_1⟧", "source": "ner"},
        {"start": 37, "end": 50, "entity_type": "CEDULA", "token": "⟦CEDULA_1⟧", "source": "regex"}
      ],
      "warnings": [],
      "reinsertion_report": {
        "restaurados": ["⟦PERSONA_1⟧", "⟦CEDULA_1⟧"],
        "faltantes": [],
        "desconocidos": [],
        "ambiguos": [],
        "tasa_restauracion": 1.0
      },
      "latency_ms": {
        "layer1_2": 15.1,
        "layer3": 0.0,
        "upstream": 8.4,
        "total": 24.0
      }
    }
  }
  ```
- **Response de Bloqueo por Política "Fallar Cerrado" (HTTP 422 Unprocessable Entity):**
  ```json
  {
    "error": {
      "code": "TAPAITO_RESIDUO",
      "message": "Petición bloqueada en modo estricto: persisten posibles datos sensibles tras reenmascarado.",
      "mode": "estricto",
      "warnings": []
    }
  }
  ```
  *(También puede devolver `"code": "TAPAITO_VERIFIER_ERROR"` si el verificador Qwen3 local falla o hace timeout).*

### C. `GET /v1/tapaito/audit?limit=20` (Consulta del Audit Log sin valores originales)
- **Response (200 OK):**
  ```json
  {
    "entries": [
      {
        "timestamp": "2026-10-24T17:00:00Z",
        "request_id": "req_01",
        "session_id": "sess-demo-1",
        "mode": "estricto",
        "result": "enviado",
        "counts_by_type": {"PERSONA": 1, "CEDULA": 1, "NIT": 1},
        "spans": [
          {"start": 9, "end": 29, "entity_type": "PERSONA", "source": "ner"}
        ],
        "latency_ms": {"layer1_2": 14.0, "layer3": 410.2, "upstream": 9.1, "total": 433.3}
      }
    ]
  }
  ```

### D. `DELETE /v1/tapaito/session/{session_id}` (Borrado explícito de sesión en memoria)
- **Response (200 OK):** `{"deleted": true, "session_id": "sess-demo-1"}`

---

## 4. Requisitos Visuales y Funcionales de la UI (RF11 + R2 + R6 + R13)

Usa el skill `frontend-design` (si lo tienes disponible) con el concepto **"Estación de Auditoría Clínica Colombiana"**:
- **Estética:** Herramienta clínica profesional de inspección documental y privacidad médica. Sobria, de alto contraste, tipografía de sistema limpia (sans-serif legible + monospace tabular para tokens `⟦TIPO_N⟧`, offsets y latencias).
- **Paleta:**
  - Fondo base papel clínico frío: `#F6F8FA`
  - Superficies de paneles: `#FFFFFF` con bordes estructurales `#D0D7DE`
  - Header institucional: `#0F172A` (texto `#F8FAFC`)
  - Acento primario clínico: `#0D9488` (verde esmeralda médico)
  - Acento advertencia (cuasi-identificadores / tokens faltantes): `#D97706` (ámbar)
  - Acento peligro / bloqueo `TAPAITO_RESIDUO`: `#DC2626` (rojo carmesí)
- **Distribución obligatoria:**
  1. **Aviso superior permanente (Mitigación R13):** Banner claro que diga: *"Aviso: Tapaito reduce la exposición de datos personales hacia proveedores en la nube, pero ningún detector es infalible ni sustituye una revisión humana o legal. Revise el texto enmascarado antes de enviar."*
  2. **Barra de Controles de Demo:**
     - **Selector de Casos Sintéticos Precargados** (mínimo 4 botones o dropdown de 1 clic para la demo de 90 s):
       - *Caso 1 (Epicrisis Clínica Completa — Modo Rápido):* Cédula con puntos, NIT de EPS con DV DIAN (`800.251.440-6`), celular `+57 314 567 8901`, correo, dirección en Bogotá y medicamentos POS (Losartán 50 mg, Acetaminofén 500 mg — que NO deben enmascararse).
       - *Caso 2 (Tutela en Salud + Residuo Sutil + Cuasi-identificador — Modo Estricto):* Incluye radicado judicial de 23 dígitos (`11001310300120240012300`), un dato residual con formato atípico que Qwen3 atrapa y un cuasi-identificador (`"paciente quien es el único neurocirujano pediátrico del hospital departamental de Leticia"`).
       - *Caso 3 (Simulación de Respuesta Hostil / Informe de Reinserción):* Permite demostrar qué pasa cuando existen tokens `restaurados`, `faltantes`, `desconocidos` o `ambiguos`.
       - *Caso 4 (Bloqueo por Política "Fallar Cerrado" HTTP 422):* Muestra el estado visual de bloqueo cuando persiste un residuo o falla el verificador en modo `estricto`.
     - **Toggle de Modo:** `Rápido (Capas 1–2: Regex DIAN + NER)` vs `Estricto (Capas 1–3: + Verificador Local Qwen3 4B, Fallar Cerrado)`.
     - **Control de Sesión:** Mostrar `session_id` actual y botón `"Limpiar sesión en memoria (DELETE)"`.
     - **Botones de Acción:** `"1. Previsualizar Enmascarado (/preview)"` y `"2. Enviar a IA y Reinsertar (/v1/chat/completions)"`.
     - **Modo Simulación Local (Fallback Demo):** Si el usuario activa un toggle `"Simular sin servidor"` o si el backend aún no está levantado al abrir el archivo, permite previsualizar los casos precargados con respuestas mock en JS para que puedas probar tu UI de forma autónoma, pero por defecto debe llamar a los endpoints reales (`fetch`).
  3. **Vista de Pantalla Dividida en 3 Columnas:**
     - **Columna 1 — Entrada del Profesional (Equipo Local):** Textarea editable + vista con las entidades detectadas resaltadas sobre el texto original usando sus offsets (`start`, `end`) con etiquetas de color por `entity_type` (`CEDULA`, `NIT`, `CELULAR`, `CORREO`, `RADICADO`, `PERSONA`, `DIRECCION`, `UBICACION`, `ORGANIZACION`, `RESIDUO`) e indicador de capa (`regex`, `ner`, `llm`). Debajo, el **Banner Ámbar de Advertencias de Cuasi-identificadores** (`warnings[]`).
     - **Columna 2 — Lo que Recibe la Nube (Payload Enmascarado):** Muestra exactamente el texto `masked` / `masked_prompt` con los tokens `⟦TIPO_N⟧` estilizados como píldoras monoespaciadas de alta visibilidad, más la respuesta cruda del upstream (`raw_upstream_response`) antes de reinsertar. Si ocurre un bloqueo HTTP 422 (`TAPAITO_RESIDUO` o `TAPAITO_VERIFIER_ERROR`), muestra un escudo rojo claro indicando: **"ENVÍO BLOQUEADO (FALLAR CERRADO): Ningún dato salió a la nube"**.
     - **Columna 3 — Respuesta Final Reinsertada + Informe de Reinserción:** Muestra el texto final para el usuario con los valores restaurados resaltados en verde, cualquier token no restaurado o desconocido resaltado en rojo/ámbar, y la tarjeta del **Informe de Reinserción (`reinsertion_report`)** con contadores y chips para: `Restaurados`, `Faltantes`, `Desconocidos`, `Ambiguos` y `% Tasa de Restauración`, además del desglose de latencias (`layer1_2`, `layer3`, `upstream`, `total`).
  4. **Panel Inferior — Audit Log Local JSONL en Vivo (`/v1/tapaito/audit`):**
     - Botón `"Actualizar Audit Log"` (y actualización automática tras cada petición).
     - Tabla mostrando `timestamp`, `request_id`, `mode`, `result` (`enviado`/`bloqueado`), `counts_by_type`, offsets (`start..end`) y `latency_ms`, destacando explícitamente que **no existe ninguna columna ni campo con valores originales (CE6)**.

## 5. Entregable `docs/DEMO.md`

Crea `docs/DEMO.md` siguiendo la sección 15 de `TAPAITO.md`:
- Guion cronometrado de **90 segundos** dividido en los 6 bloques exactos (`0–10 s`, `10–30 s`, `30–50 s`, `50–70 s`, `70–85 s`, `85–90 s`).
- Qué clic hacer en la UI en cada bloque y qué decir en voz alta.
- Los textos sintéticos exactos de respaldo para copiar y pegar.
- Cómo ejecutar la demo 100 % offline con el upstream mock.

Cuando termines, haz commit únicamente de `src/tapaito/ui/index.html`, `src/tapaito/ui/styles.css`, `src/tapaito/ui/app.js` y `docs/DEMO.md` con el mensaje `feat(ui): add split-screen clinical audit UI and 90s demo script`.
```
---
