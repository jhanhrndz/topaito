# Guion Oficial de Demostración en Vivo y Offline (90 Segundos)

> **Propósito:** Este documento contiene el guion cronometrado de **90 segundos** (dividido en 6 bloques cronometrados), las acciones exactas sobre la interfaz `/ui` (**Estación de Auditoría Clínica Colombiana**), los textos clínicos sintéticos de respaldo y el procedimiento para ejecutar la demostración **100 % sin conexión a internet** (CE8).

---

## 1. Preparación Rápida Antes de Salir a Escena (100 % Offline — CE8)

Tapaito incluye un servidor upstream determinista (`TAPAITO_UPSTREAM_BASE_URL=mock` por defecto) que permite demostrar el ciclo completo sin depender de Wi-Fi ni de claves de API externas.

```powershell
# 1. Precalentar el verificador local Qwen3 4B en Ollama (opcional si se usa el Modo Estricto en vivo)
ollama run qwen3:4b "ok"

# 2. Levantar la estación local Tapaito en 127.0.0.1:8000
.\.venv\Scripts\uvicorn tapaito.api.app:app --host 127.0.0.1 --port 8000

# 3. Abrir en el navegador:
#    http://127.0.0.1:8000/ui
```

- **Respaldo de consola (sin navegador):** Si deseas ejecutar la misma secuencia de 90 segundos directamente en terminal, ejecuta:
  ```powershell
  .\.venv\Scripts\python scripts/run_demo_offline.py
  ```

---

## 2. Guion Cronometrado de 90 Segundos (6 Bloques Exactos)

### Bloque 1 (`0–10 s`) — El Problema Real en Consultorios y Hospitales
- **Acción en pantalla:** Mostrar la cabecera de `http://127.0.0.1:8000/ui` con el banner superior de alcance responsable y las 3 columnas listas.
- **Qué decir en voz alta:**
  > *"Hoy los médicos y abogados de salud en Colombia ya pegan epicrisis y tutelas en chatbots de IA para resumirlas. Con cada copia salen cédulas, NIT de aseguradoras, celulares, radicados judiciales de 23 dígitos y nombres de pacientes hacia servidores externos. Tapaito es un proxy local compatible con OpenAI que intercepta ese tráfico en `127.0.0.1`."*

---

### Bloque 2 (`10–30 s`) — Enmascarado Colombiano sin Destruir la Utilidad Médica (Modo Rápido)
- **Acción en la UI:**
  1. Hacer clic en el botón **`Caso 1 — Epicrisis Clínica Completa`** (Modo Rápido seleccionado automáticamente).
  2. Hacer clic en **`1. Previsualizar Enmascarado (/preview)`** (o directamente en **`2. Enviar a IA y Reinsertar`**).
- **Qué señalar en pantalla:**
  - En la **Columna 1 (Equipo Médico Local)**: mostrar los spans resaltados por offset (`start..end`) para `Juan Carlos Restrepo Gómez` (`PERSONA` / `ner`), `1.032.456.789` (`CEDULA` / `regex`), `800.251.440-6` (`NIT` validado con dígito de verificación módulo 11 de la DIAN), `+57 314 567 8901` (`CELULAR`) y `Calle 45 # 12-34 Apto 301` (`DIRECCION`).
  - Señalar que **`CIE-10 J189`**, **`CUPS 890201`**, **`Losartán 50 mg`** y **`Acetaminofén 500 mg`** quedaron intactos.
  - En la **Columna 2 (Lo que Recibe la Nube)**: mostrar cómo el proveedor externo solo recibe píldoras `⟦PERSONA_1⟧`, `⟦CEDULA_1⟧`, `⟦NIT_1⟧`.
- **Qué decir en voz alta:**
  > *"Pegamos una epicrisis sintética. A la izquierda vemos qué detecta cada capa en unos 15 milisegundos: validamos el dígito de verificación DIAN del NIT y protegemos cédula, celular y dirección, pero conservamos intactos códigos CIE-10, CUPS y dosis de Losartán para no degradar la calidad clínica. En la columna central vemos lo único que sale a la nube: tokens `⟦TIPO_N⟧`."*

---

### Bloque 3 (`30–50 s`) — Reinserción Tolerante e Informe Explícito
- **Acción en la UI:**
  1. Observar la **Columna 3 (Respuesta Reinsertada)** tras pulsar **`2. Enviar a IA y Reinsertar`**.
  2. Hacer clic en **`Caso 3 — Mutación Hostil del LLM`** y pulsar **`2. Enviar a IA y Reinsertar`** para demostrar cómo Tapaito recupera tokens incluso si el modelo externo los devuelve en minúsculas o con corchetes alterados (`[persona_1]`, `⟦ cedula_1 ⟧`, `((ORGANIZACION_1))`).
- **Qué decir en voz alta:**
  > *"Cuando el modelo responde, Tapaito reinserta localmente los valores desde la memoria RAM de la sesión y entrega un informe explícito: vemos el 100 % de tasa de restauración, incluso si el LLM externo altera mayúsculas o corchetes. Si el modelo inventara un token, jamás se adivina: se reporta en el informe."*

---

### Bloque 4 (`50–70 s`) — Momento Fuerte: Verificador Local Qwen3 4B y Política "Fallar Cerrado" (HTTP 422)
- **Acción en la UI:**
  1. Hacer clic en **`Caso 2 — Tutela + Residuo + Cuasi-ID`** (activa **Modo Estricto** con `qwen3:4b` local en Ollama) y pulsar **`2. Enviar a IA y Reinsertar`**.
     - Señalar en la Columna 1 que el contacto en minúsculas sin etiqueta estándar (`"luz marina betancur"`) fue atrapado por la **Capa 3 (`llm`)** y que aparece el **Banner Ámbar de Advertencia** por el cuasi-identificador (`"único juez promiscuo municipal de Puerto Carreño"`).
  2. Hacer clic en **`Caso 4 — Bloqueo Fallar Cerrado (422)`** y pulsar **`2. Enviar a IA y Reinsertar`**.
     - Señalar el **Escudo Rojo (`HTTP 422 · TAPAITO_RESIDUO`)** en la Columna 2: *"ENVÍO BLOQUEADO — FALLAR CERRADO: Ningún dato salió a la nube"*.
- **Qué decir en voz alta:**
  > *"¿Qué pasa cuando las expresiones regulares y spaCy fallan porque alguien escribió un nombre en minúsculas sin etiqueta o un cargo único en un municipio pequeño? En Modo Estricto, Qwen3 4B corriendo localmente en 4 GB de VRAM audita el texto ya enmascarado, reenmascara el residuo y emite una advertencia ámbar sobre el cuasi-identificador. Y si un residuo persiste o el verificador falla, la política es fallar cerrado con HTTP 422: cero bytes salen a la nube."*

---

### Bloque 5 (`70–85 s`) — Benchmark PII-CO y Auditoría Sin Valores Originales (CE6)
- **Acción en la UI:**
  1. Desplazar ligeramente hacia el **Panel Inferior de Auditoría Local (`GET /v1/tapaito/audit`)**.
  2. Señalar las columnas `counts_by_type`, `spans` (solo coordenadas `[start..end]`) y `result` (`enviado` / `bloqueado`), junto a la insignia **GARANTÍA CE6: CERO VALORES ORIGINALES ALMACENADOS**.
- **Qué decir en voz alta:**
  > *"En nuestro benchmark sintético PII-CO sobre el conjunto de prueba congelado, alcanzamos 100 % de recall en identificadores estructurados colombianos y reducimos las fugas residuales de 4.32 % a 0.00 % al activar Qwen3 local. Además, el log de auditoría registra conteos, offsets y latencias, pero jamás almacena un solo valor original."*

---

### Bloque 6 (`85–90 s`) — Cierre Honesto e Integración en 1 Línea
- **Acción en la UI:** Hacer clic en **`Borrar Sesión en Memoria (DELETE)`** para limpiar el mapa en RAM.
- **Qué decir en voz alta:**
  > *"Tapaito reduce la exposición de datos personales hacia la nube sin reemplazar el criterio médico ni una revisión legal. Funciona hoy mismo: en cualquier cliente OpenAI solo cambias `base_url` a `http://127.0.0.1:8000/v1` y listo."*

---

## 3. Textos Sintéticos de Respaldo para Copiar y Pegar

 Todos los datos siguientes son **100 % sintéticos y ficticios** (RNF8).

### Caso 1 — Epicrisis Clínica Completa (Modo Rápido)
```text
EPICRISIS MEDICINA INTERNA: El paciente Juan Carlos Restrepo Gómez, identificado con CC 1.032.456.789, afiliado a EPS Sanitas (NIT 800.251.440-6), teléfono móvil +57 314 567 8901, correo jrestrepo.demo@pacientes.co y domicilio en Calle 45 # 12-34 Apto 301 en Bogotá, consulta por cuadro respiratorio agudo de 58 años. Diagnóstico principal CIE-10 J189, interconsulta CUPS 890201. Plan ambulatorio: continuar Losartán 50 mg cada 12 horas y Acetaminofén 500 mg según dolor.
```

### Caso 2 — Tutela en Salud + Residuo Sutil + Cuasi-identificador (Modo Estricto)
```text
ACCIÓN DE TUTELA EN SALUD: Dentro del expediente con radicado 11001-31-03-001-2024-00123-00, el accionante con CC 79.456.123 solicita autorización prioritaria de procedimiento CIE-10 I10. Nota administrativa de admisión: en caso de urgencia avisar en portería a luz marina betancur. Observación social: el paciente ejerce como único juez promiscuo municipal de Puerto Carreño.
```

### Caso 3 — Prueba de Mutación Hostil del LLM (`X-Tapaito-Mock-Hostile: case_and_brackets`)
```text
VALORACIÓN PRIORITARIA: Paciente Juan Carlos Restrepo Gómez con CC 1.032.456.789 remitido por EPS Sanitas con NIT 800.251.440-6 desde Bogotá. Presenta diagnóstico CIE-10 J189 y recibe manejo con Losartán 50 mg y Acetaminofén 500 mg.
```

### Caso 4 — Bloqueo por Política "Fallar Cerrado" (`HTTP 422 · TAPAITO_RESIDUO`)
```text
SOLICITUD DE AUDITORÍA ESTRICTA: Paciente atendido en urgencias con CC 79.456.123 y NIT aseguradora 800.251.440-6. Observación de admisión con múltiples contactos residuales no estructurados: entregar copia en recepción a luz marina betancur o al acompañante carlos alberto ruiz.
```
