# Trabajo Futuro y Elementos Fuera del Alcance del MVP (`FUTURE.md`)

> Siguiendo la sección 5 de [`TAPAITO.md`](file:///C:/Users/jchrn/Documents/Trabajos/Personal/hacktoberfest/TAPAITO.md) (*Regla anti-alcance*), todo elemento que no mapea a los requisitos funcionales RF1–RF13 del MVP se documenta aquí como evolución futura.

---

## 1. Funcionalidades Declaradas Fuera del Alcance del MVP (§5)

1. **Soporte de Streaming SSE (`stream: true` en `/v1/chat/completions`):**
   - *Motivo de exclusión:* La reinserción tolerante de tokens (`⟦PERSONA_1⟧`, `[persona_1]`) requiere un buffer de ventana deslizante sobre los chunks SSE para no cortar un token a mitad de emisión. En el MVP se opera con respuestas completas sin streaming.
2. **Otros Verticales Colombianos (Bufetes Jurídicos, Contadores/Tributario, RRHH):**
   - *Motivo de exclusión:* El MVP se enfoca en el vertical **clínicas** (historias clínicas, epicrisis, órdenes médicas, tutelas en salud y correos a pacientes) para maximizar la precisión de los filtros médicos (`MEDICAL_STOPLIST`) y del benchmark **PII-CO**.
3. **Procesamiento de Documentos Binarios (PDF, DOCX, HL7/FHIR) e Imágenes/Multimodal:**
   - *Motivo de exclusión:* Extraer texto manteniendo el diseño de un PDF o redactar texto quemado en imágenes médicas (DICOM/PNG) requiere motores OCR locales y pipelines de reconstrucción documental fuera de un proxy ligero de API.
4. **Cola de Revisión Humana Asíncrona y Autenticación Multiusuario:**
   - *Motivo de exclusión:* Tapaito está diseñado como un proxy local ligero (`127.0.0.1`) de adopción inmediata cambiando únicamente `base_url` en el equipo del profesional.
5. **Resolución Automática de Re-identificación por Contexto:**
   - *Motivo de exclusión:* Reescribir automáticamente cuasi-identificadores clínicos (ej. generalizar edades o cargos) altera el contenido médico y puede inducir errores clínicos. El MVP detecta y advierte (`warnings`), pero no reescribe hechos clínicos.
6. **Fine-tuning de Modelos Locales (LoRA sobre Qwen3 / spaCy clínico):**
   - *Motivo de exclusión:* El MVP evalúa el desempeño base de `es_core_news_md` + `qwen3:4b` zero-shot con esquema JSON estructurado sobre el benchmark abierto PII-CO.

---

## 2. Mejoras Técnicas Identificadas Durante el Desarrollo

1. **Verificación paralela por oración en Capa 3:** Cachear en memoria (por hash SHA-256 de la oración enmascarada) las oraciones clínicas estándar ya auditadas por Qwen3 en la misma sesión para reducir la latencia del modo `estricto` en conversaciones largas.
2. **Validador de dígito de verificación para cuentas bancarias y tarjetas (Luhn):** Añadir validación Luhn opcional al detector de cuentas/tarjetas en Capa 1.
3. **Integración opcional con Gemma 4 como destino Upstream:** Conectar `UPSTREAM_BASE_URL` al endpoint compatible con OpenAI de Google Gemini API (`https://generativelanguage.googleapis.com/v1beta/openai/`) para usar modelos Gemma/Gemini como proveedor en la nube detrás del proxy Tapaito.
