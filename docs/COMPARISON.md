# Comparativa Honesta con Alternativas Abiertas (`COMPARISON.md`)

> **Regla de rigor (§12 y §14 de `TAPAITO.md`):** Esta comparativa evalúa a **Tapaito** frente a herramientas de código abierto existentes en el ecosistema de protección de PII para LLMs. No se inventan capacidades ni carencias; cualquier aspecto que dependa de configuraciones no documentadas de forma estándar se indica explícitamente como `"no verificado"` o `"requiere desarrollo a medida"`.

---

## 1. Tabla Comparativa Verificada

| Característica / Capacidad | **Tapaito (MVP v0.1.0)** | **Microsoft Presidio** (`presidio-analyzer` + `presidio-anonymizer`) | **LLM Guard** (Protect AI — `Vault` + `Anonymize` / `Deanonymize`) |
|---|---|---|---|
| **Licencia Open Source** | Apache 2.0 | MIT | MIT |
| **Modo de despliegue principal** | Proxy HTTP local compatible con OpenAI (`/v1/chat/completions`, cambiar solo `base_url`) + UI pantalla dividida integrada (`/ui`) | Librería Python / microservicios REST (`analyzer`, `anonymizer`); no incluye por defecto un proxy directo `/v1/chat/completions` con reinserción | Librería Python / servidor API de escaneo de prompts y salidas |
| **Detector nativo de NIT Colombiano con algoritmo DIAN (pesos primos 3..71, mod 11)** | **Sí (incluido y validado en Capa 1)** | **No incluido por defecto** (incluye reconocedores para US SSN, UK NHS, ES NIF, IT, PL, SG, AU, IN; para Colombia requiere programar un `PatternRecognizer` + `validate_result` propio) | **No incluido por defecto** (delega en Presidio o modelos NER genéricos; requiere reconocedor personalizado) |
| **Detector nativo de Radicado Judicial Colombiano (23 dígitos CSJ)** | **Sí (incluido y validado en Capa 1)** | **No incluido por defecto** (requiere `PatternRecognizer` a medida) | **No incluido por defecto** |
| **Detector nativo de Celular Colombiano (`+57` / `3[0-5]\d{8}`) y Cédula con contexto clínico negativo (`CUPS`, `CIE-10`, `INVIMA`)** | **Sí (incluido en Capa 1 + `MEDICAL_STOPLIST` en Capa 2)** | Soporte genérico de teléfonos vía `PhoneRecognizer` (`phonenumbers`), pero **sin** filtro nativo de contexto negativo para códigos clínicos colombianos (`CUPS`/`INVIMA`) ni cédula colombiana por defecto | Soporte genérico de teléfonos y NER; sin filtros nativos para códigos médicos colombianos (`CUPS`/`INVIMA`) |
| **Verificador semántico residual con LLM local (auditar el texto *ya enmascarado* + política "fallar cerrado")** | **Sí (Capa 3 con Qwen3 4B vía Ollama, JSON Schema, 1 reenmascarado y bloqueo HTTP 422 `TAPAITO_RESIDUO` / `TAPAITO_VERIFIER_ERROR`)** | **No incluido como verificador residual post-máscara con bloqueo** (Presidio se enfoca en detección primaria con regex/NER/Transformers) | **No como auditor LLM post-máscara** (usa modelos DeBERTa/RoBERTa para detección primaria de PII y prompt injection, no un LLM local que audite el texto ya enmascarado ni advierta cuasi-identificadores) |
| **Advertencias de Cuasi-identificadores por contexto (sin alterar el texto clínico)** | **Sí (`warnings[]` generados por Qwen3 en Capa 3 y visibles en `/ui`)** | No incluido | No incluido |
| **Reinserción tolerante a mutaciones del LLM (`[persona_1]`, `⟦ PERSONA_1 ⟧`) + Informe estructurado (`restaurados`, `faltantes`, `desconocidos`, `ambiguos`)** | **Sí (`reinsert_tokens` + `ReinsertionReport` por petición)** | `presidio-anonymizer` incluye un `DeanonymizeEngine` por reemplazo exacto de operadores, pero **no** un motor de reinserción tolerante a corchetes/mayúsculas alteradas por LLMs con reporte de tokens `ambiguos`/`desconocidos` | Incluye scanner `Deanonymize` con `Vault` (con coincidencia exacta o difusa opcional), pero **no** emite el desglose estructurado de `restaurados`, `faltantes`, `desconocidos` y `ambiguos` en el contrato de respuesta OpenAI |
| **Benchmark abierto de textos clínicos sintéticos colombianos (**PII-CO**)** | **Sí (`bench/` con semillas fijas `dev`/`test`, hash SHA-256 y evaluación de fugas residuales)** | Cuenta con `presidio-research` (datos sintéticos principalmente en inglés/multilingüe general, sin corpus clínico colombiano con NIT-DV y radicados de 23 dígitos) | No incluye un benchmark específico de textos clínicos colombianos |
| **Madurez general, soporte multilingüe e integraciones empresariales (Kubernetes, Spark, OCR de imágenes)** | **No (MVP acotado a texto en español y vertical clínico colombiano)** | **Alta** (`presidio-image-redactor`, soporte multi-idioma, despliegue empresarial probado) | **Alta** (múltiples scanners adicionales de toxicidad, secretos, código y relevancia) |

---

## 2. Cuándo Usar Cada Herramienta

- **Cuándo elegir Microsoft Presidio o LLM Guard:**
  - Si necesitas procesar múltiples idiomas (inglés, alemán, etc.), redactar texto dentro de imágenes (`presidio-image-redactor`), o integrar un pipeline corporativo con decenas de escáneres genéricos y cuentas con un equipo de ingeniería para escribir y mantener tus propios `PatternRecognizer` colombianos.
- **Cuándo elegir Tapaito:**
  - Si trabajas con textos clínicos o administrativos en **Colombia** (donde abundan cédulas sin checksum, NIT con dígito de verificación DIAN, celulares `3xx`, radicados de 23 dígitos y códigos médicos `CUPS`/`CIE-10`), necesitas **conectarlo en 1 minuto cambiando solo `base_url`**, quieres una **segunda línea de defensa local con Qwen3 4B** que falle cerrado ante cualquier residuo, y necesitas visibilidad transparente mediante la UI de pantalla dividida y el informe de reinserción.
