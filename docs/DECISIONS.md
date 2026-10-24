# Registro de Decisiones Arquitectónicas y Técnicas (`DECISIONS.md`)

> Registro histórico de decisiones técnicas, configuraciones de modelos y hallazgos empíricos de Tapaito.

---

## D1 — Desactivación de "Thinking" y Configuración de Latencia de Qwen3 4B en Ollama

- **Contexto:** Se requiere ejecutar el modelo de verificación semántica `qwen3:4b` en máquinas con GPUs de consumo (4 GB VRAM) minimizando la latencia y desactivando el razonamiento largo oculto (*thinking*) para garantizar respuestas en formato JSON estricto.
- **Hallazgos empíricos verificados:**
  - **Entorno:** Windows, Python `3.13.14`, Ollama `0.35.1`, modelo `qwen3:4b` (ID `359d7dd4bcda`, 3.1 GB en memoria con `num_ctx=1536`, split `25% CPU / 75% GPU`).
  - **Causa raíz de latencia inicial:** Con el contexto por defecto de Qwen3, el KV cache excede los 4 GB de VRAM provocando offload pesado a CPU y carga en frío > 30 s. Al fijar `"options": {"num_ctx": 1536, "temperature": 0, "num_predict": 512}`, el modelo cabe en un 75 % en GPU.
  - **Desactivación de thinking verificada:** En Ollama `0.35.1`, pasar `"think": false` en el nivel raíz del JSON de `/api/chat` junto con `/no_think` al inicio del prompt de sistema produce `thinking_field_len = 0` (cero tokens de razonamiento oculto) y respeta estrictamente el `format` JSON Schema.
  - **Métricas reales de latencia:**
    - Primera corrida con modelo cargado: `7127.98 ms` (~7.1 s)
    - Corridas cálidas consecutivas: ~3.8 s a ~7.9 s
    - **Latencia p50 en benchmark:** `3893.86 ms` (~3.89 s)
    - **Latencia p95 en benchmark:** `7963.12 ms` (~7.96 s)
    - **Calidad de salida:** Detecta residuos atípicos (nombres en minúsculas sin etiqueta) y advierte cuasi-identificadores contextuales sin marcar erróneamente medicamentos (`Losartán 50 mg`, `Acetaminofén 500 mg`).
- **Decisión:**
  1. Usar simultáneamente `"think": False` en el payload de Ollama y `/no_think` en el system prompt.
  2. Fijar `num_ctx: 1536`, `num_predict: 512`, `temperature: 0`, `keep_alive: "15m"` y `MAX_VERIFY_CHARS = 1800` (troceando si el texto es mayor).
- **Alternativa descartada:** Dejar `num_ctx` por defecto (4096/32768), lo cual desborda los 4 GB de VRAM y multiplica por >4x la latencia.

---

## D2 — Servidor Estático Integrado para la Estación de Auditoría Clínica

- **Contexto:** Se requiere servir la interfaz de usuario de pantalla dividida directamente desde la aplicación sin requerir pasos de compilación complejos (Node.js/npm) para garantizar una instalación rápida y funcionamiento 100 % offline.
- **Decisión:** Desarrollar la interfaz en HTML5, CSS3 y JavaScript Vanilla puro en `src/tapaito/ui/`, servida directamente por FastAPI en `GET /ui` y montando los recursos estáticos en `/ui/static` mediante `StaticFiles`.
- **Alternativa descartada:** Usar un framework frontend compilado (React/Vite) que exigiría instalar Node.js y npm, aumentando el tamaño del proyecto y la fricción de instalación.

---

## D3 — Trade-off Precisión/Recall en Cédula Colombiana + Barrido de Sesión

- **Contexto:** La cédula de ciudadanía colombiana (6 a 10 dígitos) no tiene dígito de verificación público. En textos clínicos abundan números de 6 a 10 dígitos que **no** son documentos de identidad (códigos CUPS de 6 dígitos como `890201`, registros INVIMA, números de lote, órdenes de laboratorio o dosis altas en `UI`/`ml`).
- **Decisión:**
  1. En `validators.py::has_cedula_context`, evaluar primero una ventana de **contexto negativo inmediato** (`CUPS`, `CIE-10`, `lote`, `INVIMA`, `orden #`, `cama`, `habitación`, y unidades pospuestas `mg`, `ml`, `mcg`, `UI`, `mmHg`, etc.).
  2. Exigir **contexto positivo** (`cédula`, `CC`, `C.C.`, `documento`, `identificación`, `portador`, `DNI`, `T.I.`) en una ventana de 45 caracteres previos / 25 posteriores (cortada en signos de puntuación `;`/`.` para no contaminar oraciones contiguas), **o** formato explícito con puntos de miles colombianos (`1.032.456.789` o `79.456.123`).
  3. Combinar lo anterior con el **Barrido de Sesión (*Second-Pass Session Sweep*)** en `masker.py`: una vez que la cédula se detecta con contexto al inicio del documento o sesión, cualquier aparición posterior del mismo número limpio (incluso sin `"CC"` ni puntos) se enmascara automáticamente con el mismo token `⟦CEDULA_1⟧`.
- **Alternativa descartada:** Enmascarar cualquier número de 6–10 dígitos sin contexto, lo cual destruye la utilidad clínica al ocultar códigos CUPS, lotes y valores de laboratorio.

---

## D4 — Refinamiento de Filtros Clínicos NER Guiado Exclusivamente por `dev`

- **Contexto:** Al evaluar inicialmente el conjunto de desarrollo `bench/data/dev/dataset.jsonl` (30 casos, sin tocar `test`), el detector spaCy `es_core_news_md` generó falsos positivos sobre encabezados documentales en mayúsculas (`HISTORIA CLÍNICA DE EVOLUCIÓN`, `ORDEN MÉDICA AMBULATORIA`, `CUMPLIMIENTO DE`, `TUTELA`, `SALUD`, `Radicado`, `Asegurador`, `Egreso`, `Atendido`, `Cuadro`) y verbos de prescripción (`Continuar Metformina`).
- **Decisión:** Ampliar `MEDICAL_STOPLIST` y `_CLINICAL_NON_NAME_WORDS` en `src/tapaito/detect/ner_layer.py` para descartar encabezados documentales y verbos de prescripción clínica, preservando intacta la detección de nombres de instituciones de salud reales (`Clínica ...`, `Hospital ...`, `Fundación ...`). Tras el ajuste, los falsos positivos en `dev` bajaron a `0` sin haber leído ni modificado jamás `bench/data/test/dataset.jsonl` (cuyo hash SHA-256 `1d4edee3c11e3773879f1ed095a8ae5dc01dea5a0d2671851edd2b8e76d9bace` se mantuvo intacto).
- **Alternativa descartada:** Desactivar las etiquetas `ORG` o `LOC` de spaCy por completo, lo que habría reducido el recall sobre nombres de clínicas/EPS y municipios.
