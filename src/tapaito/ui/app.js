/**
 * Tapaito UI — Estación de Auditoría Clínica Colombiana
 * Cliente Vanilla JS 100 % Offline (Sin dependencias externas — CE8)
 *
 * Conecta con:
 * - POST /v1/tapaito/preview
 * - POST /v1/chat/completions
 * - GET  /v1/tapaito/audit?limit=20
 * - DELETE /v1/tapaito/session/{session_id}
 * - GET  /healthz
 */

(() => {
  "use strict";

  // =========================================================================
  // 1. Casos Clínicos Sintéticos Precargados (100 % Ficticios — RNF8)
  // =========================================================================
  const PRESET_CASES = {
    case1: {
      id: "case1",
      title: "Caso 1 — Epicrisis Clínica Completa (Modo Rápido)",
      mode: "rapido",
      sessionId: "sess-epicrisis-01",
      hostileMode: "",
      force422: false,
      text:
        "EPICRISIS MEDICINA INTERNA: El paciente Juan Carlos Restrepo Gómez, identificado con CC 1.032.456.789, afiliado a EPS Sanitas (NIT 800.251.440-6), teléfono móvil +57 314 567 8901, correo jrestrepo.demo@pacientes.co y domicilio en Calle 45 # 12-34 Apto 301 en Bogotá, consulta por cuadro respiratorio agudo de 58 años. Diagnóstico principal CIE-10 J189, interconsulta CUPS 890201. Plan ambulatorio: continuar Losartán 50 mg cada 12 horas y Acetaminofén 500 mg según dolor.",
    },
    case2: {
      id: "case2",
      title: "Caso 2 — Tutela en Salud + Residuo Sutil + Cuasi-identificador (Modo Estricto)",
      mode: "estricto",
      sessionId: "sess-tutela-02",
      hostileMode: "",
      force422: false,
      text:
        "ACCIÓN DE TUTELA EN SALUD: Dentro del expediente con radicado 11001-31-03-001-2024-00123-00, el accionante con CC 79.456.123 solicita autorización prioritaria de procedimiento CIE-10 I10. Nota administrativa de admisión: en caso de urgencia avisar en portería a luz marina betancur. Observación social: el paciente ejerce como único juez promiscuo municipal de Puerto Carreño.",
    },
    case3: {
      id: "case3",
      title: "Caso 3 — Mutación Hostil del LLM + Informe de Reinserción Tolerante",
      mode: "rapido",
      sessionId: "sess-hostil-03",
      hostileMode: "case_and_brackets",
      force422: false,
      text:
        "VALORACIÓN PRIORITARIA: Paciente Juan Carlos Restrepo Gómez con CC 1.032.456.789 remitido por EPS Sanitas con NIT 800.251.440-6 desde Bogotá. Presenta diagnóstico CIE-10 J189 y recibe manejo con Losartán 50 mg y Acetaminofén 500 mg.",
    },
    case4: {
      id: "case4",
      title: "Caso 4 — Bloqueo por Política Fallar Cerrado HTTP 422 (Modo Estricto)",
      mode: "estricto",
      sessionId: "sess-bloqueo-04",
      hostileMode: "",
      force422: true,
      text:
        "SOLICITUD DE AUDITORÍA ESTRICTA: Paciente atendido en urgencias con CC 79.456.123 y NIT aseguradora 800.251.440-6. Observación de admisión con múltiples contactos residuales no estructurados: entregar copia en recepción a luz marina betancur o al acompañante carlos alberto ruiz.",
    },
  };

  // Estado reactivo local de la estación
  const state = {
    activeCase: "case1",
    mode: "rapido",
    tokenToOriginalValue: {},
    localAuditFallback: [],
  };

  // =========================================================================
  // 2. Referencias al DOM
  // =========================================================================
  const dom = {
    healthPill: document.getElementById("health-pill"),
    sessionInput: document.getElementById("session-id-input"),
    btnDeleteSession: document.getElementById("btn-delete-session"),

    presetButtons: document.querySelectorAll(".preset-btn"),
    modeRapidoBtn: document.getElementById("mode-rapido-btn"),
    modeEstrictoBtn: document.getElementById("mode-estricto-btn"),
    hostileSelect: document.getElementById("hostile-select"),
    toggleForce422: document.getElementById("toggle-force-422"),
    toggleOfflineSim: document.getElementById("toggle-offline-sim"),

    btnPreview: document.getElementById("btn-preview"),
    btnSendChat: document.getElementById("btn-send-chat"),

    statusBar: document.getElementById("status-bar"),
    statusIndicator: document.getElementById("status-indicator"),
    statusMessage: document.getElementById("status-message"),

    clinicalInput: document.getElementById("clinical-input"),
    charCounter: document.getElementById("char-counter"),
    entityCountBadge: document.getElementById("entity-count-badge"),
    highlightedOriginal: document.getElementById("highlighted-original"),
    entitySpansList: document.getElementById("entity-spans-list"),
    warningsContainer: document.getElementById("warnings-container"),
    warningsList: document.getElementById("warnings-list"),

    cloudStatusTag: document.getElementById("cloud-status-tag"),
    blockShield: document.getElementById("block-shield"),
    shieldCode: document.getElementById("shield-code"),
    shieldMessage: document.getElementById("shield-message"),
    maskedTokenCount: document.getElementById("masked-token-count"),
    maskedOutput: document.getElementById("masked-output"),
    upstreamModelBadge: document.getElementById("upstream-model-badge"),
    rawUpstreamOutput: document.getElementById("raw-upstream-output"),

    restorationRateBadge: document.getElementById("restoration-rate-badge"),
    restoredOutput: document.getElementById("restored-output"),
    reportSummaryLabel: document.getElementById("report-summary-label"),
    countRestaurados: document.getElementById("count-restaurados"),
    countFaltantes: document.getElementById("count-faltantes"),
    countDesconocidos: document.getElementById("count-desconocidos"),
    countAmbiguos: document.getElementById("count-ambiguos"),
    chipsRestaurados: document.getElementById("chips-restaurados"),
    chipsFaltantes: document.getElementById("chips-faltantes"),
    chipsDesconocidos: document.getElementById("chips-desconocidos"),
    chipsAmbiguos: document.getElementById("chips-ambiguos"),

    latTotalBadge: document.getElementById("lat-total-badge"),
    latL12: document.getElementById("lat-l12"),
    latL3: document.getElementById("lat-l3"),
    latUpstream: document.getElementById("lat-upstream"),
    latTotal: document.getElementById("lat-total"),

    btnRefreshAudit: document.getElementById("btn-refresh-audit"),
    auditTableBody: document.getElementById("audit-table-body"),
  };

  // =========================================================================
  // 3. Utilidades de Sanitización HTML y Formateo Seguro
  // =========================================================================
  function escapeHtml(raw) {
    return String(raw ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function escapeRegExp(str) {
    return String(str).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  }

  function setStatus(kind, message) {
    dom.statusIndicator.className = `status-dot status-${kind}`;
    dom.statusMessage.textContent = message;
  }

  function updateCharCounter() {
    const len = dom.clinicalInput.value.length;
    dom.charCounter.textContent = `${len} caracteres`;
  }

  // =========================================================================
  // 4. Renderizado de Columna 1: Offsets Exactos (start..end) y Advertencias
  // =========================================================================
  function renderOriginalWithHighlights(originalText, entities) {
    state.tokenToOriginalValue = {};

    if (!originalText) {
      dom.highlightedOriginal.innerHTML =
        '<span class="empty-hint">No hay texto para analizar.</span>';
      dom.entitySpansList.innerHTML = "";
      dom.entityCountBadge.textContent = "0 entidades";
      return;
    }

    const sorted = Array.isArray(entities)
      ? [...entities].sort((a, b) => a.start - b.start || a.end - b.end)
      : [];

    dom.entityCountBadge.textContent = `${sorted.length} entidad${sorted.length === 1 ? "" : "es"}`;

    if (sorted.length === 0) {
      dom.highlightedOriginal.innerHTML = escapeHtml(originalText);
      dom.entitySpansList.innerHTML =
        '<span class="empty-hint">Ningún identificador sensible detectado en este fragmento.</span>';
      return;
    }

    let cursor = 0;
    const htmlParts = [];
    const chipParts = [];

    for (const ent of sorted) {
      const start = Math.max(0, Number(ent.start) || 0);
      const end = Math.min(originalText.length, Number(ent.end) || 0);
      if (start < cursor || end <= start) {
        continue;
      }

      if (start > cursor) {
        htmlParts.push(escapeHtml(originalText.slice(cursor, start)));
      }

      const rawSlice = originalText.slice(start, end);
      const etype = escapeHtml(ent.entity_type || "RESIDUO");
      const source = escapeHtml(ent.source || "regex");
      const token = escapeHtml(ent.token || "");

      if (ent.token && rawSlice) {
        state.tokenToOriginalValue[ent.token] = rawSlice;
      }

      htmlParts.push(
        `<mark class="entity-mark etype-${etype}" title="Token: ${token} | Capa: ${source} | Offsets: ${start}..${end}">` +
          `${escapeHtml(rawSlice)}` +
          `<span class="entity-mark-meta">${token} · ${source}</span>` +
        `</mark>`
      );

      chipParts.push(
        `<span class="span-chip">` +
          `<kbd class="source-tag source-${source}">${source}</kbd>` +
          `<strong>${etype}</strong>` +
          `<span>[${start}..${end}]</span>` +
          `<code>${token}</code>` +
        `</span>`
      );

      cursor = end;
    }

    if (cursor < originalText.length) {
      htmlParts.push(escapeHtml(originalText.slice(cursor)));
    }

    dom.highlightedOriginal.innerHTML = htmlParts.join("");
    dom.entitySpansList.innerHTML = chipParts.join("");
  }

  function renderWarnings(warnings) {
    const list = Array.isArray(warnings) ? warnings.filter(Boolean) : [];
    if (list.length === 0) {
      dom.warningsContainer.classList.add("hidden");
      dom.warningsList.innerHTML = "";
      return;
    }
    dom.warningsContainer.classList.remove("hidden");
    dom.warningsList.innerHTML = list
      .map((w) => `<li>${escapeHtml(w)}</li>`)
      .join("");
  }

  // =========================================================================
  // 5. Renderizado de Columna 2: Texto Enmascarado + Escudo de Bloqueo HTTP 422
  // =========================================================================
  function formatTextWithTokenPills(text) {
    if (!text) {
      return '<span class="empty-hint">Sin contenido.</span>';
    }
    const safe = escapeHtml(text);
    // Resaltar tokens canónicos ⟦TIPO_N⟧ y mutaciones hostiles como [persona_1], ((ORG_1)), ⟦ cedula_1 ⟧
    return safe
      .replace(/⟦\s*[A-Za-z_]+_\d+\s*⟧/g, (match) => {
        const isCanonical = /^⟦[A-Z_]+_\d+⟧$/.test(match);
        const cls = isCanonical ? "token-pill" : "token-pill token-pill-hostile";
        return `<span class="${cls}">${match}</span>`;
      })
      .replace(/(\[\s*[a-zA-Z_]+_\d+\s*\]|\(\(\s*[a-zA-Z_]+_\d+\s*\)\)|\[PERSONA\])/g, (match) => {
        return `<span class="token-pill token-pill-hostile">${match}</span>`;
      });
  }

  function renderMaskedColumn(maskedText, rawUpstreamText) {
    dom.blockShield.classList.add("hidden");
    dom.cloudStatusTag.className = "panel-zone-tag zone-masked";
    dom.cloudStatusTag.textContent = "Solo Tokens ⟦TIPO_N⟧";

    const canonicalTokens = String(maskedText || "").match(/⟦[A-Z_]+_\d+⟧/g) || [];
    const uniqueTokens = Array.from(new Set(canonicalTokens));
    dom.maskedTokenCount.textContent = `${uniqueTokens.length} token${uniqueTokens.length === 1 ? "" : "s"}`;

    dom.maskedOutput.innerHTML = formatTextWithTokenPills(maskedText);

    if (rawUpstreamText !== null && rawUpstreamText !== undefined) {
      dom.rawUpstreamOutput.innerHTML = formatTextWithTokenPills(rawUpstreamText);
    }
  }

  function renderBlockedState(errorObj, warningsFallback = []) {
    const code = errorObj?.code || "TAPAITO_RESIDUO";
    const msg =
      errorObj?.message ||
      "Petición bloqueada en modo estricto: persisten posibles datos sensibles tras reenmascarado.";
    const warnings = errorObj?.warnings?.length ? errorObj.warnings : warningsFallback;

    dom.blockShield.classList.remove("hidden");
    dom.shieldCode.textContent = `HTTP 422 Unprocessable Entity · ${code}`;
    dom.shieldMessage.textContent = msg;

    dom.cloudStatusTag.className = "panel-zone-tag zone-blocked";
    dom.cloudStatusTag.textContent = "BLOQUEADO · HTTP 422";

    dom.maskedTokenCount.textContent = "ENVÍO CANCELADO";
    dom.maskedOutput.innerHTML =
      `<span class="empty-hint">[FALLAR CERRADO ACTIVO] El pipeline abortó la salida antes de contactar al proveedor externo (${escapeHtml(code)}).</span>`;
    dom.rawUpstreamOutput.innerHTML =
      '<span class="empty-hint">0 llamadas realizadas al upstream. Ningún byte salió de 127.0.0.1.</span>';

    dom.restorationRateBadge.className = "counter-pill rate-pill-warn";
    dom.restorationRateBadge.textContent = "Bloqueado (422)";
    dom.restoredOutput.innerHTML =
      `<span class="empty-hint">Petición retenida localmente por la política de modo estricto (${escapeHtml(code)}). Revise la nota clínica o las advertencias en la Columna 1.</span>`;
    dom.reportSummaryLabel.textContent = "No aplica (envío bloqueado)";

    renderWarnings(warnings);
  }

  // =========================================================================
  // 6. Renderizado de Columna 3: Respuesta Reinsertada + Informe + Latencias
  // =========================================================================
  function renderRestoredColumn(restoredText, reinsertionReport, latencyMs) {
    let html = escapeHtml(restoredText || "");

    // Resaltar en verde cada valor original restaurado (de mayor a menor longitud para evitar solapes)
    const restoredTokens = reinsertionReport?.restaurados || [];
    const valuesToHighlight = restoredTokens
      .map((tok) => ({
        token: tok,
        value: state.tokenToOriginalValue[tok],
      }))
      .filter((item) => item.value && item.value.length >= 2)
      .sort((a, b) => b.value.length - a.value.length);

    for (const item of valuesToHighlight) {
      const escapedVal = escapeHtml(item.value);
      const pattern = new RegExp(escapeRegExp(escapedVal), "g");
      html = html.replace(
        pattern,
        `<span class="restored-value-pill" title="Restaurado desde ${escapeHtml(item.token)}">${escapedVal}</span>`
      );
    }

    // Resaltar en rojo cualquier token desconocido o ambiguo que haya quedado literal en la respuesta
    const problemTokens = [
      ...(reinsertionReport?.desconocidos || []),
      ...(reinsertionReport?.ambiguos || []),
    ];
    for (const badTok of problemTokens) {
      const escapedBad = escapeHtml(badTok);
      const pattern = new RegExp(escapeRegExp(escapedBad), "g");
      html = html.replace(
        pattern,
        `<span class="unrestored-token-pill" title="Token no sustituido por seguridad">${escapedBad}</span>`
      );
    }

    dom.restoredOutput.innerHTML =
      html || '<span class="empty-hint">Sin respuesta reinsertada.</span>';

    // Actualizar contadores y chips del Informe de Reinserción
    const restaurados = reinsertionReport?.restaurados || [];
    const faltantes = reinsertionReport?.faltantes || [];
    const desconocidos = reinsertionReport?.desconocidos || [];
    const ambiguos = reinsertionReport?.ambiguos || [];
    const tasa =
      typeof reinsertionReport?.tasa_restauracion === "number"
        ? reinsertionReport.tasa_restauracion
        : 1.0;

    const pct = `${(tasa * 100).toFixed(0)}%`;
    dom.restorationRateBadge.textContent = `Tasa: ${pct}`;
    dom.restorationRateBadge.className =
      tasa >= 0.99 && desconocidos.length === 0 && ambiguos.length === 0
        ? "counter-pill rate-pill-ok"
        : "counter-pill rate-pill-warn";

    dom.reportSummaryLabel.textContent = `${restaurados.length} restaurados · ${faltantes.length} faltantes · ${desconocidos.length} desconocidos`;

    dom.countRestaurados.textContent = String(restaurados.length);
    dom.countFaltantes.textContent = String(faltantes.length);
    dom.countDesconocidos.textContent = String(desconocidos.length);
    dom.countAmbiguos.textContent = String(ambiguos.length);

    const renderChips = (arr) =>
      arr.length
        ? arr.map((t) => `<span class="report-chip">${escapeHtml(t)}</span>`).join("")
        : '<span class="empty-hint">Ninguno</span>';

    dom.chipsRestaurados.innerHTML = renderChips(restaurados);
    dom.chipsFaltantes.innerHTML = renderChips(faltantes);
    dom.chipsDesconocidos.innerHTML = renderChips(desconocidos);
    dom.chipsAmbiguos.innerHTML = renderChips(ambiguos);

    if (latencyMs) {
      renderLatency(latencyMs);
    }
  }

  function renderLatency(latencyMs) {
    const l12 = latencyMs?.layer1_2 ?? 0;
    const l3 = latencyMs?.layer3 ?? 0;
    const up = latencyMs?.upstream;
    const total = latencyMs?.total ?? 0;

    dom.latL12.textContent = `${Number(l12).toFixed(2)} ms`;
    dom.latL3.textContent = `${Number(l3).toFixed(2)} ms`;
    dom.latUpstream.textContent =
      up !== undefined && up !== null ? `${Number(up).toFixed(2)} ms` : "— (solo preview)";
    dom.latTotal.textContent = `${Number(total).toFixed(2)} ms`;
    dom.latTotalBadge.textContent = `Total: ${Number(total).toFixed(2)} ms`;
  }

  // =========================================================================
  // 7. Motor de Simulación Offline (Fallback Autónomo y Bloqueo Instantáneo 422)
  // =========================================================================
  function buildSimulatedPreview(text, mode, sessionId) {
    // Detectores ligeros en JS para el modo "Simular sin servidor"
    const patterns = [
      { type: "RADICADO", source: "regex", re: /\b\d{5}-\d{2}-\d{2}-\d{3}-\d{4}-\d{5}-\d{2}\b|\b\d{23}\b/g },
      { type: "NIT", source: "regex", re: /\b(?:8\d{2}|9\d{2})\.\d{3}\.\d{3}-\d\b/g },
      { type: "CEDULA", source: "regex", re: /\b\d{1,2}\.\d{3}\.\d{3}\b/g },
      { type: "CELULAR", source: "regex", re: /\+57\s*3\d{2}\s*\d{3}\s*\d{4}\b/g },
      { type: "CORREO", source: "regex", re: /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b/g },
      { type: "DIRECCION", source: "regex", re: /\b(?:Calle|Carrera|Diagonal|Transversal)\s+\d+\s*#\s*\d+-\d+(?:\s+Apto\s+\d+)?/gi },
      { type: "PERSONA", source: "ner", re: /\b(?:Juan Carlos Restrepo Gómez|Maria Fernanda Gomez)\b/g },
      { type: "ORGANIZACION", source: "ner", re: /\bEPS Sanitas\b/g },
      { type: "UBICACION", source: "ner", re: /\b(?:Bogotá|Puerto Carreño|Leticia)\b/g },
    ];

    if (mode === "estricto") {
      patterns.push({
        type: "PERSONA",
        source: "llm",
        re: /\b(?:luz marina betancur|carlos alberto ruiz)\b/gi,
      });
    }

    const rawSpans = [];
    for (const pat of patterns) {
      for (const m of text.matchAll(pat.re)) {
        rawSpans.push({
          start: m.index,
          end: m.index + m[0].length,
          entity_type: pat.type,
          source: pat.source,
          rawText: m[0],
        });
      }
    }

    rawSpans.sort((a, b) => a.start - b.start || (b.end - b.start) - (a.end - a.start));
    const merged = [];
    let lastEnd = -1;
    for (const sp of rawSpans) {
      if (sp.start >= lastEnd) {
        merged.push(sp);
        lastEnd = sp.end;
      }
    }

    const counters = {};
    const valueMap = {};
    const entities = merged.map((sp) => {
      const key = `${sp.entity_type}::${sp.rawText.toLowerCase()}`;
      if (!valueMap[key]) {
        counters[sp.entity_type] = (counters[sp.entity_type] || 0) + 1;
        valueMap[key] = `⟦${sp.entity_type}_${counters[sp.entity_type]}⟧`;
      }
      return {
        start: sp.start,
        end: sp.end,
        entity_type: sp.entity_type,
        token: valueMap[key],
        source: sp.source,
      };
    });

    let masked = "";
    let cursor = 0;
    for (const ent of entities) {
      masked += text.slice(cursor, ent.start) + ent.token;
      cursor = ent.end;
    }
    masked += text.slice(cursor);

    const warnings = [];
    if (/único\s+juez|único\s+neurocirujano/i.test(text)) {
      warnings.push(
        "Cuasi-identificador contextual detectado: cargo o condición única en municipio pequeño (riesgo de re-identificación indirecta)."
      );
    }

    const l12 = 12.4;
    const l3 = mode === "estricto" ? 418.6 : 0.0;
    return {
      original: text,
      masked,
      mode,
      session_id: sessionId,
      entities,
      warnings,
      latency_ms: {
        layer1_2: l12,
        layer3: l3,
        total: Number((l12 + l3).toFixed(2)),
      },
    };
  }

  function recordLocalSimulatedAudit(mode, sessionId, result, entities, latencyMs, errorCode = null) {
    const counts = {};
    const spans = [];
    for (const ent of entities || []) {
      counts[ent.entity_type] = (counts[ent.entity_type] || 0) + 1;
      spans.push({
        start: ent.start,
        end: ent.end,
        entity_type: ent.entity_type,
        source: ent.source,
      });
    }
    state.localAuditFallback.unshift({
      timestamp: new Date().toISOString(),
      request_id: `req_sim_${Math.random().toString(36).slice(2, 8)}`,
      session_id: sessionId,
      mode,
      result,
      error_code: errorCode,
      counts_by_type: counts,
      spans,
      latency_ms: latencyMs,
    });
  }

  // =========================================================================
  // 8. Acciones de API: /preview, /v1/chat/completions, /audit y DELETE session
  // =========================================================================
  async function runPreview() {
    const text = dom.clinicalInput.value;
    const mode = state.mode;
    const sessionId = dom.sessionInput.value.trim() || "sess-demo-1";
    const force422 = dom.toggleForce422.checked;
    const offlineSim = dom.toggleOfflineSim.checked;

    dom.btnPreview.disabled = true;
    dom.btnSendChat.disabled = true;
    setStatus("loading", `Ejecutando previsualización en modo ${mode.toUpperCase()}…`);

    try {
      // Si el presentador activó "Forzar simulación de bloqueo HTTP 422" en modo estricto
      if (force422) {
        const simPrev = buildSimulatedPreview(text, "estricto", sessionId);
        renderOriginalWithHighlights(text, simPrev.entities);
        const errPayload = {
          code: "TAPAITO_RESIDUO",
          message:
            "Petición bloqueada en modo estricto: persisten posibles datos sensibles tras 1 ciclo de reenmascarado (política Fallar Cerrado CE5).",
          mode: "estricto",
          warnings: [
            "Persiste segundo nombre propio sin formato estándar tras reenmascarado.",
          ],
        };
        renderBlockedState(errPayload, errPayload.warnings);
        renderLatency({ layer1_2: 13.1, layer3: 412.4, total: 425.5 });
        recordLocalSimulatedAudit("estricto", sessionId, "bloqueado", simPrev.entities, {
          layer1_2: 13.1,
          layer3: 412.4,
          total: 425.5,
        }, "TAPAITO_RESIDUO");
        setStatus("blocked", "Bloqueo HTTP 422 (TAPAITO_RESIDUO) activado por política Fallar Cerrado.");
        await refreshAuditLog();
        return;
      }

      if (offlineSim) {
        const data = buildSimulatedPreview(text, mode, sessionId);
        renderOriginalWithHighlights(data.original, data.entities);
        renderWarnings(data.warnings);
        renderMaskedColumn(data.masked, null);
        renderLatency(data.latency_ms);
        setStatus("ok", `Previsualización local simulada completada (${data.entities.length} entidades).`);
        return;
      }

      const resp = await fetch("/v1/tapaito/preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text,
          mode,
          session_id: sessionId,
        }),
      });

      const body = await resp.json();

      if (resp.status === 422) {
        renderBlockedState(body.error);
        setStatus("blocked", `Envío bloqueado con HTTP 422 (${body.error?.code || "TAPAITO_RESIDUO"}).`);
        await refreshAuditLog();
        return;
      }

      if (!resp.ok) {
        throw new Error(body?.error?.message || `HTTP ${resp.status}`);
      }

      renderOriginalWithHighlights(body.original, body.entities);
      renderWarnings(body.warnings);
      renderMaskedColumn(body.masked, null);
      renderLatency(body.latency_ms);
      setStatus(
        "ok",
        `Previsualización completada en ${body.latency_ms?.total ?? 0} ms (${body.entities?.length ?? 0} entidades enmascaradas).`
      );
      await refreshAuditLog();
    } catch (err) {
      setStatus("blocked", `Error al conectar con /v1/tapaito/preview: ${err.message}`);
    } finally {
      dom.btnPreview.disabled = false;
      dom.btnSendChat.disabled = false;
    }
  }

  async function runChatCompletion() {
    const text = dom.clinicalInput.value;
    const mode = state.mode;
    const sessionId = dom.sessionInput.value.trim() || "sess-demo-1";
    const hostileMode = dom.hostileSelect.value;
    const force422 = dom.toggleForce422.checked;
    const offlineSim = dom.toggleOfflineSim.checked;

    dom.btnPreview.disabled = true;
    dom.btnSendChat.disabled = true;
    setStatus(
      "loading",
      `Procesando flujo completo (/v1/chat/completions) en modo ${mode.toUpperCase()}…`
    );

    try {
      if (force422) {
        const simPrev = buildSimulatedPreview(text, "estricto", sessionId);
        renderOriginalWithHighlights(text, simPrev.entities);
        const errPayload = {
          code: "TAPAITO_RESIDUO",
          message:
            "Petición bloqueada en modo estricto: persisten posibles datos sensibles tras reenmascarado. Cero bytes enviados al proveedor.",
          mode: "estricto",
          warnings: [
            "Política Fallar Cerrado (CE5): residuo persistente detectado en segunda verificación.",
          ],
        };
        renderBlockedState(errPayload, errPayload.warnings);
        renderLatency({ layer1_2: 14.2, layer3: 430.8, upstream: 0.0, total: 445.0 });
        recordLocalSimulatedAudit("estricto", sessionId, "bloqueado", simPrev.entities, {
          layer1_2: 14.2,
          layer3: 430.8,
          total: 445.0,
        }, "TAPAITO_RESIDUO");
        setStatus(
          "blocked",
          "ENVÍO BLOQUEADO (HTTP 422 · TAPAITO_RESIDUO): Ningún dato salió a la nube."
        );
        await refreshAuditLog();
        return;
      }

      if (offlineSim) {
        const simPrev = buildSimulatedPreview(text, mode, sessionId);
        renderOriginalWithHighlights(simPrev.original, simPrev.entities);
        renderWarnings(simPrev.warnings);

        const uniqueTokens = Array.from(new Set(simPrev.entities.map((e) => e.token)));
        let rawUp = "";
        let restored = "";
        let report = {
          restaurados: uniqueTokens,
          faltantes: [],
          desconocidos: [],
          ambiguos: [],
          tasa_restauracion: 1.0,
        };

        if (hostileMode === "case_and_brackets") {
          const mutated = uniqueTokens.map((tok, i) => {
            const inner = tok.replace(/[⟦⟧]/g, "");
            if (i % 3 === 0) return `[${inner.toLowerCase()}]`;
            if (i % 3 === 1) return `⟦ ${inner.toLowerCase()} ⟧`;
            return `((${inner}))`;
          });
          rawUp = `Resumen clinico procesado: ${mutated.join(", ")}`;
          restored = `Resumen clinico procesado: ${uniqueTokens
            .map((t) => state.tokenToOriginalValue[t] || t)
            .join(", ")}`;
        } else if (hostileMode === "invented_and_missing") {
          const kept = uniqueTokens.slice(0, -1);
          const missing = uniqueTokens.slice(-1);
          rawUp = `Resumen clinico: ${kept.join(", ")} referenciado por ⟦PERSONA_99⟧ con nota ambigua [PERSONA].`;
          restored = `Resumen clinico: ${kept
            .map((t) => state.tokenToOriginalValue[t] || t)
            .join(", ")} referenciado por ⟦PERSONA_99⟧ con nota ambigua [PERSONA].`;
          report = {
            restaurados: kept,
            faltantes: missing,
            desconocidos: ["⟦PERSONA_99⟧"],
            ambiguos: ["[PERSONA]"],
            tasa_restauracion: uniqueTokens.length ? kept.length / uniqueTokens.length : 1.0,
          };
        } else {
          rawUp = `Resumen Clínico Automatizado (Entidades vinculadas: ${uniqueTokens.join(", ")}).\n- Síntesis del caso: Se procesó la nota preservando ${uniqueTokens.length} token(s).`;
          restored = rawUp;
          for (const tok of uniqueTokens) {
            const val = state.tokenToOriginalValue[tok];
            if (val) {
              restored = restored.split(tok).join(val);
            }
          }
        }

        const lat = {
          layer1_2: simPrev.latency_ms.layer1_2,
          layer3: simPrev.latency_ms.layer3,
          upstream: 4.2,
          total: Number((simPrev.latency_ms.total + 4.2).toFixed(2)),
        };

        renderMaskedColumn(simPrev.masked, rawUp);
        renderRestoredColumn(restored, report, lat);
        recordLocalSimulatedAudit(mode, sessionId, "enviado", simPrev.entities, lat);
        setStatus("ok", "Flujo simulado sin servidor completado con éxito.");
        await refreshAuditLog();
        return;
      }

      const headers = {
        "Content-Type": "application/json",
        "X-Tapaito-Mode": mode,
        "X-Tapaito-Session": sessionId,
      };
      if (hostileMode) {
        headers["X-Tapaito-Mock-Hostile"] = hostileMode;
      }

      const resp = await fetch("/v1/chat/completions", {
        method: "POST",
        headers,
        body: JSON.stringify({
          model: "tapaito-mock",
          messages: [
            {
              role: "system",
              content:
                "Eres un asistente clínico colombiano. Resume la nota clínica y extrae los datos clave conservando los códigos diagnósticos y medicamentos.",
            },
            {
              role: "user",
              content: text,
            },
          ],
        }),
      });

      const body = await resp.json();

      if (resp.status === 422) {
        renderBlockedState(body.error);
        setStatus(
          "blocked",
          `ENVÍO BLOQUEADO (HTTP 422 · ${body.error?.code || "TAPAITO_RESIDUO"}): Ningún dato salió a la nube.`
        );
        await refreshAuditLog();
        return;
      }

      if (!resp.ok) {
        throw new Error(body?.error?.message || `HTTP ${resp.status}`);
      }

      const tapaitoMeta = body.tapaito || {};
      const assistantText = body.choices?.[0]?.message?.content || "";

      dom.upstreamModelBadge.textContent = body.model || "tapaito-mock";

      renderOriginalWithHighlights(text, tapaitoMeta.entities_masked || []);
      renderWarnings(tapaitoMeta.warnings || []);
      renderMaskedColumn(tapaitoMeta.masked_prompt || "", tapaitoMeta.raw_upstream_response || "");
      renderRestoredColumn(
        assistantText,
        tapaitoMeta.reinsertion_report || {},
        tapaitoMeta.latency_ms || {}
      );

      const ratePct = (
        ((tapaitoMeta.reinsertion_report?.tasa_restauracion ?? 1.0) * 100)
      ).toFixed(0);
      setStatus(
        "ok",
        `Ciclo E2E completado en ${tapaitoMeta.latency_ms?.total ?? 0} ms · Tasa de reinserción: ${ratePct}%.`
      );
      await refreshAuditLog();
    } catch (err) {
      setStatus("blocked", `Error en /v1/chat/completions: ${err.message}`);
    } finally {
      dom.btnPreview.disabled = false;
      dom.btnSendChat.disabled = false;
    }
  }

  // =========================================================================
  // 9. Gestión de Sesión (DELETE /v1/tapaito/session/{id}) y Audit Log
  // =========================================================================
  async function deleteCurrentSession() {
    const sessionId = dom.sessionInput.value.trim() || "sess-demo-1";
    try {
      const resp = await fetch(`/v1/tapaito/session/${encodeURIComponent(sessionId)}`, {
        method: "DELETE",
      });
      const data = await resp.json();
      state.tokenToOriginalValue = {};
      setStatus(
        "ok",
        `Sesión "${sessionId}" eliminada de la memoria RAM (deleted=${Boolean(data.deleted)}).`
      );
    } catch (err) {
      state.tokenToOriginalValue = {};
      setStatus("ok", `Mapa local de la sesión "${sessionId}" limpiado en el navegador.`);
    }
  }

  function renderAuditRows(entries) {
    if (!Array.isArray(entries) || entries.length === 0) {
      dom.auditTableBody.innerHTML =
        '<tr><td colspan="8" class="audit-empty-row">Aún no hay eventos en <code>audit.jsonl</code>. Ejecute una previsualización o envío para registrar metadatos sin valores originales.</td></tr>';
      return;
    }

    dom.auditTableBody.innerHTML = entries
      .map((entry) => {
        const ts = escapeHtml(entry.timestamp || "—");
        const reqId = escapeHtml(entry.request_id || "—");
        const sessId = escapeHtml(entry.session_id || "—");
        const mode = escapeHtml(entry.mode || "rapido");
        const result = entry.result === "bloqueado" ? "bloqueado" : "enviado";
        const errCode = entry.error_code ? ` (${escapeHtml(entry.error_code)})` : "";

        const countsObj = entry.counts_by_type || {};
        const countsStr =
          Object.keys(countsObj).length > 0
            ? Object.entries(countsObj)
                .map(([k, v]) => `<code>${escapeHtml(k)}:${escapeHtml(v)}</code>`)
                .join(" ")
            : '<span class="empty-hint">0</span>';

        const spansArr = Array.isArray(entry.spans) ? entry.spans : [];
        const spansPreview =
          spansArr.length > 0
            ? spansArr
                .slice(0, 6)
                .map(
                  (s) =>
                    `<code>[${escapeHtml(s.start)}..${escapeHtml(s.end)} ${escapeHtml(s.entity_type)}/${escapeHtml(s.source)}]</code>`
                )
                .join(" ") +
              (spansArr.length > 6 ? ` <span>+${spansArr.length - 6} más</span>` : "")
            : '<span class="empty-hint">ninguno</span>';

        const lat = entry.latency_ms || {};
        const latStr = `L12:${lat.layer1_2 ?? 0} | L3:${lat.layer3 ?? 0} | T:${lat.total ?? 0}`;

        return (
          `<tr>` +
            `<td>${ts}</td>` +
            `<td><code>${reqId}</code></td>` +
            `<td><code>${sessId}</code></td>` +
            `<td>${mode}</td>` +
            `<td><span class="result-badge result-${result}">${result}${errCode}</span></td>` +
            `<td>${countsStr}</td>` +
            `<td>${spansPreview}</td>` +
            `<td><code>${escapeHtml(latStr)}</code></td>` +
          `</tr>`
        );
      })
      .join("");
  }

  async function refreshAuditLog() {
    if (dom.toggleOfflineSim.checked && state.localAuditFallback.length > 0) {
      renderAuditRows(state.localAuditFallback);
      return;
    }

    try {
      const resp = await fetch("/v1/tapaito/audit?limit=20");
      if (!resp.ok) {
        throw new Error(`HTTP ${resp.status}`);
      }
      const data = await resp.json();
      const combined = [
        ...state.localAuditFallback,
        ...(Array.isArray(data.entries) ? data.entries : []),
      ].slice(0, 20);
      renderAuditRows(combined);
    } catch (_err) {
      renderAuditRows(state.localAuditFallback);
    }
  }

  async function checkServerHealth() {
    try {
      const resp = await fetch("/healthz");
      if (!resp.ok) throw new Error("No OK");
      const data = await resp.json();
      dom.healthPill.className = "health-pill health-ok";
      dom.healthPill.textContent = `Nodo Local Activo · v${data.version || "0.1.0"}`;
    } catch (_err) {
      dom.healthPill.className = "health-pill health-offline";
      dom.healthPill.textContent = "Modo Autónomo (Sin servidor)";
      dom.toggleOfflineSim.checked = true;
    }
  }

  // =========================================================================
  // 10. Selección de Modo y Casos Precargados
  // =========================================================================
  function setMode(newMode) {
    state.mode = newMode === "estricto" ? "estricto" : "rapido";
    const isEstricto = state.mode === "estricto";

    dom.modeRapidoBtn.classList.toggle("active", !isEstricto);
    dom.modeRapidoBtn.setAttribute("aria-pressed", String(!isEstricto));

    dom.modeEstrictoBtn.classList.toggle("active", isEstricto);
    dom.modeEstrictoBtn.setAttribute("aria-pressed", String(isEstricto));
  }

  function loadPresetCase(caseKey) {
    const preset = PRESET_CASES[caseKey];
    if (!preset) return;

    state.activeCase = caseKey;
    dom.presetButtons.forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.case === caseKey);
    });

    dom.clinicalInput.value = preset.text;
    dom.sessionInput.value = preset.sessionId;
    dom.hostileSelect.value = preset.hostileMode;
    dom.toggleForce422.checked = Boolean(preset.force422);
    setMode(preset.mode);
    updateCharCounter();

    setStatus("idle", `Cargado: ${preset.title}. Haga clic en Previsualizar o Enviar a IA.`);
  }

  // =========================================================================
  // 11. Inicialización de Eventos
  // =========================================================================
  function init() {
    dom.presetButtons.forEach((btn) => {
      btn.addEventListener("click", () => {
        loadPresetCase(btn.dataset.case);
      });
    });

    dom.modeRapidoBtn.addEventListener("click", () => setMode("rapido"));
    dom.modeEstrictoBtn.addEventListener("click", () => setMode("estricto"));

    dom.clinicalInput.addEventListener("input", updateCharCounter);

    dom.btnPreview.addEventListener("click", runPreview);
    dom.btnSendChat.addEventListener("click", runChatCompletion);
    dom.btnDeleteSession.addEventListener("click", deleteCurrentSession);
    dom.btnRefreshAudit.addEventListener("click", refreshAuditLog);

    // Cargar Caso 1 por defecto y verificar salud del backend
    loadPresetCase("case1");
    checkServerHealth().then(() => {
      refreshAuditLog();
      runPreview();
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
