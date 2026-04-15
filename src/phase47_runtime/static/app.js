/* global fetch */
(function () {
  const $ = (id) => document.getElementById(id);

  const OBJECT_SECTIONS_FALLBACK = [
    { id: "brief", label: "Brief" },
    { id: "why_now", label: "Why now" },
    { id: "what_could_change", label: "What could change" },
    { id: "evidence", label: "Evidence" },
    { id: "history", label: "History" },
    { id: "ask_ai", label: "Ask AI" },
    { id: "advanced", label: "Advanced" },
  ];
  let objectSections = OBJECT_SECTIONS_FALLBACK.slice();

  /** @type {Record<string, unknown> | null} */
  let lastFeed = null;

  /** Last Today spectrum query (for object detail API). */
  const lastSpectrumQuery = { horizon: "short", mock_price_tick: "0" };

  function cockpitLang() {
    try {
      return window.__cockpitLang || localStorage.getItem("cockpitLang") || "ko";
    } catch (_) {
      return window.__cockpitLang || "ko";
    }
  }

  function withLang(path) {
    if (path.indexOf("lang=") >= 0) return path;
    const lg = cockpitLang();
    const sep = path.indexOf("?") >= 0 ? "&" : "?";
    return path + sep + "lang=" + encodeURIComponent(lg);
  }

  function tr(key) {
    const m = window.__localeStrings || {};
    return m[key] != null && String(m[key]) !== "" ? String(m[key]) : key;
  }

  async function loadLocaleStrings() {
    const lg = cockpitLang();
    const r = await fetch("/api/locale?lang=" + encodeURIComponent(lg));
    const json = await r.json().catch(() => ({}));
    if (json.ok && json.strings) window.__localeStrings = json.strings;
  }

  function applyChromeStrings() {
    document.querySelectorAll("[data-i18n]").forEach((el) => {
      const k = el.getAttribute("data-i18n");
      if (k) el.textContent = tr(k);
    });
    document.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
      const k = el.getAttribute("data-i18n-placeholder");
      if (k) el.setAttribute("placeholder", tr(k));
    });
  }

  async function api(path, opts) {
    const o = opts || {};
    const method = (o.method || "GET").toUpperCase();
    let url = path;
    if (method === "GET" && path.startsWith("/api/") && !path.startsWith("/api/locale")) {
      url = withLang(path);
    }
    const r = await fetch(url, o);
    const j = await r.json().catch(() => ({}));
    return { ok: r.ok, status: r.status, json: j };
  }

  function escapeHtml(s) {
    if (!s) return "";
    const d = document.createElement("div");
    d.textContent = s;
    return d.innerHTML;
  }

  function fmtBody(s) {
    return escapeHtml(s || "").replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  }

  function showPanel(name) {
    document.querySelectorAll(".panel").forEach((p) => p.classList.remove("visible"));
    const el = document.getElementById("panel-" + name);
    if (el) el.classList.add("visible");
    document.querySelectorAll("#nav button.nav-main[data-panel]").forEach((b) => {
      b.classList.toggle("active", b.dataset.panel === name);
    });
    if (name === "replay") loadReplay();
    if (name === "advanced") loadAlerts();
    if (name === "watchlist") loadWatchlistPanel();
    if (name === "ask_ai") syncAskAiFromFeed();
  }

  document.querySelectorAll("#nav button.nav-main[data-panel]").forEach((btn) => {
    btn.addEventListener("click", () => showPanel(btn.dataset.panel));
  });

  document.querySelectorAll("#replay-subtabs button[data-replay-sub]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const sub = btn.dataset.replaySub;
      document.querySelectorAll("#replay-subtabs button").forEach((b) => b.classList.toggle("on", b === btn));
      $("replay-sub-timeline").style.display = sub === "timeline" ? "block" : "none";
      $("replay-sub-counterfactual").style.display = sub === "counterfactual" ? "block" : "none";
      if (sub === "counterfactual") loadCounterfactual();
    });
  });

  const replayCache = { events: [], series: [] };

  function renderReplayChart(series) {
    const svg = $("replay-svg");
    const ns = "http://www.w3.org/2000/svg";
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    function addPath(ser, dash) {
      const pts = ser && ser.points;
      if (!pts || !pts.length) return;
      const d = pts
        .map((p, i) => `${i === 0 ? "M" : "L"} ${(p.x_norm * 100).toFixed(2)} ${(36 - p.y * 30).toFixed(2)}`)
        .join(" ");
      const path = document.createElementNS(ns, "path");
      path.setAttribute("d", d);
      path.setAttribute("fill", "none");
      path.setAttribute("stroke", (ser.style && ser.style.color) || "#5b8cff");
      path.setAttribute("stroke-width", "0.35");
      path.setAttribute("vector-effect", "non-scaling-stroke");
      if (dash) path.setAttribute("stroke-dasharray", "2 1.5");
      path.setAttribute("opacity", String((ser.style && ser.style.opacity) || 0.5));
      svg.appendChild(path);
    }
    const ref = series.find((s) => s.series_id === "illustrative_reference");
    const stance = series.find((s) => s.series_id === "stance_posture_index");
    addPath(ref, true);
    addPath(stance, false);
    const evs = replayCache.events || [];
    const n = evs.length;
    evs.forEach((ev, i) => {
      const xn = n <= 1 ? 50 : (i / (n - 1)) * 100;
      const circle = document.createElementNS(ns, "circle");
      circle.setAttribute("cx", xn.toFixed(2));
      circle.setAttribute("cy", "18");
      circle.setAttribute("r", "0.85");
      circle.setAttribute("fill", "#c9a227");
      circle.setAttribute("opacity", "0.9");
      svg.appendChild(circle);
    });
  }

  async function selectReplayEvent(eventId, liEl) {
    document.querySelectorAll("ul.replay-events li").forEach((x) => x.classList.remove("selected"));
    if (liEl) liEl.classList.add("selected");
    const { json } = await api("/api/replay/micro-brief?event_id=" + encodeURIComponent(eventId));
    const aside = $("replay-micro-brief");
    if (!json.ok) {
      aside.innerHTML = `<h3>Micro-brief</h3><p class="empty">${escapeHtml(JSON.stringify(json))}</p>`;
      return;
    }
    const m = json.micro_brief || {};
    const st = m.style_token || {};
    aside.innerHTML =
      `<h3>Micro-brief</h3>` +
      `<div class="brief-block"><div class="brief-label">${escapeHtml(m.event_type || "")}</div>` +
      `<div class="brief-value">${escapeHtml(m.title || "")}</div></div>` +
      `<div class="brief-block"><div class="brief-label">Known then</div><div class="brief-value">${escapeHtml(m.known_then || "")}</div></div>` +
      `<div class="brief-block"><div class="brief-label">Message</div><div class="brief-value">${escapeHtml(m.message_summary || "")}</div></div>` +
      `<div class="brief-block"><div class="brief-label">Evidence</div><div class="brief-value">${escapeHtml(m.evidence_summary || "")}</div></div>` +
      `<div class="brief-block"><div class="brief-label">Decision quality</div><div class="brief-value">${escapeHtml(m.decision_quality_note || "")}</div></div>` +
      `<div class="brief-block"><div class="brief-label">Outcome quality</div><div class="brief-value">${escapeHtml(m.outcome_quality_note || "")}</div></div>` +
      (st.marker
        ? `<p class="meta" style="margin-top:0.5rem">Marker: ${escapeHtml(st.marker)} · ${escapeHtml(st.color || "")}</p>`
        : "");
  }

  async function loadCounterfactual() {
    const { json } = await api("/api/replay/contract");
    const host = $("cf-branches");
    host.innerHTML = "";
    const branches =
      (json.replay_surface &&
        json.replay_surface.counterfactual_scaffold &&
        json.replay_surface.counterfactual_scaffold.branches) ||
      [];
    branches.forEach((b) => {
      const div = document.createElement("div");
      div.className = "cf-branch" + (b.state === "stub" ? " stub" : "");
      div.textContent = (b.label || b.id) + (b.state === "stub" ? " — stub" : "");
      host.appendChild(div);
    });
  }

  async function loadReplay() {
    const { json } = await api("/api/replay/timeline");
    if (!json.ok) {
      $("replay-event-list").innerHTML = `<li class='empty'>${escapeHtml(json.error || "error")}</li>`;
      return;
    }
    replayCache.events = json.events || [];
    replayCache.series = json.series || [];
    const pf = json.portfolio_traceability || {};
    $("replay-portfolio-stub").textContent = pf.note || "";
    renderReplayChart(json.series || []);
    const ul = $("replay-event-list");
    ul.innerHTML = "";
    (json.events || []).forEach((ev) => {
      const li = document.createElement("li");
      li.dataset.eventId = ev.event_id;
      li.innerHTML =
        `<span class="ev-type">${escapeHtml(ev.event_type)}</span><br/>${escapeHtml(ev.title || "")}<br/><span class="mono" style="font-size:0.72rem">${escapeHtml(
          (ev.timestamp_utc || "").slice(0, 19)
        )}</span>`;
      li.addEventListener("click", () => selectReplayEvent(ev.event_id, li));
      ul.appendChild(li);
    });
  }

  function wireHomeJumpButtons(root) {
    root.querySelectorAll("button[data-jump]").forEach((btn) => {
      btn.addEventListener("click", () => showPanel(btn.getAttribute("data-jump")));
    });
  }

  function readSpectrumTablePrefs(wrap) {
    let sortVal = "position_desc";
    let watchOnly = false;
    try {
      sortVal = sessionStorage.getItem("todaySpectrumSort") || "position_desc";
      watchOnly = sessionStorage.getItem("todaySpectrumWatchOnly") === "1";
    } catch (_) {}
    const ps = wrap && wrap.querySelector("#spectrum-sort-select");
    const pw = wrap && wrap.querySelector("#spectrum-watch-only");
    if (ps && ps.value) sortVal = ps.value;
    if (pw) watchOnly = !!pw.checked;
    return { sortVal, watchOnly };
  }

  async function loadTodaySpectrumDemo() {
    const wrap = $("home-spectrum-demo-wrap");
    if (!wrap) return;
    const prefs = readSpectrumTablePrefs(wrap);
    const prev = wrap.querySelector("#spectrum-horizon-select");
    const prevMock = wrap.querySelector("#spectrum-mock-tick");
    const hz = prev && prev.value ? prev.value : "short";
    const mt = prevMock && prevMock.value ? prevMock.value : "0";
    const { json } = await api(
      "/api/today/spectrum?horizon=" + encodeURIComponent(hz) + "&mock_price_tick=" + encodeURIComponent(mt)
    );
    if (!json.ok) {
      wrap.innerHTML = `<p class="empty">${escapeHtml(JSON.stringify(json))}</p>`;
      return;
    }
    lastSpectrumQuery.horizon = json.horizon || "short";
    lastSpectrumQuery.mock_price_tick = json.mock_price_tick || "0";
    const opts = (json.horizon_options || [])
      .map((o) => `<option value="${escapeHtml(o.id)}"${o.id === json.horizon ? " selected" : ""}>${escapeHtml(o.label)}</option>`)
      .join("");
    function bandLabel(b) {
      if (b === "left") return tr("spectrum.band_left");
      if (b === "right") return tr("spectrum.band_right");
      return tr("spectrum.band_center");
    }
    function bandDot(b) {
      const cls = b === "left" ? "left" : b === "right" ? "right" : "center";
      return `<span class="spectrum-dot spectrum-dot--${cls}" aria-hidden="true"></span>`;
    }
    const watchArr = Array.isArray(window.__watchlistSpectrumFilterIds)
      ? window.__watchlistSpectrumFilterIds
      : window.__todayWatchlistAssetIds || [];
    const watchIdSet = new Set(watchArr.map((x) => String(x)));
    const watchFilterDisabled = watchIdSet.size === 0;
    let rowObjs = (json.rows || []).slice();
    if (prefs.watchOnly && !watchFilterDisabled) {
      rowObjs = rowObjs.filter((r) => watchIdSet.has(String(r.asset_id || "")));
    }
    rowObjs.sort((a, b) => {
      if (prefs.sortVal === "asset_az") {
        return String(a.asset_id || "").localeCompare(String(b.asset_id || ""));
      }
      const pa = parseFloat(a.spectrum_position);
      const pb = parseFloat(b.spectrum_position);
      const na = Number.isFinite(pa) ? pa : 0;
      const nb = Number.isFinite(pb) ? pb : 0;
      if (prefs.sortVal === "position_asc") return na - nb;
      return nb - na;
    });
    let rows = "";
    if (!rowObjs.length) {
      const rawCount = (json.rows || []).length;
      const emptyMsg = rawCount && prefs.watchOnly ? tr("spectrum.watch_filter_empty") : "—";
      rows = `<tr><td colspan="6" class="empty">${escapeHtml(emptyMsg)}</td></tr>`;
    } else {
      rowObjs.forEach((r) => {
        const b = r.spectrum_band || "center";
        const msg = r.message || {};
        const head = escapeHtml(msg.headline || "");
        const sub = escapeHtml(msg.one_line_take || "");
        const aid = escapeHtml(r.asset_id || "");
        const wcRaw = String(r.what_changed || "");
        const wcEsc = escapeHtml(wcRaw);
        const titleAttr = wcEsc.replace(/"/g, "&quot;");
        const ratRaw = String(r.rationale_summary || "").trim();
        const rat = escapeHtml(ratRaw);
        const ratDetails = ratRaw
          ? `<details class="spectrum-rationale"><summary>${escapeHtml(tr("spectrum.expand_rationale"))}</summary><div>${rat}</div></details>`
          : "";
        rows +=
          "<tr><td class='mono'>" +
          `<button type="button" class="spectrum-asset-btn" data-asset="${aid}">${aid}</button>` +
          "</td><td>" +
          bandDot(b) +
          escapeHtml(bandLabel(b)) +
          "</td><td>" +
          escapeHtml(String(r.spectrum_position ?? "")) +
          "</td><td>" +
          escapeHtml(r.valuation_tension || "") +
          "</td><td><span class='spectrum-msg-head'>" +
          head +
          "</span><span class='spectrum-msg-sub'>" +
          sub +
          "</span>" +
          ratDetails +
          "</td><td>" +
          (wcEsc ? `<span class="wc-chip" title="${titleAttr}">${wcEsc}</span>` : `<span class="wc-chip">—</span>`) +
          "</td></tr>";
      });
    }
    const sd = prefs.sortVal === "position_desc" ? " selected" : "";
    const sa = prefs.sortVal === "position_asc" ? " selected" : "";
    const sz = prefs.sortVal === "asset_az" ? " selected" : "";
    const wChk = prefs.watchOnly ? " checked" : "";
    const wDis = watchFilterDisabled ? " disabled" : "";
    wrap.innerHTML =
      `<div class="feed-card today-hero-card"><h3>${escapeHtml(tr("spectrum.hero_title"))}</h3>` +
      `<p class="sub">${escapeHtml(tr("spectrum.demo_meta"))}</p>` +
      `<p class="meta">${escapeHtml(tr("spectrum.as_of"))}: ${escapeHtml(json.as_of_utc || "—")} · ${escapeHtml(tr("spectrum.model_family"))}: <span class="mono">${escapeHtml(
        json.active_model_family || ""
      )}</span></p>` +
      (json.price_layer_note
        ? `<p class="mono" style="font-size:0.72rem;margin:0.25rem 0;">${escapeHtml(json.price_layer_note)}</p>`
        : "") +
      (json.mock_price_tick === "1" && json.mock_price_tick_note
        ? `<p class="sub" style="color:var(--warn)">${escapeHtml(json.mock_price_tick_note)}</p>`
        : "") +
      `<div class="spectrum-legend"><span>${bandDot("left")}${escapeHtml(tr("spectrum.band_left"))}</span>` +
      `<span>${bandDot("center")}${escapeHtml(tr("spectrum.band_center"))}</span>` +
      `<span>${bandDot("right")}${escapeHtml(tr("spectrum.band_right"))}</span></div>` +
      `<div class="spectrum-toolbar">` +
      `<label class="meta">${escapeHtml(tr("spectrum.sort_by"))} <select id="spectrum-sort-select">` +
      `<option value="position_desc"${sd}>${escapeHtml(tr("spectrum.sort_position_desc"))}</option>` +
      `<option value="position_asc"${sa}>${escapeHtml(tr("spectrum.sort_position_asc"))}</option>` +
      `<option value="asset_az"${sz}>${escapeHtml(tr("spectrum.sort_asset_az"))}</option>` +
      `</select></label>` +
      `<label class="meta"><input type="checkbox" id="spectrum-watch-only"${wChk}${wDis} /> ${escapeHtml(tr("spectrum.watch_only"))}</label>` +
      `</div>` +
      (() => {
        const W = (window.__todayWatchlistAssetIds || []).length;
        const F = (window.__watchlistSpectrumFilterIds || []).length;
        const S = (window.__spectrumSeedAssetIds || []).length;
        const rawM = (window.__watchlistOnSpectrumRaw || []).length;
        const M = (window.__watchlistOnSpectrumAliased || []).length;
        const ctx =
          `<p class="spectrum-context-line">` +
          `${escapeHtml(tr("spectrum.label_bundle"))}: ${W} · ${escapeHtml(tr("spectrum.label_filter_tokens"))}: ${F} · ${escapeHtml(
            tr("spectrum.label_seed_board")
          )}: ${S} · ${escapeHtml(tr("spectrum.label_match_on_seed"))}: ${M}` +
          `</p>`;
        let hint = "";
        if (rawM === 0 && M > 0) {
          hint = `<p class="spectrum-hint-warn">${escapeHtml(tr("spectrum.hint_alias_active"))}</p>`;
        } else if (M === 0 && W > 0 && S > 0) {
          hint = `<p class="spectrum-hint-warn">${escapeHtml(tr("spectrum.hint_no_overlap"))}</p>`;
        }
        return ctx + hint;
      })() +
      `<p class="sub">${escapeHtml(tr("spectrum.row_click_hint"))}</p>` +
      `<div class="row" style="margin:0.35rem 0;flex-wrap:wrap;gap:0.5rem"><label class="meta">${escapeHtml(tr("spectrum.horizon_picker"))} <select id="spectrum-horizon-select">${opts}</select></label>` +
      `<label class="meta">${escapeHtml(tr("spectrum.mock_mode"))} <select id="spectrum-mock-tick">` +
      `<option value="0"${json.mock_price_tick === "0" ? " selected" : ""}>${escapeHtml(tr("spectrum.mock_base"))}</option>` +
      `<option value="1"${json.mock_price_tick === "1" ? " selected" : ""}>${escapeHtml(tr("spectrum.mock_shock"))}</option>` +
      `</select></label></div>` +
      `<div class="spectrum-table-scroll"><table style="width:100%;font-size:0.82rem;border-collapse:collapse"><thead><tr>` +
      `<th style="text-align:left;border-bottom:1px solid #2a3544">${escapeHtml(tr("spectrum.col_asset"))}</th>` +
      `<th style="text-align:left;border-bottom:1px solid #2a3544">${escapeHtml(tr("spectrum.col_band"))}</th>` +
      `<th style="text-align:left;border-bottom:1px solid #2a3544">${escapeHtml(tr("spectrum.col_position"))}</th>` +
      `<th style="text-align:left;border-bottom:1px solid #2a3544">${escapeHtml(tr("spectrum.col_tension"))}</th>` +
      `<th style="text-align:left;border-bottom:1px solid #2a3544">${escapeHtml(tr("spectrum.col_message"))}</th>` +
      `<th style="text-align:left;border-bottom:1px solid #2a3544">${escapeHtml(tr("spectrum.col_changed"))}</th>` +
      `</tr></thead><tbody>${rows}</tbody></table></div></div>`;
    const sortEl = wrap.querySelector("#spectrum-sort-select");
    if (sortEl) {
      sortEl.onchange = () => {
        try {
          sessionStorage.setItem("todaySpectrumSort", sortEl.value);
        } catch (_) {}
        loadTodaySpectrumDemo();
      };
    }
    const wo = wrap.querySelector("#spectrum-watch-only");
    if (wo) {
      wo.onchange = () => {
        try {
          sessionStorage.setItem("todaySpectrumWatchOnly", wo.checked ? "1" : "0");
        } catch (_) {}
        loadTodaySpectrumDemo();
      };
    }
    const sel = wrap.querySelector("#spectrum-horizon-select");
    if (sel) sel.onchange = () => loadTodaySpectrumDemo();
    const sm = wrap.querySelector("#spectrum-mock-tick");
    if (sm) sm.onchange = () => loadTodaySpectrumDemo();
    wrap.querySelectorAll(".spectrum-asset-btn").forEach((btn) => {
      btn.addEventListener("click", () => openTodayObjectDetail(btn.getAttribute("data-asset") || ""));
    });
  }

  function renderTodayObjectDetailHtml(j) {
    const msg = j.message || {};
    const inf = j.information || {};
    const res = j.research || {};
    const links = res.links || {};
    const spec = j.spectrum || {};
    function ulItems(arr) {
      const a = Array.isArray(arr) ? arr : [];
      if (!a.length) return `<li class="sub">—</li>`;
      return a.map((x) => `<li>${escapeHtml(x)}</li>`).join("");
    }
    function kv(labelKey, val) {
      const v = val != null && String(val) !== "" ? String(val) : "—";
      return `<div class="mir-kv"><span class="k">${escapeHtml(tr(labelKey))}</span>${escapeHtml(v)}</div>`;
    }
    const metaLine =
      `${escapeHtml(j.horizon_label || "")} · <span class="mono">${escapeHtml(j.asset_id || "")}</span> · ${escapeHtml(
        j.active_model_family || ""
      )} · ${escapeHtml(j.as_of_utc || "")}`;
    const msgBlock =
      kv("today_detail.f_headline", msg.headline) +
      kv("today_detail.f_one_line", msg.one_line_take) +
      kv("today_detail.f_why_now", msg.why_now) +
      kv("today_detail.f_what_changed", msg.what_changed) +
      kv("today_detail.f_unproven", msg.what_remains_unproven) +
      kv("today_detail.f_watch", msg.what_to_watch) +
      kv("today_detail.f_confidence", msg.confidence_band) +
      kv("today_detail.f_action", msg.action_frame) +
      kv("today_detail.f_evidence", msg.linked_evidence_summary);
    const infBlock =
      `<div class="mir-kv"><span class="k">${escapeHtml(tr("today_detail.supporting"))}</span><ul class="feed-list">${ulItems(
        inf.supporting_signals
      )}</ul></div>` +
      `<div class="mir-kv"><span class="k">${escapeHtml(tr("today_detail.opposing"))}</span><ul class="feed-list">${ulItems(
        inf.opposing_signals
      )}</ul></div>` +
      kv("today_detail.evidence", inf.evidence_summary) +
      kv("today_detail.data_note", inf.data_layer_note);
    const prefillEnc = encodeURIComponent(links.prefill_ask_ai || "");
    const resBlock =
      `<div class="mir-kv"><span class="k">${escapeHtml(tr("today_detail.deeper_rationale"))}</span>${escapeHtml(
        res.deeper_rationale || ""
      )}</div>` +
      `<div class="mir-kv"><span class="k">${escapeHtml(tr("spectrum.model_family"))}</span>${escapeHtml(
        res.model_family_context || ""
      )}</div>` +
      `<div class="row" style="margin-top:0.75rem">` +
      `<button type="button" class="btn" id="today-detail-btn-replay">${escapeHtml(tr("today_detail.link_replay"))}</button>` +
      `<button type="button" class="btn btn-primary" id="today-detail-btn-ask" data-prefill="${prefillEnc}">${escapeHtml(
        tr("today_detail.link_ask")
      )}</button>` +
      `</div>`;

    return (
      `<p class="meta">${metaLine}</p>` +
      `<div class="mir-block"><h4>${escapeHtml(tr("today_detail.spectrum_ctx"))}</h4>` +
      `<div class="mir-kv"><span class="k">${escapeHtml(tr("spectrum.col_band"))}</span>${escapeHtml(spec.spectrum_band || "")} · ${escapeHtml(
        tr("spectrum.col_position")
      )}: ${escapeHtml(String(spec.spectrum_position ?? ""))}</div>` +
      `<div class="mir-kv"><span class="k">${escapeHtml(tr("spectrum.col_tension"))}</span>${escapeHtml(spec.valuation_tension || "")}</div>` +
      `<div class="mir-kv"><span class="k">${escapeHtml(tr("spectrum.col_rationale"))}</span>${escapeHtml(spec.rationale_summary || "")}</div>` +
      `<div class="mir-kv"><span class="k">${escapeHtml(tr("spectrum.col_changed"))}</span>${escapeHtml(spec.what_changed || "")}</div></div>` +
      `<div class="mir-block"><h4>${escapeHtml(tr("today_detail.section_message"))}</h4>${msgBlock}</div>` +
      `<div class="mir-block"><h4>${escapeHtml(tr("today_detail.section_information"))}</h4>${infBlock}</div>` +
      `<div class="mir-block"><h4>${escapeHtml(tr("today_detail.section_research"))}</h4>${resBlock}</div>`
    );
  }

  function wireTodayDetailActions() {
    const br = $("today-detail-btn-replay");
    if (br)
      br.addEventListener("click", () => {
        showPanel("replay");
        loadReplay();
      });
    const ba = $("today-detail-btn-ask");
    if (ba) {
      ba.addEventListener("click", () => {
        const raw = ba.getAttribute("data-prefill") || "";
        let text = "";
        try {
          text = decodeURIComponent(raw);
        } catch (_) {
          text = raw;
        }
        const ta = $("conv-in");
        if (ta) ta.value = text;
        showPanel("ask_ai");
        syncAskAiFromFeed();
      });
    }
  }

  async function openTodayObjectDetail(assetId) {
    if (!assetId) return;
    const q = lastSpectrumQuery;
    const { json } = await api(
      "/api/today/object?asset_id=" +
        encodeURIComponent(assetId) +
        "&horizon=" +
        encodeURIComponent(q.horizon || "short") +
        "&mock_price_tick=" +
        encodeURIComponent(q.mock_price_tick || "0")
    );
    const root = $("today-detail-root");
    if (!root) return;
    const ptd = $("panel-today_detail");
    if (!json.ok) {
      if (ptd) ptd.removeAttribute("data-current-asset");
      root.innerHTML = `<p class="empty">${escapeHtml(JSON.stringify(json))}</p>`;
      showPanel("today_detail");
      return;
    }
    if (ptd) ptd.setAttribute("data-current-asset", assetId);
    root.innerHTML = renderTodayObjectDetailHtml(json);
    wireTodayDetailActions();
    showPanel("today_detail");
  }

  async function loadHomeFeed() {
    const { json } = await api("/api/home/feed");
    lastFeed = json && json.ok ? json : lastFeed;
    const root = $("home-feed-root");
    if (!json.ok) {
      root.innerHTML = `<p class="empty">${escapeHtml(JSON.stringify(json))}</p>`;
      return;
    }

    const tsui = json.today_spectrum_ui;
    window.__todayWatchlistAssetIds = (tsui && tsui.watchlist_asset_ids) || [];
    window.__watchlistSpectrumFilterIds = (tsui && tsui.watchlist_spectrum_filter_ids) || window.__todayWatchlistAssetIds;
    window.__spectrumSeedAssetIds = (tsui && tsui.spectrum_seed_asset_ids) || [];
    window.__watchlistOnSpectrumRaw = (tsui && tsui.watchlist_on_spectrum) || [];
    window.__watchlistOnSpectrumAliased = (tsui && tsui.watchlist_on_spectrum_aliased) || [];

    const today = json.today || {};
    const act = today.action_needed;
    const actHtml = act
      ? `<div class="action-flag">${escapeHtml(tr("action.review"))}</div>`
      : `<div class="action-flag passive">${escapeHtml(tr("action.calm"))}</div>`;

    const parts = [];
    parts.push(
      `<div class="feed-card"><h3>${escapeHtml(tr("home.card.today"))}</h3><div class="sub" style="font-weight:600;color:var(--text)">${escapeHtml(today.title || "")}</div>` +
        `<div class="body" style="margin-top:0.5rem">${fmtBody(today.body || "")}</div>${actHtml}</div>`
    );

    const tss = json.today_spectrum_summary;
    if (tss && tss.top_messages && tss.top_messages.length) {
      let tli = "";
      tss.top_messages.forEach((tm) => {
        const aid = escapeHtml(tm.asset_id || "");
        tli +=
          `<li><button type="button" class="spectrum-asset-btn spectrum-home-summary-open" data-asset="${aid}"><strong class="mono">${aid}</strong></button> <span class="sub">(${escapeHtml(
            tm.spectrum_band || ""
          )})</span>` +
          `<div style="margin-top:0.25rem;font-weight:600">${escapeHtml(tm.headline || "")}</div>` +
          `<div class="sub">${escapeHtml(tm.one_line_take || "")}</div></li>`;
      });
      parts.push(
        `<div class="feed-card"><h3>${escapeHtml(tr("home.spectrum.card_title"))}</h3>` +
          `<p class="sub">${escapeHtml(tr("home.spectrum.card_meta"))}</p>` +
          `<p class="meta">${escapeHtml(tss.horizon_label || "")} · <span class="mono">${escapeHtml(tss.active_model_family || "")}</span> · ${escapeHtml(
            tss.as_of_utc || ""
          )}</p>` +
          `<ul class="feed-list">${tli}</ul></div>`
      );
    }

    const wb = json.watchlist_block || {};
    const witems = wb.items || [];
    let whtml = "";
    witems.forEach((it) => {
      whtml +=
        `<li><strong>${escapeHtml(it.label || "")}</strong> — ${escapeHtml(it.detail || "")}` +
        `<div class="sub">${escapeHtml(it.why_watching || "")}</div></li>`;
    });
    const wch = (wb.what_changed_bullets || []).map((x) => `<li>${escapeHtml(x)}</li>`).join("");
    const wempty = wb.empty_state;
    parts.push(
      `<div class="feed-card"><h3>${escapeHtml(tr("home.card.watchlist"))}</h3>` +
        (wempty
          ? `<p class="sub"><strong>${escapeHtml(wempty.title)}</strong> — ${escapeHtml(wempty.why)} <em>${escapeHtml(wempty.fills_when)}</em></p>`
          : "") +
        (whtml ? `<ul class="feed-list">${whtml}</ul>` : "") +
        (wch
          ? `<div class="brief-label" style="margin-top:0.5rem">${escapeHtml(tr("home.section.what_changed"))}</div><ul class="feed-list">${wch}</ul>`
          : "") +
        `</div>`
    );

    const rip = json.research_in_progress || {};
    const threads = rip.threads || [];
    let rhtml = "";
    threads.forEach((th) => {
      rhtml +=
        `<li><strong>${escapeHtml(th.headline || "")}</strong> <span class="mono">${escapeHtml(th.when || "")}</span>` +
        `<div class="sub">${escapeHtml(th.sub || "")}</div><div class="sub">${escapeHtml(th.checkpoint || "")}</div></li>`;
    });
    const rempty = rip.empty_state;
    parts.push(
      `<div class="feed-card"><h3>${escapeHtml(tr("home.card.research"))}</h3>` +
        (rempty
          ? `<p class="sub"><strong>${escapeHtml(rempty.title)}</strong> — ${escapeHtml(rempty.why)} <em>${escapeHtml(rempty.fills_when)}</em></p>`
          : "") +
        (rhtml ? `<ul class="feed-list">${rhtml}</ul>` : `<p class="sub">${escapeHtml(tr("home.research.no_threads"))}</p>`) +
        `</div>`
    );

    const ap = json.alerts_preview || [];
    let ahtml = "";
    ap.forEach((a) => {
      const attn = a.needs_attention ? " · needs attention" : "";
      ahtml +=
        `<li><strong>${escapeHtml(a.status)}</strong> · ${escapeHtml(a.class || "")} · ${escapeHtml(a.asset_id || "")}${escapeHtml(attn)}` +
        `<br/><span class="sub">${escapeHtml(a.summary || "")}</span></li>`;
    });
    const ae = json.alerts_empty || {};
    parts.push(
      `<div class="feed-card"><h3>${escapeHtml(tr("home.card.alerts"))}</h3>` +
        (ahtml
          ? `<ul class="feed-list">${ahtml}</ul>`
          : `<p class="sub"><strong>${escapeHtml(ae.title || "No alerts")}</strong> — ${escapeHtml(ae.why || "")} <em>${escapeHtml(ae.fills_when || "")}</em></p>`) +
        `<button type="button" class="btn" data-jump="advanced">${escapeHtml(tr("home.jump.manage_alerts"))}</button></div>`
    );

    const jp = json.decision_journal_preview || [];
    let jhtml = "";
    jp.forEach((d) => {
      jhtml +=
        `<li><span class="mono">${escapeHtml(d.timestamp)}</span> · <strong>${escapeHtml(d.asset_id)}</strong> · ${escapeHtml(
          d.action_framing_plain || d.decision_type
        )}<div class="sub">${escapeHtml(d.why_short || "")}</div><div class="sub">${escapeHtml(d.replay_hint || "")}</div></li>`;
    });
    const je = json.decision_journal_empty;
    parts.push(
      `<div class="feed-card"><h3>${escapeHtml(tr("home.card.journal"))}</h3>` +
        (jhtml
          ? `<ul class="feed-list">${jhtml}</ul>`
          : je
            ? `<p class="sub"><strong>${escapeHtml(je.title)}</strong> — ${escapeHtml(je.why)} <em>${escapeHtml(je.fills_when)}</em></p>`
            : "") +
        `<button type="button" class="btn" data-jump="journal">${escapeHtml(tr("home.jump.open_journal"))}</button></div>`
    );

    const ab = json.ask_ai_brief || {};
    const sc = ab.shortcuts || [];
    let sclist = "";
    sc.forEach((s) => {
      sclist += `<li>${escapeHtml(s.label)}</li>`;
    });
    parts.push(
      `<div class="feed-card"><h3>${escapeHtml(tr("home.card.ask_ai"))}</h3><p class="body">${escapeHtml(ab.daily_line || "")}</p>` +
        `<ul class="feed-list" style="font-size:0.82rem">${sclist}</ul>` +
        `<button type="button" class="btn" data-jump="ask_ai">${escapeHtml(tr("home.jump.open_ask_ai"))}</button></div>`
    );

    const rp = json.replay_preview || {};
    const rpe = json.replay_preview_empty;
    const rpHead = escapeHtml(rp.headline || "Replay");
    const rpAsset = rp.asset_id ? `<strong>${escapeHtml(rp.asset_id)}</strong> · ` : "";
    const rpTs = rp.timestamp ? `<span class="mono">${escapeHtml(rp.timestamp)}</span><br/>` : "";
    parts.push(
      `<div class="feed-card"><h3>${escapeHtml(tr("home.card.replay"))}</h3>` +
        (rpe
          ? `<p class="sub"><strong>${escapeHtml(rpe.title)}</strong> — ${escapeHtml(rpe.why)} <em>${escapeHtml(rpe.fills_when)}</em></p>`
          : "") +
        `<p class="sub" style="font-weight:600;color:var(--text)">${rpHead}</p>` +
        `${rpAsset}${rpTs}` +
        `<p class="body" style="margin-top:0.45rem">${fmtBody(rp.one_line || "")}</p>` +
        `<p class="sub">${escapeHtml(rp.time_axis_snippet || "")}</p>` +
        `<p class="sub">${escapeHtml(rp.since_then || "")}</p>` +
        `<button type="button" class="btn btn-primary" data-jump="replay">${escapeHtml(tr("home.jump.open_replay"))}</button></div>`
    );

    const ps = json.portfolio_snapshot || {};
    parts.push(
      `<div class="feed-card"><h3>${escapeHtml(tr("home.card.portfolio"))}</h3><p class="sub">${escapeHtml(ps.copy || "")}</p>` +
        `<span class="badge default">${escapeHtml(ps.state || "stub")}</span></div>`
    );

    root.innerHTML = parts.join("");
    wireHomeJumpButtons(root);
    root.querySelectorAll(".spectrum-home-summary-open").forEach((btn) => {
      btn.addEventListener("click", () => {
        lastSpectrumQuery.horizon = "short";
        openTodayObjectDetail(btn.getAttribute("data-asset") || "");
      });
    });
    syncAskAiFromFeed();
    loadTodaySpectrumDemo();
  }

  async function loadWatchlistPanel() {
    const { json } = await api("/api/home/feed");
    if (json.ok) lastFeed = json;
    const root = $("watchlist-root");
    if (!json.ok) {
      root.innerHTML = `<p class="empty">${escapeHtml(JSON.stringify(json))}</p>`;
      return;
    }
    const wb = json.watchlist_block || {};
    const witems = wb.items || [];
    let whtml = "";
    witems.forEach((it) => {
      whtml +=
        `<div class="feed-card"><h3>${escapeHtml(it.label || "")}</h3><p class="body">${escapeHtml(it.detail || "")}</p>` +
        `<p class="sub">${escapeHtml(it.why_watching || "")}</p></div>`;
    });
    const wch = (wb.what_changed_bullets || []).map((x) => `<li>${escapeHtml(x)}</li>`).join("");
    const wempty = wb.empty_state;
    const blocks = [];
    if (wempty) {
      blocks.push(
        `<div class="feed-card"><h3>${escapeHtml(wempty.title)}</h3><p class="sub">${escapeHtml(wempty.why)}</p><p class="sub"><em>${escapeHtml(wempty.fills_when)}</em></p></div>`
      );
    }
    blocks.push(whtml);
    if (wch) {
      blocks.push(
        `<div class="feed-card"><h3>${escapeHtml(tr("home.section.what_changed"))}</h3><ul class="feed-list">${wch}</ul></div>`
      );
    }
    const joined = blocks.filter(Boolean).join("");
    root.innerHTML = joined || `<p class="empty">No watchlist rows yet.</p>`;
  }

  function syncAskAiFromFeed() {
    const ab = lastFeed && lastFeed.ask_ai_brief;
    $("ask-brief-line").textContent = (ab && ab.daily_line) || "Load Home once to refresh the copilot brief.";
    buildAskShortcuts();
  }

  function buildAskShortcuts() {
    const host = $("ask-shortcuts");
    host.innerHTML = "";
    const sc =
      (lastFeed && lastFeed.ask_ai_brief && lastFeed.ask_ai_brief.shortcuts) ||
      [
        { label: "What matters now?", prompt_text: "decision summary" },
        { label: "What changed?", prompt_text: "what changed" },
        { label: "Show my active research", prompt_text: "research layer" },
        { label: "What should I review next?", prompt_text: "what remains unproven" },
        { label: "Show my last decisions", prompt_text: "decision summary" },
        { label: "Open Replay for this item", prompt_text: "what changed", opens_panel: "replay" },
      ];
    sc.forEach((s) => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "btn";
      b.textContent = s.label;
      b.addEventListener("click", () => {
        if (s.opens_panel === "replay") {
          showPanel("replay");
          loadReplay();
          return;
        }
        $("conv-in").value = s.prompt_text;
        submitConv();
      });
      host.appendChild(b);
    });
  }

  function renderSectionPayload(j) {
    const el = $("object-section-body");
    if (!j.ok) {
      el.innerHTML = `<p class="empty">${escapeHtml(JSON.stringify(j))}</p>`;
      return;
    }
    const parts = [];
    if (j.intro) parts.push(`<p class="intro">${escapeHtml(j.intro)}</p>`);
    if (j.paragraphs) {
      j.paragraphs.forEach((p) => {
        parts.push(`<div class="brief-block"><div class="brief-value">${escapeHtml(p).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")}</div></div>`);
      });
    }
    if (j.message_summary) parts.push(`<div class="brief-block"><div class="brief-label">Message</div><div class="brief-value">${escapeHtml(j.message_summary)}</div></div>`);
    if (j.bullets_changed && j.bullets_changed.length) {
      parts.push("<div class='brief-label'>What changed</div><ul>" + j.bullets_changed.map((x) => "<li>" + escapeHtml(x) + "</li>").join("") + "</ul>");
    }
    if (j.watchpoints_plain && j.watchpoints_plain.length) {
      parts.push("<div class='brief-label'>What could change</div><ul>" + j.watchpoints_plain.map((x) => "<li>" + escapeHtml(x) + "</li>").join("") + "</ul>");
    }
    if (j.reopen_note) parts.push(`<div class="brief-block"><div class="brief-label">Reopen</div><div class="brief-value">${escapeHtml(j.reopen_note)}</div></div>`);
    if (j.closeout_plain) parts.push(`<div class="brief-block"><div class="brief-label">Closeout</div><div class="brief-value">${escapeHtml(j.closeout_plain)}</div></div>`);
    if (j.key_facts && j.key_facts.length) {
      parts.push("<div class='brief-label'>Key facts</div><ul>" + j.key_facts.map((x) => "<li>" + escapeHtml(x) + "</li>").join("") + "</ul>");
    }
    if (j.limits_and_provenance && j.limits_and_provenance.length) {
      parts.push("<div class='brief-label'>Limits &amp; provenance</div><ul>" + j.limits_and_provenance.map((x) => "<li>" + escapeHtml(x) + "</li>").join("") + "</ul>");
    }
    if (j.what_did_not_change && j.what_did_not_change.length) {
      parts.push("<div class='brief-label'>What did not change</div><ul>" + j.what_did_not_change.map((x) => "<li>" + escapeHtml(x) + "</li>").join("") + "</ul>");
    }
    if (j.what_remains_unproven && j.what_remains_unproven.length) {
      parts.push("<div class='brief-label'>What remains unproven / uncertain</div><ul>" + j.what_remains_unproven.map((x) => "<li>" + escapeHtml(x) + "</li>").join("") + "</ul>");
    }
    if (j.links) {
      parts.push(
        "<p>Jump to panels:</p><ul>" +
          j.links
            .map((L) => {
              return (
                "<li><button type='button' class='btn' data-jump='" +
                escapeHtml(L.panel) +
                "'>" +
                escapeHtml(L.label) +
                "</button></li>"
              );
            })
            .join("") +
          "</ul>"
      );
    }
    if (j.shortcuts) {
      parts.push("<div class='brief-label'>Copilot shortcuts (same as Ask AI tab)</div><div class='shortcut-row'></div>");
    }
    if (j.internal_layers) {
      parts.push(`<p class="intro">Internal layers (reference only): ${escapeHtml(j.internal_layers.join(", "))}</p>`);
    }
    if (j.raw_drilldown) {
      parts.push("<details><summary>Raw drilldown JSON</summary><pre class='mono'>" + escapeHtml(JSON.stringify(j.raw_drilldown, null, 2)) + "</pre></details>");
    }
    if (j.layer_summaries && Object.keys(j.layer_summaries).length) {
      parts.push("<details><summary>Layer summaries (pitch)</summary><pre class='mono'>" + escapeHtml(JSON.stringify(j.layer_summaries, null, 2)) + "</pre></details>");
    }
    if (j.trace_links && Object.keys(j.trace_links).length) {
      parts.push("<details><summary>Trace links</summary><pre class='mono'>" + escapeHtml(JSON.stringify(j.trace_links, null, 2)) + "</pre></details>");
    }
    el.innerHTML = parts.join("") || "<p class='empty'>No content.</p>";
    el.querySelectorAll("button[data-jump]").forEach((btn) => {
      btn.addEventListener("click", () => {
        showPanel(btn.getAttribute("data-jump"));
      });
    });
  }

  function buildObjectTabs() {
    const host = $("object-tabs");
    if (!host || !objectSections.length) return;
    host.innerHTML = "";
    objectSections.forEach((S, i) => {
      const b = document.createElement("button");
      b.type = "button";
      b.textContent = S.label;
      b.className = i === 0 ? "on" : "";
      b.addEventListener("click", () => {
        host.querySelectorAll("button").forEach((x) => x.classList.remove("on"));
        b.classList.add("on");
        loadObjectSection(S.id);
      });
      host.appendChild(b);
    });
    loadObjectSection(objectSections[0].id);
  }

  async function refreshObjectTabsFromOverview() {
    const { json } = await api("/api/overview");
    const tabs = json.user_first && json.user_first.navigation && json.user_first.navigation.object_detail_sections;
    if (json.ok && tabs && tabs.length) {
      objectSections = tabs.map((x) => ({ id: x.id, label: x.label }));
    } else {
      objectSections = OBJECT_SECTIONS_FALLBACK.slice();
    }
    buildObjectTabs();
  }

  async function loadObjectSection(section) {
    const { json } = await api("/api/user-first/section/" + encodeURIComponent(section));
    renderSectionPayload(json);
  }

  async function refreshMeta() {
    const { json } = await api("/api/meta");
    const m = json;
    const stale = m.bundle_stale ? '<span class="stale">Stale — reload recommended</span>' : "Fresh";
    $("hdr-meta").innerHTML =
      `Bundle time: ${escapeHtml(m.phase46_generated_utc || "—")} · Loaded: ${escapeHtml(m.runtime_loaded_at_utc || "—")} · ${stale}<br/>` +
      `Alerts: ${m.open_alert_count ?? "—"} open / ${m.total_alerts ?? "—"} total · Decisions: ${m.decision_count ?? "—"}`;
  }

  async function loadAlerts() {
    const st = $("flt-alert-status").value;
    const aid = $("flt-alert-asset").value.trim();
    let q = "/api/alerts?";
    if (st) q += "status=" + encodeURIComponent(st) + "&";
    if (aid) q += "asset_id=" + encodeURIComponent(aid) + "&";
    const { json } = await api(q);
    const ul = $("alert-list");
    ul.innerHTML = "";
    const list = json.alerts || [];
    $("alerts-empty").style.display = list.length ? "none" : "block";
    list.forEach((a, idx) => {
      const li = document.createElement("li");
      const id = a.alert_id || "";
      const attn = a.requires_attention ? " · <strong>Needs attention</strong>" : "";
      li.innerHTML =
        `<strong>${escapeHtml(a.status)}</strong> · ${escapeHtml(a.alert_class || "")} · ${escapeHtml(a.asset_id || "")}${attn}<br/>` +
        `<span class="mono">${escapeHtml((a.message_summary || "").slice(0, 220))}</span><br/>` +
        `<span class="mono" style="font-size:0.72rem">${escapeHtml(id)}</span><br/>`;
      ["acknowledge", "resolve", "supersede", "dismiss"].forEach((act) => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "btn";
        btn.textContent = act;
        btn.addEventListener("click", async () => {
          const body = id ? { action: act, alert_id: id } : { action: act, index: idx };
          const r = await api("/api/alerts/action", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
          });
          alert(r.json.ok ? "OK" : JSON.stringify(r.json));
          refreshMeta();
          loadAlerts();
          loadHomeFeed();
        });
        li.appendChild(btn);
      });
      ul.appendChild(li);
    });
  }

  async function loadJournalDecisions() {
    const { json } = await api("/api/decisions");
    const rows = json.decisions || [];
    $("decisions-empty").style.display = rows.length ? "none" : "block";
    const host = $("journal-cards");
    host.innerHTML = "";
    const recent = rows.slice(-24);
    recent.reverse().forEach((d) => {
      const div = document.createElement("div");
      div.className = "feed-card";
      div.innerHTML =
        `<div class="mono" style="font-size:0.75rem">${escapeHtml(String(d.timestamp || "").slice(0, 19))}</div>` +
        `<h3 style="margin:0.35rem 0 0.25rem;font-size:0.95rem">${escapeHtml(String(d.asset_id || "—"))}</h3>` +
        `<div class="sub">${escapeHtml(String(d.decision_type || ""))}</div>` +
        `<div class="body" style="margin-top:0.5rem">${escapeHtml(String(d.founder_note || "").slice(0, 800))}</div>` +
        `<div class="sub" style="margin-top:0.5rem">Use <strong>Replay</strong> for the timeline around this timestamp.</div>`;
      host.appendChild(div);
    });
  }

  async function submitConv() {
    const r = await api("/api/conversation", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: $("conv-in").value }),
    });
    const out = $("conv-out");
    const res = r.json.response || {};
    if (!r.json.ok) {
      out.innerHTML = "<pre class='mono'>" + escapeHtml(JSON.stringify(r.json, null, 2)) + "</pre>";
      return;
    }
    const md = res.body_markdown || "";
    out.innerHTML =
      "<div class='intent-tag'>Intent: " +
      escapeHtml(res.intent || "") +
      "</div>" +
      "<div class='md'>" +
      escapeHtml(md).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>").replace(/\n/g, "<br/>") +
      "</div>";
  }

  $("btn-alerts-refresh").addEventListener("click", loadAlerts);

  $("btn-record-decision").addEventListener("click", async () => {
    const asset_id = $("rec-aid").value.trim();
    if (!asset_id) {
      alert("Asset ID is required to log a decision.");
      return;
    }
    const body = {
      decision_type: $("rec-dt").value,
      asset_id,
      founder_note: $("rec-note").value,
      linked_message_summary: "runtime_ui",
      linked_authoritative_artifact: "phase46_bundle",
      linked_research_provenance: "phase44_bundle",
    };
    const r = await api("/api/decisions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    alert(r.json.ok ? "Recorded." : JSON.stringify(r.json));
    refreshMeta();
    loadJournalDecisions();
    loadHomeFeed();
  });

  $("btn-conv").addEventListener("click", submitConv);

  $("btn-reload").addEventListener("click", async () => {
    await api("/api/reload", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
    await refreshMeta();
    await loadHomeFeed();
    await loadJournalDecisions();
    if ($("panel-replay").classList.contains("visible")) await loadReplay();
    if ($("panel-advanced").classList.contains("visible")) await loadAlerts();
    alert("Bundle reloaded.");
  });

  async function pollNotif() {
    const { json } = await api("/api/notifications");
    const ev = json.events || [];
    const last = ev[ev.length - 1];
    $("notif-hint").textContent = last ? last.kind + " @ " + last.event_timestamp : "none";
  }

  async function switchLang(lg) {
    window.__cockpitLang = lg;
    try {
      localStorage.setItem("cockpitLang", lg);
    } catch (_) {}
    const koOn = lg === "ko";
    const lk = $("lang-ko");
    const le = $("lang-en");
    if (lk) lk.setAttribute("aria-pressed", koOn ? "true" : "false");
    if (le) le.setAttribute("aria-pressed", koOn ? "false" : "true");
    await loadLocaleStrings();
    applyChromeStrings();
    await refreshObjectTabsFromOverview();
    await loadHomeFeed();
    if ($("panel-watchlist").classList.contains("visible")) await loadWatchlistPanel();
    if ($("panel-research").classList.contains("visible") && objectSections[0]) await loadObjectSection(objectSections[0].id);
    if ($("panel-replay").classList.contains("visible")) await loadReplay();
    if ($("panel-advanced").classList.contains("visible")) await loadAlerts();
    if ($("panel-home").classList.contains("visible")) await loadTodaySpectrumDemo();
    const ptd2 = $("panel-today_detail");
    if (ptd2 && ptd2.classList.contains("visible")) {
      const aid = ptd2.getAttribute("data-current-asset");
      if (aid) await openTodayObjectDetail(aid);
    }
  }

  $("lang-ko").addEventListener("click", () => switchLang("ko"));
  $("lang-en").addEventListener("click", () => switchLang("en"));

  const tdb = $("today-detail-back");
  if (tdb) {
    tdb.addEventListener("click", () => {
      const p = $("panel-today_detail");
      if (p) p.removeAttribute("data-current-asset");
      showPanel("home");
      loadTodaySpectrumDemo();
    });
  }

  async function initCockpit() {
    window.__cockpitLang = cockpitLang();
    await loadLocaleStrings();
    applyChromeStrings();
    await refreshObjectTabsFromOverview();
    buildAskShortcuts();
    await refreshMeta();
    await loadHomeFeed();
    await loadJournalDecisions();
    pollNotif();
    setInterval(pollNotif, 8000);
  }

  initCockpit();
})();
