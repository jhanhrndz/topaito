# Límites Conocidos y Qué NO Garantiza Tapaito (`LIMITS.md`)

> **Transparencia técnica y prudencia legal:** Tapaito es una herramienta técnica de código abierto diseñada para **reducir la exposición de datos personales** cuando profesionales de la salud o equipos pequeños interactúan con proveedores de IA en la nube. Antes de utilizarla en cualquier flujo de trabajo, lea cuidadosamente sus alcances y limitaciones.

---

## 1. Qué NO Garantiza Tapaito

1. **No es un sistema de desidentificación irreversible:**
   Tapaito opera mediante **enmascarado reversible por sesión (seudonimización temporal en memoria)** con marcadores como `⟦PERSONA_1⟧` o `⟦CEDULA_1⟧` para poder restaurar los valores en la respuesta. No transforma estadísticamente el documento ni elimina de forma permanente el vínculo con el titular del dato.
2. **No constituye asesoría jurídica ni certifica marcos regulatorios:**
   El uso de Tapaito **no** sustituye una evaluación de impacto de privacidad, **no** reemplaza el consentimiento informado del titular ni las políticas de tratamiento de datos exigidas por la normativa colombiana (Ley 1581 de 2012, Decreto 1377 de 2013 o resoluciones del Ministerio de Salud). Ninguna herramienta de software por sí sola otorga certificación legal automática.
3. **Ningún detector automático es infalible (Riesgo de Falsos Negativos):**
   Aunque Tapaito combina tres capas (expresiones regulares con validadores colombianos como el dígito de verificación de la DIAN, reconocimiento de entidades nombradas con spaCy y un verificador local con Qwen3 4B vía Ollama), **pueden existir fugas residuales**, especialmente ante:
   - Nombres propios poco frecuentes escritos en minúsculas, con errores tipográficos severos o partidos por saltos de línea arbitrarios.
   - Cédulas de ciudadanía de 6 a 10 dígitos escritas sin puntos separadores y sin ninguna palabra clave cercana (`CC`, `cédula`, `documento`, `identificación`), dado que la cédula colombiana no posee un dígito de verificación matemático público.
   - Direcciones rurales no estandarizadas (referencias informales a veredas o linderos sin nomenclatura vial).
4. **Riesgo de Re-identificación por Contexto Clínico (Cuasi-identificadores — R6):**
   Incluso cuando se enmascaran el nombre, la cédula y el teléfono, la combinación de atributos clínicos o demográficos poco comunes (por ejemplo, *"paciente que ejerce como único juez promiscuo municipal de Puerto Carreño con diagnóstico raro..."*) puede permitir deducir la identidad de la persona.
   - En modo `estricto`, el verificador local Qwen3 emite **advertencias (`warnings`)** cuando detecta posibles cuasi-identificadores, pero **no los enmascara ni reescribe el relato clínico**, dejando la decisión bajo criterio del profesional humano.
5. **Alcance exclusivo a texto plano en español (Vertical Clínico Colombiano):**
   - Este MVP procesa únicamente cadenas de texto en español en el endpoint `POST /v1/chat/completions` (sin streaming).
   - **No** procesa imágenes médicas (DICOM, radiografías), audio, archivos PDF/DOCX binarios ni adjuntos multimodales.
6. **Falsos Positivos y Utilidad Clínica (R8):**
   A pesar de contar con una lista de exclusión clínica (`MEDICAL_STOPLIST` para medicamentos POS/PBS, epónimos como Glasgow/Babinski y códigos CUPS/CIE-10), el modelo NER puede ocasionalmente etiquetar como `PERSONA` o `UBICACION` algún epónimo médico poco común o nombre de procedimiento no incluido en el filtro.

---

## 2. Recomendaciones de Uso Responsable

- **Revise siempre antes de enviar:** Utilice la vista previa (`/ui` o `POST /v1/tapaito/preview`) para inspeccionar visualmente qué entidades fueron enmascaradas y qué advertencias de cuasi-identificadores se generaron.
- **Prefiera el Modo `estricto` para textos libres:** En notas de evolución o relatos abiertos, utilice `X-Tapaito-Mode: estricto` para activar la auditoría local con Qwen3 4B y la política de **fallar cerrado** (bloqueo HTTP 422 ante duda o error del verificador).
- **Limpie la sesión al terminar cada caso:** Invoque `DELETE /v1/tapaito/session/{session_id}` (o el botón correspondiente en `/ui`) al cambiar de paciente para purgar inmediatamente el mapa en memoria RAM.
