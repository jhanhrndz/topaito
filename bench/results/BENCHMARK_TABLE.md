# Benchmark PII-CO — Resultados en `test` (50 casos)

- **Casos totales:** 50 (Casos difíciles: 25 / 50.0%)
- **Casos con cuasi-identificador (R6):** 6
- **Criterio CE2 (Recall estructurados en Modo Rápido ≥ 0.95):** **1.0000** (CUMPLIDO)
- **Criterio CE3 (Recuperación residual de Qwen3 en Modo Estricto):** Fugas residuales bajan de **4.32%** (12 fugas) a **0.00%** (0 fugas) — **18** entidades residuales recuperadas por Capa 3

## 1. Resumen Comparativo por Configuración (Nivel Solape / Entidad)

| Configuración | Precisión | Recall Global | F1 Global | Recall Estructurados (CE2) | Fugas Residuales (%) | Fugas (#) | Latencia p50 (ms) | Latencia p95 (ms) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **Config A** (`regex_only`) | 1.0000 | 0.6115 | 0.7589 | 1.0000 | 38.85% | 108/278 | 0.86 | 1.52 |
| **Config B** (`rapido_regex_ner`) | 0.9888 | 0.9496 | 0.9688 | 1.0000 | 4.32% | 12/278 | 12.23 | 19.23 |
| **Config C** (`estricto_qwen`) | 0.9684 | 0.9928 | 0.9805 | 1.0000 | 0.00% | 0/278 | 3893.86 | 7963.12 |

## 2. Resumen Comparativo por Configuración (Coincidencia Exacta de Span)

| Configuración | Precisión Exacta | Recall Exacto | F1 Exacto | Recall Estructurados Exacto |
|---|---:|---:|---:|---:|
| **Config A** (`regex_only`) | 1.0000 | 0.6115 | 0.7589 | 1.0000 |
| **Config B** (`rapido_regex_ner`) | 0.9888 | 0.9496 | 0.9688 | 1.0000 |
| **Config C** (`estricto_qwen`) | 0.9684 | 0.9928 | 0.9805 | 1.0000 |

## 3. Desglose por Tipo de Entidad (Solape y Fugas Residuales)

| Tipo de Entidad | Gold (#) | Recall A | Recall B (Rápido) | Recall C (Estricto) | Precisión B | F1 B | Fugas A (%) | Fugas B (%) | Fugas C (%) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `CEDULA` | 40 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0% | 0.0% | 0.0% |
| `NIT` | 30 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0% | 0.0% | 0.0% |
| `CELULAR` | 30 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0% | 0.0% | 0.0% |
| `CORREO` | 20 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0% | 0.0% | 0.0% |
| `RADICADO` | 10 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0% | 0.0% | 0.0% |
| `PERSONA` | 72 | 0.0000 | 0.8333 | 1.0000 | 0.9836 | 0.9023 | 100.0% | 16.7% | 0.0% |
| `DIRECCION` | 20 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0% | 0.0% | 0.0% |
| `UBICACION` | 16 | 0.0000 | 0.9375 | 0.9375 | 0.8824 | 0.9091 | 100.0% | 0.0% | 0.0% |
| `ORGANIZACION` | 20 | 0.0000 | 0.9500 | 0.9500 | 1.0000 | 0.9744 | 100.0% | 0.0% | 0.0% |
| `FECHA_NAC` | 10 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0% | 0.0% | 0.0% |
| `CUENTA` | 10 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0% | 0.0% | 0.0% |
