# Benchmark PII-CO — Resultados en `dev` (30 casos)

- **Casos totales:** 30 (Casos difíciles: 15 / 50.0%)
- **Casos con cuasi-identificador (R6):** 4
- **Criterio CE2 (Recall estructurados en Modo Rápido ≥ 0.95):** **1.0000** (CUMPLIDO)
- **Criterio CE3 (Recuperación residual de Qwen3 en Modo Estricto):** Fugas residuales bajan de **4.19%** (7 fugas) a **0.00%** (0 fugas) — **11** entidades residuales recuperadas por Capa 3

## 1. Resumen Comparativo por Configuración (Nivel Solape / Entidad)

| Configuración | Precisión | Recall Global | F1 Global | Recall Estructurados (CE2) | Fugas Residuales (%) | Fugas (#) | Latencia p50 (ms) | Latencia p95 (ms) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **Config A** (`regex_only`) | 1.0000 | 0.6108 | 0.7584 | 1.0000 | 38.92% | 65/167 | 0.82 | 1.38 |
| **Config B** (`rapido_regex_ner`) | 0.9812 | 0.9401 | 0.9602 | 1.0000 | 4.19% | 7/167 | 12.24 | 18.17 |
| **Config C** (`estricto_qwen`) | 0.9591 | 0.9820 | 0.9704 | 1.0000 | 0.00% | 0/167 | 4241.89 | 7309.37 |

## 2. Resumen Comparativo por Configuración (Coincidencia Exacta de Span)

| Configuración | Precisión Exacta | Recall Exacto | F1 Exacto | Recall Estructurados Exacto |
|---|---:|---:|---:|---:|
| **Config A** (`regex_only`) | 1.0000 | 0.6108 | 0.7584 | 1.0000 |
| **Config B** (`rapido_regex_ner`) | 0.9812 | 0.9401 | 0.9602 | 1.0000 |
| **Config C** (`estricto_qwen`) | 0.9591 | 0.9820 | 0.9704 | 1.0000 |

## 3. Desglose por Tipo de Entidad (Solape y Fugas Residuales)

| Tipo de Entidad | Gold (#) | Recall A | Recall B (Rápido) | Recall C (Estricto) | Precisión B | F1 B | Fugas A (%) | Fugas B (%) | Fugas C (%) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `CEDULA` | 24 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0% | 0.0% | 0.0% |
| `NIT` | 18 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0% | 0.0% | 0.0% |
| `CELULAR` | 18 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0% | 0.0% | 0.0% |
| `CORREO` | 12 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0% | 0.0% | 0.0% |
| `RADICADO` | 6 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0% | 0.0% | 0.0% |
| `PERSONA` | 43 | 0.0000 | 0.8372 | 1.0000 | 0.9730 | 0.9000 | 100.0% | 16.3% | 0.0% |
| `DIRECCION` | 12 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0% | 0.0% | 0.0% |
| `UBICACION` | 10 | 0.0000 | 0.9000 | 0.9000 | 0.8182 | 0.8571 | 100.0% | 0.0% | 0.0% |
| `ORGANIZACION` | 12 | 0.0000 | 0.8333 | 0.8333 | 1.0000 | 0.9091 | 100.0% | 0.0% | 0.0% |
| `FECHA_NAC` | 6 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0% | 0.0% | 0.0% |
| `CUENTA` | 6 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0% | 0.0% | 0.0% |
