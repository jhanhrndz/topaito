# TAPAITO — Especificación del proyecto para el agente de IA

> Este archivo es la **fuente de verdad** del proyecto. Léelo completo antes de actuar.
> Si algo aquí contradice una suposición tuya, gana este archivo. Si algo es ambiguo, decide la opción más simple que cumpla los criterios de aceptación y regístrala en `docs/DECISIONS.md`.

---

## 1. Resumen

**Tapaito** es un proxy local, compatible con la API de OpenAI (`/v1/chat/completions`), que se ubica entre cualquier aplicación y una IA en la nube. Antes de que el texto salga del equipo:

1. **Enmascara datos personales colombianos** (cédula, NIT con dígito de verificación, celular, correo, radicado judicial, nombres, direcciones) usando regex con validadores, NER en español y un modelo abierto local.
2. **Verifica con un modelo abierto local (Qwen3 4B vía Ollama)** que no quedó nada sin enmascarar. El modelo *audita* el texto ya enmascarado; no detecta desde cero.
3. **Reinserta** los datos reales en la respuesta de la nube y entrega un **informe de reinserción** visible.
4. **Mide su desempeño** con **PII-CO**, un benchmark abierto de textos sintéticos colombianos con etiquetas exactas.

Frase de venta: *"Los profesionales ya usan IA con datos de sus clientes. Tapaito les permite seguir haciéndolo exponiendo menos, y mide cuánto logra."*

## 2. Contexto del hackathon

- Se debe construir un **proyecto original que use IA open source / open-weight como parte importante de su funcionamiento** (Enfoque 1), o un proyecto con Gemma 4 vía Gemini API (Enfoque 2).
- **Decisión: Enfoque 1.** El modelo abierto local (Qwen3 4B) es parte estructural: es el verificador que garantiza el principio "el dato sensible nunca sale identificable del equipo".
- Gemma 4 **no es parte central**. Opcionalmente puede ser el destino "nube" de la demo si su endpoint es accesible de forma compatible con OpenAI. Verifícalo en la documentación oficial; si no es trivial, no lo hagas.
- Tiempo total disponible: **~5 horas** de ejecución. Desarrollo asistido por agentes (tú y tus subagentes).
- Criterios típicos de jurado a optimizar: originalidad, uso real del modelo abierto, utilidad, calidad técnica, demo clara, documentación, honestidad sobre límites.

## 3. Problema

Médicos, abogados, contadores y equipos pequeños pegan documentos con datos personales en chatbots en la nube por productividad, casi siempre sin política interna. En Colombia, la Ley 1581 de 2012 (habeas data) clasifica los datos de salud como sensibles y regula su tratamiento y transferencia. No existe una herramienta abierta, ligera y local, con detectores colombianos validados y desempeño medido, que reduzca esa exposición sin cambiar las herramientas del usuario.

## 4. Finalidad y criterios de éxito

**Finalidad:** reducir la exposición de datos personales hacia proveedores de IA en la nube, de forma demostrable y medible, con adopción de bajo costo (cambiar una URL).

**Criterios de éxito del MVP (todos deben cumplirse o declararse como no cumplidos en el README):**

| ID | Criterio | Verificación |
|---|---|---|
| CE1 | Un cliente OpenAI existente funciona cambiando solo `base_url` | Test E2E con el SDK `openai` de Python |
| CE2 | En el conjunto de prueba, el recall de identificadores estructurados (cédula, NIT, celular, correo, radicado) en modo Rápido es ≥ 0.95 | `make bench` |
| CE3 | La capa Qwen verificadora recupera al menos un porcentaje medible de residuos que regex+NER no detectaron | `make bench`, tabla por configuración |
| CE4 | La reinserción restaura ≥ 95 % de los tokens en tareas cerradas con el upstream mock y reporta fallos explícitamente | Tests + informe de reinserción |
| CE5 | Política "fallar cerrado": si el verificador falla o hace timeout en modo Estricto, la petición se bloquea | Test automatizado |
| CE6 | El audit log nunca contiene valores originales | Test automatizado que busca valores conocidos en el log |
| CE7 | Instalación y demo en ≤ 5 comandos documentados | Probado desde cero en un entorno limpio |
| CE8 | Demo de 90 s grabable sin depender de la red | Upstream mock como respaldo |

## 5. Alcance

### Entra en el MVP

- Proxy FastAPI con `POST /v1/chat/completions` **sin streaming** y `GET /v1/models` mínimo.
- **Un solo vertical: clínicas** (historias clínicas, órdenes, epicrisis, citas, correos a pacientes).
- Detección en **3 capas** (regex+validadores → NER spaCy español → verificador Qwen3 4B).
- **Dos modos:** `rapido` (capas 1–2) y `estricto` (capas 1–3, fallar cerrado).
- Tokens de seudónimo estrictos y coherentes por sesión; reinserción tolerante; informe de reinserción.
- Audit log local JSONL sin valores originales.
- Benchmark **PII-CO** (≈ 40–60 casos de prueba + conjunto de desarrollo aparte) con generador determinista.
- Métrica de utilidad (10–15 casos): resumen con datos enmascarados vs. sin enmascarar.
- UI de **pantalla dividida** servida por el propio FastAPI (HTML + JS sin build).
- Advertencias (sin enmascarar) de cuasi-identificadores detectados por Qwen.
- README, LICENSE (Apache 2.0), `docs/LIMITS.md` ("Qué NO garantiza"), tabla comparativa honesta con alternativas.

### NO entra (declarar como trabajo futuro, no implementar)

Imágenes/multimodal, streaming, otros verticales (bufetes, contadores, RRHH), cola de revisión humana, resolución automática de re-identificación por contexto, autenticación/multiusuario, despliegue en nube, fine-tuning de modelos, cumplimiento legal certificado, soporte de documentos PDF/DOCX.

> **Regla anti-alcance:** si una tarea no mapea a un RF de este archivo, no se hace. Cualquier idea nueva va a `docs/FUTURE.md`.

## 6. Requisitos

### Funcionales

- **RF1** Endpoint compatible con OpenAI chat completions (mensajes `system`/`user`/`assistant`; se procesan todos los mensajes de texto).
- **RF2** Detectores de capa 1 con validadores: cédula (6–10 dígitos, con contexto de palabras clave porque no tiene checksum), NIT (9 dígitos + DV, **validar DV con algoritmo DIAN**), celular colombiano (`3[0-5]\d{8}`, con/sin `+57`/`57`, con separadores), correo, radicado judicial (23 dígitos), cuenta/IBAN-like opcional, fechas de nacimiento con contexto.
- **RF3** Capa 2: spaCy `es_core_news_md` para PER, ORG, LOC; filtros para reducir falsos positivos (p. ej. términos médicos, nombres de medicamentos).
- **RF4** Capa 3: Qwen3 4B local, salida JSON con esquema fijo, entrada = texto ya enmascarado, salida = lista de hallazgos residuales `{texto, tipo, confianza}` y lista de `advertencias` de cuasi-identificadores.
- **RF5** Almacén de sesión: mapa `valor ↔ token` coherente (mismo valor → mismo token en la sesión); TTL y borrado explícito (`DELETE /v1/tapaito/session/{id}`). Solo en memoria.
- **RF6** Tokens con formato `⟦TIPO_N⟧` (p. ej. `⟦PERSONA_1⟧`, `⟦CEDULA_2⟧`). Inyección de instrucción de sistema que pide conservar los tokens literalmente.
- **RF7** Reinserción tolerante a mayúsculas, espacios y corchetes alterados; informe por respuesta: `restaurados`, `faltantes`, `desconocidos`, `ambiguos`.
- **RF8** Modo `estricto`: tras enmascarar, verificar; si hay residuos, enmascarar y reverificar; si persisten, **bloquear** con error claro (HTTP 422 con código `TAPAITO_RESIDUO`).
- **RF9** Audit log JSONL local: timestamp, id de petición, modo, conteo por tipo, posiciones (offsets), resultado (`enviado`/`bloqueado`), latencias por capa. **Nunca valores originales.**
- **RF10** Endpoint `POST /v1/tapaito/preview` que devuelve texto original, texto enmascarado, entidades con offsets y tipo (para la UI) sin llamar al upstream.
- **RF11** UI pantalla dividida: (a) lo que escribe el usuario con entidades resaltadas, (b) lo que recibe la nube, (c) respuesta final reinsertada + informe de reinserción. Toggle de modo. Vista del audit log.
- **RF12** Upstream configurable por entorno (`UPSTREAM_BASE_URL`, `UPSTREAM_API_KEY`, `UPSTREAM_MODEL`). Incluir un **upstream mock** local (para tests, benchmark de utilidad offline y respaldo de demo).
- **RF13** Comando `make bench` que genera el dataset (semilla fija), evalúa 3 configuraciones y escribe `bench/results/*.json` y una tabla Markdown.

### No funcionales

- **RNF1** Corre en portátil con **24 GB RAM / 4 GB VRAM**. Qwen3 4B en Q4 (`qwen3:4b`). Latencia de capas 1–2 < 300 ms por texto de ≤ 2.000 caracteres.
- **RNF2** Capa 3 con **límite de tokens de salida** y **timeout configurable** (por defecto 20 s). Solo audita texto ≤ N caracteres (configurable; trocear si es mayor).
- **RNF3** Qwen sin razonamiento largo: usar el parámetro de Ollama para desactivar "thinking" o `/no_think`; **verificar en la versión instalada de Ollama cuál funciona** y registrarlo.
- **RNF4** Python 3.11+, tipado, `ruff`, `pytest`, cobertura de los módulos críticos (validadores, reinserción, política fallar cerrado).
- **RNF5** 100 % open source; dependencias con licencias compatibles con Apache 2.0.
- **RNF6** Reproducible: `Makefile`, `pyproject.toml`, semillas fijas, versiones fijadas.
- **RNF7** Sin telemetría ni llamadas de red salvo al upstream configurado y a Ollama local.
- **RNF8** **Solo datos sintéticos.** Prohibido usar datos personales reales en tests, ejemplos o capturas.

## 7. Arquitectura

```
 App cliente (SDK OpenAI)                       ┌─────────────────────────────┐
        │  base_url=http://localhost:8080/v1    │   Ollama (Qwen3 4B, local)  │
        ▼                                       └──────────────▲──────────────┘
┌───────────────────────────────────────────────────────────────┼──────────┐
│ TAPAITO (FastAPI)                                              │          │
│                                                                │          │
│  Request ─► [1] Regex+Validadores ─► [2] NER spaCy ─► Merge ─► [3] Verificador Qwen
│                                                         │         (solo modo estricto)
│                                  Almacén de sesión ◄────┤              │
│                                  (valor ↔ ⟦TOKEN⟧)      ▼              ▼
│                                              Texto enmascarado ─► ¿residuo? ─► bloquear / reenmascarar
│                                                         │
│                                                         ▼
│                                           Upstream (OpenAI-compatible / mock)
│                                                         │
│  Respuesta ◄─ Reinserción tolerante + Informe ◄─────────┘
│       │
│       └─► Audit log JSONL (sin valores)      UI split-screen (/ui)
└──────────────────────────────────────────────────────────────────────────┘
```

### Estructura de carpetas sugerida

```
tapaito/
├── AGENTS.md                 # copia/resumen operativo de este archivo para agentes
├── TAPAITO.md                # este archivo
├── PLAN.md                   # lo genera el agente (ver §11)
├── README.md  LICENSE  Makefile  pyproject.toml
├── src/tapaito/
│   ├── api/                  # FastAPI: routers, esquemas, errores
│   ├── detect/
│   │   ├── regex_layer.py    # patrones colombianos
│   │   ├── validators.py     # NIT-DV, celular, radicado, cédula+contexto
│   │   ├── ner_layer.py      # spaCy + filtros
│   │   ├── llm_verifier.py   # Qwen vía Ollama, JSON con esquema
│   │   └── merge.py          # fusión de spans, prioridad y solapes
│   ├── mask/                 # tokens, almacén de sesión, enmascarado
│   ├── restore/              # reinserción tolerante + informe
│   ├── policy/               # modos, fallar cerrado, timeouts
│   ├── audit/                # log JSONL sin valores
│   ├── upstream/             # cliente OpenAI-compatible + mock
│   └── ui/                   # index.html, app.js, styles.css
├── bench/
│   ├── generator/            # plantillas clínicas + generador determinista
│   ├── data/dev/  data/test/ # conjuntos separados
│   ├── run_bench.py  utility_eval.py
│   └── results/
├── tests/
└── docs/  DECISIONS.md  LIMITS.md  COMPARISON.md  FUTURE.md  DEMO.md  RISKS.md
```

### Contrato del API (resumen)

- `POST /v1/chat/completions` — cuerpo OpenAI estándar. Cabeceras opcionales: `X-Tapaito-Mode: rapido|estricto`, `X-Tapaito-Session: <id>`. La respuesta es la estándar de OpenAI **más** un campo `tapaito` con el informe (`entities_masked`, `reinsertion_report`, `mode`, `latency_ms`).
- `POST /v1/tapaito/preview` — `{text, mode}` → `{masked, entities[], warnings[], latency_ms}`.
- `GET /v1/tapaito/audit?limit=N` — últimas entradas del log (sin valores).
- `DELETE /v1/tapaito/session/{id}` — borra el mapa de la sesión.
- `GET /ui` — interfaz de pantalla dividida. `GET /healthz`.

### Notas técnicas obligatorias

- **NIT:** el DV se calcula con el algoritmo de la DIAN (pesos de primos 3, 7, 13, 17, 19, 23, 29, 37, 41, 43, 47, 53, 59, 67, 71 aplicados de derecha a izquierda sobre el número; `residuo = suma mod 11`; DV = residuo si es 0 o 1, si no `11 − residuo`). **Verifica la implementación con NIT reales públicos conocidos de empresas** (que no son datos personales) y con casos construidos a mano, y documenta la fuente.
- **Cédula:** no tiene dígito verificador público; exigir contexto ("cédula", "C.C.", "CC", "documento", "identificación") o formato con puntos para reducir falsos positivos. Documentar el trade-off precisión/recall.
- **Fusión de spans:** ante solapes, prevalece el tipo estructurado validado sobre el NER. Mantener offsets sobre el texto original.
- **Qwen:** usar salida estructurada (parámetro `format` con JSON schema de Ollama) y `temperature` 0. Si el JSON es inválido: un reintento; si falla de nuevo, en modo estricto → bloquear.
- **Prompt injection:** el texto del usuario pasa al verificador local como **dato**, no como instrucciones; el prompt del verificador debe decirlo explícitamente y se debe tener un test con un texto que intente "ordenar" al verificador que ignore datos.

## 8. Reinserción robusta (decisiones fijadas)

1. Formato de token poco ambiguo (`⟦PERSONA_1⟧`), no palabras flexionables.
2. Instrucción de sistema inyectada: conservar tokens literalmente, sin traducir, sin modificar.
3. Caso de uso principal: **tareas cerradas** (resumir, extraer campos, redactar plantilla con tokens).
4. Reinserción tolerante (mayúsculas, espacios, variaciones de corchetes) con coincidencia exacta primero y tolerante después; nunca adivinar entre tokens ambiguos.
5. **Informe de reinserción** por respuesta; los fallos se muestran resaltados en la UI, nunca se ocultan.
6. Un token desconocido en la respuesta **no** se sustituye y se reporta.

## 9. Política "fallar cerrado" y privacidad del propio sistema

- Modo `estricto`: ante error, timeout o JSON inválido del verificador → **bloquear**.
- Residuo persistente tras reenmascarar → **bloquear**.
- El audit log guarda tipo, offsets, conteos y latencias; **no valores**. Test automático que lo comprueba.
- El mapa valor↔token vive solo en memoria con TTL; no se persiste a disco.
- Los logs de la aplicación (uvicorn, excepciones) no deben imprimir el cuerpo de las peticiones. Revisar trazas de error.
- El proxy escucha solo en `127.0.0.1` por defecto.
- Las claves del upstream vienen de variables de entorno; nunca se registran.

## 10. Benchmark PII-CO y evaluación

- **Generador determinista** (semilla fija) con plantillas clínicas colombianas: cédulas, NIT con DV válido, celulares, correos, radicados de 23 dígitos, nombres y apellidos comunes, direcciones colombianas (Calle/Carrera/Diagonal), municipios, EPS/IPS ficticias o genéricas. **Las etiquetas son exactas por construcción.**
- Casos **difíciles** a propósito: nombres que son palabras comunes, números largos que no son cédulas (códigos CUPS/CIE-10, lotes, dosis), formatos con separadores, nombre partido por salto de línea, apodos, mayúsculas/minúsculas mezcladas, errores tipográficos, cuasi-identificadores (cargo + lugar poco común).
- Un LLM puede **parafrasear** para dar variedad, pero las etiquetas se recalculan por offsets o se descartan los casos donde ya no coincidan.
- **Separación estricta:** `dev` para ajustar, `test` para reportar. Prohibido ajustar reglas mirando `test`. Registrar el hash del conjunto de prueba.
- **Métricas:** precisión, recall y F1 **por tipo de entidad** y global, a nivel de span (exacto y con solape), latencia p50/p95 por configuración.
- **Configuraciones:** (A) Regex+validadores, (B) A + NER, (C) B + verificador Qwen. Tabla Markdown en README generada automáticamente.
- **Fugas residuales:** métrica clave = % de valores sensibles que **quedan visibles** en el texto enviado (por tipo).
- **Utilidad:** en 10–15 casos, comparar resumen/extracción con texto original vs. enmascarado usando el upstream (real o mock) y una rúbrica simple (campos clave presentes: sí/no). Reportar honestamente.
- Si un resultado es malo, **se publica igual** y se explica; no se maquilla.

## 11. Modo de trabajo del agente

### 11.1 Paso 0 — antes de escribir código

1. Lee este archivo completo.
2. **Inventaría los skills disponibles** (revisa los `SKILL.md` instalados) y haz una tabla `skill → tarea donde aplica`. Usa los skills que apliquen (p. ej. diseño frontend para la UI, documentación para README/docs, lectura/creación de archivos); no fuerces skills que no aporten.
3. Genera **`PLAN.md`** con: fases, tareas, dependencias, estimación en minutos, criterio de aceptación de cada tarea, subagente responsable, skill aplicable, y qué riesgo (§13) mitiga cada tarea. Debe sumar ≤ 5 horas con ~20 min de colchón.
4. Genera **`docs/RISKS.md`** con la evaluación de riesgos (ver §13): reevalúa probabilidad/impacto, añade riesgos nuevos que detectes y define una prueba o métrica para cada mitigación.
5. **Punto de control único:** presenta `PLAN.md` y `RISKS.md` al humano y espera aprobación. Tras aprobarse, ejecuta sin más pausas salvo bloqueos reales.

### 11.2 Metodología

- **Desarrollo por fases con incrementos verificables**, con *Definition of Done* explícito por tarea:
  código + pruebas pasando + `ruff` limpio + documentación mínima + commit.
- **TDD en lo crítico:** validadores, fusión de spans, reinserción, política fallar cerrado, audit log.
- **Spike temprano de riesgo (primeros 30 min):** medir latencia real de Qwen3 4B en la laptop antes de comprometer la arquitectura de la capa 3.
- **Vertical slice primero:** lo antes posible, una petición completa de extremo a extremo (regex → upstream mock → reinserción), y luego se enriquece capa por capa.
- **Git:** repositorio desde el inicio, ramas cortas por fase o tarea, commits pequeños con mensajes convencionales (`feat:`, `fix:`, `test:`, `docs:`), tag `v0.1.0-mvp` al terminar.
- **Registro de decisiones** en `docs/DECISIONS.md` (contexto, decisión, alternativa descartada).
- **Honestidad técnica:** no declares algo funcionando sin haberlo ejecutado. Pega la evidencia (salida de tests, tabla del benchmark) en el reporte de cada fase.
- **Si una tarea excede 150 % de su estimación:** recorta alcance según §5 y registra el recorte; nunca sacrifiques los criterios CE2, CE5, CE6.

### 11.3 Subagentes (roles; ejecutar en paralelo cuando no haya dependencia)

| Subagente | Responsabilidad | Entrega |
|---|---|---|
| **Arquitecto/Integrador** | Esqueleto, contrato del API, tipos compartidos, integración, revisión final | `api/`, `policy/`, `upstream/`, DECISIONS.md |
| **Detección-Estructurada** | Regex, validadores (NIT-DV, celular, radicado, cédula+contexto), pruebas | `detect/regex_layer.py`, `validators.py`, tests |
| **Detección-NER/LLM** | spaCy + filtros, verificador Qwen, esquema JSON, anti-injection, timeouts | `ner_layer.py`, `llm_verifier.py`, tests |
| **Máscara-Reinserción** | Tokens, almacén de sesión, reinserción tolerante, informe | `mask/`, `restore/`, tests |
| **Benchmark/Datos** | Generador determinista, splits, métricas, utilidad, tabla de resultados | `bench/` |
| **Seguridad/Privacidad (revisor)** | Audit sin valores, logs sin cuerpos, fallar cerrado, prompt-injection, revisión de dependencias | tests de seguridad, `docs/RISKS.md` actualizado |
| **UI/Demo** | Pantalla dividida, resaltado, informe, vista de audit, guion de demo | `ui/`, `docs/DEMO.md` |
| **Documentación/Calidad** | README, LIMITS, COMPARISON, instalación en frío, licencia | docs, README |

Reglas para subagentes: contexto mínimo suficiente (este archivo + su tarea + interfaces), un solo responsable por archivo, **el Integrador revisa y fusiona**, y el revisor de Seguridad tiene poder de veto sobre CE5/CE6.

### 11.4 Fases sugeridas (el agente puede ajustarlas en PLAN.md)

| Fase | Tiempo | Resultado |
|---|---|---|
| **F0 Preparación y spike** | 0:00–0:30 | Repo, entorno, Ollama + Qwen3 4B, latencia medida, esqueleto con upstream mock, PLAN/RISKS aprobados |
| **F1 Capa 1 + máscara + reinserción** | 0:30–1:30 | Validadores, tokens, sesión, reinserción, informe; slice E2E con mock |
| **F2 Capa 2 + capa 3 + política** | 1:30–2:15 | NER, verificador Qwen, modos, fallar cerrado, audit log |
| **F3 Benchmark PII-CO** | 2:15–3:15 | Generador, dev/test, métricas, tabla, utilidad |
| **F4 Mejora guiada por dev** | 3:15–3:45 | Corregir debilidades vistas en `dev` (nunca en `test`), re-medir |
| **F5 UI + demo** | 3:45–4:30 | Pantalla dividida, vista de audit, guion y grabación de respaldo |
| **F6 Cierre** | 4:30–5:00 | README, LIMITS, COMPARISON, instalación en frío, tag, colchón |

## 12. Entregables

1. Repositorio con licencia **Apache 2.0**.
2. `README.md`: problema, demo (GIF o enlace), instalación en ≤ 5 comandos, arquitectura, tabla de benchmark, límites.
3. `docs/LIMITS.md` — **"Qué NO garantiza"**: no es anonimización, no es asesoría legal, no certifica cumplimiento, ningún detector es perfecto, re-identificación por contexto posible, solo texto y español.
4. `docs/COMPARISON.md` — tabla honesta contra alternativas abiertas existentes (p. ej. Microsoft Presidio, LLM Guard u otras). **Investiga en la documentación actual de cada una; no inventes capacidades ni carencias.** Si no puedes verificar algo, escribe "no verificado".
5. `bench/results/` con datos y tabla reproducibles (`make bench`).
6. `docs/DEMO.md` con guion de 90 s y datos sintéticos para reproducirlo.
7. `docs/RISKS.md` con riesgos, mitigación aplicada y evidencia.
8. Video o grabación de respaldo de la demo (si el entorno lo permite; si no, guion + capturas).

## 13. Riesgos detectados — evaluar, mitigar y probar

> **Instrucción:** en `docs/RISKS.md`, para cada riesgo: reevalúa probabilidad (B/M/A) e impacto (B/M/A), confirma o mejora la mitigación propuesta, asigna tarea y subagente, y define la **evidencia** (test, métrica o captura) que demuestra que se mitigó. Añade riesgos nuevos que identifiques.

| # | Riesgo | Prob. inicial | Impacto | Mitigación de diseño | Evidencia requerida |
|---|---|---|---|---|---|
| R1 | **"Esto ya existe"** (Presidio, proxies de enmascarado) | A | A | Foso colombiano (NIT-DV real, celular, radicado, cédula con contexto), benchmark PII-CO abierto, verificador residual local, tabla comparativa honesta | `COMPARISON.md` verificada; tabla de benchmark por tipo |
| R2 | **Reinserción frágil** (la nube reformula tokens) | A | A | Token estricto `⟦TIPO_N⟧`, instrucción de conservarlos, tareas cerradas, reinserción tolerante, informe visible, nunca adivinar | Tests con respuestas mock "hostiles" (mayúsculas, espacios, token omitido, token inventado); métrica de restauración |
| R3 | **Latencia de Qwen en 4 GB VRAM** | A | M | Spike inicial, capa 3 fuera del camino crítico, solo texto corto, salida JSON limitada, timeout, modo Rápido/Estricto | Medición p50/p95 documentada; test de timeout |
| R4 | **Datos de prueba sesgados o "demasiado fáciles"** | M | A | Generador determinista, casos difíciles a propósito, dev/test separados, hash del test, publicar resultados malos | Contador de casos difíciles; hash; sin ajuste sobre `test` |
| R5 | **Afirmaciones legales indebidas** | M | A | Lenguaje "reduce exposición", `LIMITS.md`, nunca "cumple Ley 1581" | Búsqueda automática en docs por frases prohibidas ("cumple la Ley", "100 % seguro", "anonimiza") |
| R6 | **Re-identificación por contexto** | A | M | No se promete resolver; Qwen emite advertencias de cuasi-identificadores sin enmascarar; documentado como límite | Casos en benchmark; sección en LIMITS |
| R7 | **Gemma 4 / enfoque 2 fuera** | B | B | Enfoque 1 explícito; upstream configurable (Gemma 4 opcional como destino de demo) | Nota en README |
| R8 | **Falsos positivos** que destruyen la utilidad (enmascarar medicamentos, códigos) | M | M | Filtros de NER, contexto para cédula, métrica de utilidad | Precisión por tipo; evaluación de utilidad |
| R9 | **El propio sistema filtra datos** (logs, trazas, mapa en disco) | M | A | Log sin valores, sin cuerpos en trazas, mapa solo en memoria, `127.0.0.1` | Tests de CE6; revisión del revisor de Seguridad |
| R10 | **Prompt injection contra el verificador local** | M | A | Texto como dato, esquema JSON fijo, modo estricto bloquea ante salida inválida | Test con texto adversarial |
| R11 | **Sobrealcance en 5 horas** | A | A | Alcance cerrado (§5), recortes pre-aprobados, vertical slice temprano, CE2/CE5/CE6 no negociables | Cumplimiento del PLAN; `FUTURE.md` |
| R12 | **Falla de demo en vivo** (Ollama lento, red caída, upstream caído) | M | A | Upstream mock, grabación de respaldo, datos de demo fijos, precalentar el modelo | Demo ejecutada offline una vez completa |
| R13 | **Falsa sensación de seguridad** (el usuario cree que es infalible) | M | A | Mostrar recall y fugas residuales, advertencias en UI ("revise antes de enviar"), documentación | Texto de UI y README revisados |
| R14 | **Dependencias o versiones que cambian** (Ollama, modelos, spaCy) | M | M | Versiones fijadas, comandos de instalación probados en frío, registrar versión de Ollama y del modelo | Instalación en frío exitosa |

## 14. Reglas generales del agente

1. **No inventes.** Si no verificaste algo (una versión, una característica de una librería, un dato legal), dilo.
2. **Solo datos sintéticos.** Nunca uses ni pidas datos personales reales.
3. **Pruébalo antes de decir que funciona.** Evidencia en cada reporte de fase.
4. **Mantén el alcance.** Lo nuevo va a `docs/FUTURE.md`.
5. **Lenguaje legal prudente** en todo texto del proyecto.
6. **No toques el conjunto `test` para ajustar reglas.**
7. **Reporta bloqueos temprano** con alternativas concretas, no al final.
8. **Calidad sobre cantidad:** menos funciones, bien medidas y demostrables.

## 15. Guion de demo (90 s)

1. (0–10 s) Problema: "los profesionales ya pegan datos de pacientes en chatbots".
2. (10–30 s) Se pega una historia clínica sintética; la UI muestra a la izquierda lo escrito con entidades resaltadas y a la derecha lo que recibe la nube con `⟦TOKENS⟧`.
3. (30–50 s) Llega la respuesta con datos reinsertados y el **informe de reinserción**.
4. (50–70 s) **Momento fuerte:** un caso donde regex y NER fallaron y el **verificador Qwen local** lo atrapó (modo Estricto), o un caso bloqueado por fallar cerrado.
5. (70–85 s) Tabla de benchmark PII-CO: recall por capa y fugas residuales.
6. (85–90 s) Cierre honesto: "reduce la exposición; no sustituye una revisión legal. Cambias una URL y listo."

## 16. Definición de "terminado"

El MVP está terminado cuando: los criterios CE1–CE8 están verificados (o los incumplidos están declarados con motivo), `make test` y `make bench` pasan desde un entorno limpio, `docs/RISKS.md` tiene evidencia por riesgo, el README permite a un tercero instalarlo y ver la demo, y existe el tag `v0.1.0-mvp`.
