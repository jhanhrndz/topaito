# Benchmark PII-CO — Resultados en `dev` (30 casos)

- **Casos totales:** 30 (Casos difíciles: 15 / 50.0%)
- **Casos con cuasi-identificador (R6):** 4
- **Criterio CE2 (Recall estructurados en Modo Rápido ≥ 0.95):** **1.0000** (CUMPLIDO)
- **Criterio CE3 (Recuperación residual de Qwen3 en Modo Estricto):** Fugas residuales bajan de **4.19%** (7 fugas) a **0.00%** (0 fugas) — **7** entidades residuales recuperadas por Capa 3

## 1. Resumen Comparativo por Configuración (Nivel Solape / Entidad)

| Configuración | Precisión | Recall Global | F1 Global | Recall Estructurados (CE2) | Fugas Residuales (%) | Fugas (#) | Latencia p50 (ms) | Latencia p95 (ms) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **Config A** (`regex_only`) | 1.0000 | 0.6108 | 0.7584 | 1.0000 | 38.92% | 65/167 | 0.89 | 1.63 |
| **Config B** (`rapido_regex_ner`) | 0.6797 | 0.9401 | 0.7889 | 1.0000 | 4.19% | 7/167 | 12.04 | 19.29 |
| **Config C** (`estricto_qwen`) | 0.6891 | 0.9820 | 0.8099 | 1.0000 | 0.00% | 0/167 | 3051.21 | 7786.90 |

## 2. Resumen Comparativo por Configuración (Coincidencia Exacta de Span)

| Configuración | Precisión Exacta | Recall Exacto | F1 Exacto | Recall Estructurados Exacto |
|---|---:|---:|---:|---:|
| **Config A** (`regex_only`) | 1.0000 | 0.6108 | 0.7584 | 1.0000 |
| **Config B** (`rapido_regex_ner`) | 0.6797 | 0.9401 | 0.7889 | 1.0000 |
| **Config C** (`estricto_qwen`) | 0.6891 | 0.9820 | 0.8099 | 1.0000 |

## 3. Desglose por Tipo de Entidad (Solape y Fugas Residuales)

| Tipo de Entidad | Gold (#) | Recall A | Recall B (Rápido) | Recall C (Estricto) | Precisión B | F1 B | Fugas A (%) | Fugas B (%) | Fugas C (%) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `CEDULA` | 24 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0% | 0.0% | 0.0% |
| `NIT` | 18 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0% | 0.0% | 0.0% |
| `CELULAR` | 18 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0% | 0.0% | 0.0% |
| `CORREO` | 12 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0% | 0.0% | 0.0% |
| `RADICADO` | 6 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0% | 0.0% | 0.0% |
| `PERSONA` | 43 | 0.0000 | 0.8372 | 1.0000 | 0.6316 | 0.7200 | 100.0% | 16.3% | 0.0% |
| `DIRECCION` | 12 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0% | 0.0% | 0.0% |
| `UBICACION` | 10 | 0.0000 | 0.9000 | 0.9000 | 0.3214 | 0.4737 | 100.0% | 0.0% | 0.0% |
| `ORGANIZACION` | 12 | 0.0000 | 0.8333 | 0.8333 | 0.2273 | 0.3571 | 100.0% | 0.0% | 0.0% |
| `FECHA_NAC` | 6 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0% | 0.0% | 0.0% |
| `CUENTA` | 6 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0% | 0.0% | 0.0% |
