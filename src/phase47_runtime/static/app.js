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

  const COPILOT_CTX_KEY = "cockpitCopilotContext";

  function getCopilotContext() {
    try {
      const s = sessionStorage.getItem(COPILOT_CTX_KEY);
      if (!s) return null;
      const o = JSON.parse(s);
      return o && typeof o === "object" ? o : null;
    } catch (_) {
      return null;
    }
  }

  function setCopilotContext(obj) {
    try {
      if (!obj) sessionStorage.removeItem(COPILOT_CTX_KEY);
      else sessionStorage.setItem(COPILOT_CTX_KEY, JSON.stringify(obj));
    } catch (_) {}
    refreshAskContextStrip();
    refreshSandboxTodayStrip();
    refreshJournalLineageHint();
  }

  function refreshJournalLineageHint() {
    const el = $("journal-lineage-hint");
    if (!el) return;
    const ctx = getCopilotContext();
    if (
      ctx &&
      ctx.source === "today_detail" &&
      ctx.asset_id &&
      (ctx.message_snapshot_id || ctx.replay_lineage_pointer)
    ) {
      el.style.display = "block";
      el.textContent = tr("journal.lineage_bind_hint");
    } else {
      el.style.display = "none";
      el.textContent = "";
    }
  }

  function refreshAskContextStrip() {
    const strip = $("ask-context-strip");
    const line = $("ask-context-line");
    if (!strip || !line) return;
    const ctx = getCopilotContext();
    if (!ctx || !ctx.asset_id) {
      strip.style.display = "none";
      line.textContent = "";
      return;
    }
    strip.style.display = "block";
    const bits = [ctx.asset_id, ctx.spectrum_band, ctx.headline].filter(Boolean);
    line.textContent = bits.join(" · ") || String(ctx.asset_id);
  }

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
    if (name === "research") loadResearchPanel();
    if (name === "journal") {
      loadJournalDecisions();
      refreshJournalLineageHint();
    }
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
  /** Query suffix for micro-brief when timeline was loaded with Today lineage join. */
  let replayLineageQueryForMicroBrief = "";

  function renderReplayLineageContext(j, registrySurface) {
    const box = $("replay-lineage-context");
    if (!box) return;
    if (!j || !j.asset_id) {
      box.innerHTML = "";
      box.style.display = "none";
      return;
    }
    box.style.display = "block";
    const fam = escapeHtml(String(j.active_model_family_name || ""));
    const ptr = escapeHtml(String(j.replay_lineage_pointer || ""));
    const sid = escapeHtml(String(j.message_snapshot_id || ""));
    const reg = escapeHtml(String(j.linked_registry_entry_id || ""));
    const art = escapeHtml(String(j.linked_artifact_id || ""));
    const rsInner =
      registrySurface && typeof registrySurface === "object"
        ? registrySurfaceStripInnerHtml(registrySurface)
        : "";
    const rsBlock = rsInner
      ? `<div class="brief-label" style="margin-top:0.55rem">${escapeHtml(tr("replay.registry_surface_block"))}</div>` +
        `<div class="meta" style="margin-top:0.25rem;padding:0.45rem;background:#101820;border-radius:6px;border:1px solid #2a4a62;font-size:0.78rem;line-height:1.45">${rsInner}</div>`
      : "";
    box.innerHTML =
      `<div class="brief-label">${escapeHtml(tr("replay.timeline.join_title"))}</div>` +
      `<p class="meta" style="margin:0.25rem 0">${escapeHtml(tr("replay.timeline.join_intro"))}</p>` +
      `<div style="margin-top:0.35rem"><strong>${escapeHtml(tr("replay.snapshot.family"))}</strong> ${fam}</div>` +
      `<div class="mono" style="font-size:0.7rem;margin-top:0.25rem">${escapeHtml(tr("replay.timeline.pointer"))}: ${ptr}</div>` +
      `<div class="mono" style="font-size:0.7rem">${escapeHtml(tr("replay.timeline.snapshot_id"))}: ${sid}</div>` +
      `<div class="mono" style="font-size:0.7rem">${escapeHtml(tr("replay.timeline.registry"))}: ${reg}</div>` +
      `<div class="mono" style="font-size:0.7rem">${escapeHtml(tr("replay.timeline.artifact"))}: ${art}</div>` +
      rsBlock;
  }

  function renderReplayNowThen(nt) {
    const box = $("replay-now-then-frame");
    if (!box) return;
    if (!nt || nt.contract !== "REPLAY_NOW_THEN_FRAME_V1") {
      box.innerHTML = "";
      box.style.display = "none";
      return;
    }
    box.style.display = "block";
    box.innerHTML =
      `<div class="brief-label">${escapeHtml(nt.title || "")}</div>` +
      `<p class="sub" style="margin:0.35rem 0 0">${escapeHtml(nt.body_then || "")}</p>` +
      `<p class="sub" style="margin:0.35rem 0 0">${escapeHtml(nt.body_now || "")}</p>` +
      `<p class="meta" style="margin:0.45rem 0 0">${escapeHtml(nt.disclaimer || "")}</p>`;
  }

  function highlightReplayForAsset(aid) {
    if (!aid) return;
    const ul = $("replay-event-list");
    if (!ul) return;
    let hits = 0;
    ul.querySelectorAll("li").forEach((li) => {
      const la = (li.dataset && li.dataset.assetId) || "";
      const match = !!la && la === aid;
      li.classList.toggle("replay-asset-hit", match);
      if (match) hits += 1;
    });
    const first = ul.querySelector("li.replay-asset-hit");
    if (first) first.scrollIntoView({ block: "nearest", behavior: "smooth" });
    const aside = $("replay-micro-brief");
    if (aside && hits === 0) {
      aside.innerHTML =
        `<h3>${escapeHtml(tr("panel.replay.micro"))}</h3><p class="empty">${escapeHtml(tr("replay.no_events_for_asset"))}</p>`;
    }
  }

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

  function replaySandboxBannerHtml(runId) {
    return (
      `<p id="replay-sandbox-hint" class="meta" style="display:block;margin:0 0 0.5rem;padding:0.5rem;background:#121a24;border-radius:6px;border:1px solid #2d4a6a">` +
      escapeHtml(tr("replay.sandbox_context_hint")) +
      ` <code class="mono">${escapeHtml(runId)}</code></p>`
    );
  }

  async function hydrateReplayAgingBrief(assetId) {
    const aid = String(assetId || "").trim();
    const aside = $("replay-micro-brief");
    if (!aside || !aid) return;
    aside.querySelector("#replay-aging-brief")?.remove();
    const { json } = await api(
      "/api/replay/aging-brief?asset_id=" + encodeURIComponent(aid) + "&lang=" + encodeURIComponent(cockpitLang())
    );
    if (!json.ok) return;
    const box = document.createElement("div");
    box.id = "replay-aging-brief";
    box.style.marginTop = "0.85rem";
    box.style.paddingTop = "0.75rem";
    box.style.borderTop = "1px solid #2a3544";
    let h = `<div class="brief-label">${escapeHtml(tr("replay_aging.title"))}</div>`;
    h += `<p class="sub" style="margin:0.35rem 0 0.5rem">${escapeHtml(json.framing_note || "")}</p>`;
    if (json.disclaimer) h += `<p class="meta" style="font-size:0.78rem">${escapeHtml(json.disclaimer)}</p>`;
    const strip = json.horizon_spectrum_strip || [];
    if (strip.length) {
      h += `<div class="brief-label" style="margin-top:0.5rem">${escapeHtml(tr("replay_aging.horizons"))}</div><ul class="feed-list">`;
      strip.forEach((row) => {
        h +=
          "<li><span class='mono'>" +
          escapeHtml(String(row.horizon_label || row.horizon || "")) +
          "</span> · " +
          escapeHtml(String(row.spectrum_band || "")) +
          " · pos " +
          escapeHtml(row.spectrum_position != null ? String(row.spectrum_position) : "") +
          "<div class='sub'>" +
          escapeHtml(String(row.headline || "")) +
          "</div></li>";
      });
      h += "</ul>";
    }
    const dt = json.decisions_tail || [];
    if (dt.length) {
      h += `<div class="brief-label" style="margin-top:0.5rem">${escapeHtml(tr("replay_aging.decisions"))}</div><ul class="feed-list">`;
      dt.forEach((d) => {
        h +=
          "<li><span class='mono'>" +
          escapeHtml(String(d.timestamp || "").slice(0, 19)) +
          "</span> <strong>" +
          escapeHtml(String(d.decision_type || "")) +
          "</strong><div class='sub'>" +
          escapeHtml(d.snippet || "") +
          "</div></li>";
      });
      h += "</ul>";
    }
    const sb = json.sandbox_runs_tail || [];
    if (sb.length) {
      h += `<div class="brief-label" style="margin-top:0.5rem">${escapeHtml(tr("replay_aging.sandbox"))}</div><ul class="feed-list">`;
      sb.forEach((r) => {
        h +=
          "<li><span class='mono'>" +
          escapeHtml(String(r.saved_at || "").slice(0, 19)) +
          "</span> <code class='mono'>" +
          escapeHtml(r.run_id || "") +
          "</code><div class='sub'>" +
          escapeHtml(r.hypothesis_snip || "") +
          "</div></li>";
      });
      h += "</ul>";
    }
    box.innerHTML = h;
    aside.appendChild(box);
  }

  async function selectReplayEvent(eventId, liEl) {
    document.querySelectorAll("ul.replay-events li").forEach((x) => {
      x.classList.remove("selected");
      x.classList.remove("replay-asset-hit");
    });
    if (liEl) liEl.classList.add("selected");
    const { json } = await api(
      "/api/replay/micro-brief?event_id=" + encodeURIComponent(eventId) + (replayLineageQueryForMicroBrief || "")
    );
    const aside = $("replay-micro-brief");
    if (!aside) return;
    if (!json.ok) {
      const hin = aside.querySelector("#replay-sandbox-hint");
      const hintPrefix = hin ? hin.outerHTML : "";
      aside.innerHTML =
        hintPrefix + `<h3>${escapeHtml(tr("panel.replay.micro"))}</h3><p class="empty">${escapeHtml(JSON.stringify(json))}</p>`;
      return;
    }
    const m = json.micro_brief || {};
    const st = m.style_token || {};
    const hin = aside.querySelector("#replay-sandbox-hint");
    const hintPrefix = hin ? hin.outerHTML : "";
    aside.innerHTML =
      hintPrefix +
      `<h3>${escapeHtml(tr("panel.replay.micro"))}</h3>` +
      `<div class="brief-block"><div class="brief-label">${escapeHtml(m.event_type || "")}</div>` +
      `<div class="brief-value">${escapeHtml(m.title || "")}</div></div>` +
      `<div class="brief-block"><div class="brief-label">Known then</div><div class="brief-value">${escapeHtml(m.known_then || "")}</div></div>` +
      `<div class="brief-block"><div class="brief-label">Message</div><div class="brief-value">${escapeHtml(m.message_summary || "")}</div></div>` +
      `<div class="brief-block"><div class="brief-label">Evidence</div><div class="brief-value">${escapeHtml(m.evidence_summary || "")}</div></div>` +
      `<div class="brief-block"><div class="brief-label">Decision quality</div><div class="brief-value">${escapeHtml(m.decision_quality_note || "")}</div></div>` +
      `<div class="brief-block"><div class="brief-label">Outcome quality</div><div class="brief-value">${escapeHtml(m.outcome_quality_note || "")}</div></div>` +
      (m.registry_surface_v1 && typeof m.registry_surface_v1 === "object"
        ? `<div class="brief-label" style="margin-top:0.65rem">${escapeHtml(tr("replay.registry_surface_block"))}</div>` +
          `<div class="meta" style="margin-top:0.25rem;padding:0.45rem;background:#101820;border-radius:6px;border:1px solid #2a4a62;font-size:0.78rem;line-height:1.45">${registrySurfaceStripInnerHtml(
            m.registry_surface_v1
          )}</div>`
        : "") +
      (st.marker
        ? `<p class="meta" style="margin-top:0.5rem">Marker: ${escapeHtml(st.marker)} · ${escapeHtml(st.color || "")}</p>`
        : "");
    if (m.asset_id) await hydrateReplayAgingBrief(m.asset_id);
  }

  async function hydrateReplayMessageSnapshot() {
    let sid = "";
    try {
      sid = (sessionStorage.getItem("replayMessageSnapshotId") || "").trim();
      if (sid) sessionStorage.removeItem("replayMessageSnapshotId");
    } catch (_) {}
    if (!sid) return;
    const { json } = await api("/api/replay/message-snapshot?snapshot_id=" + encodeURIComponent(sid));
    const aside = $("replay-micro-brief");
    if (!aside || !json.ok) return;
    aside.querySelector("#replay-msg-snapshot")?.remove();
    const snap = json.snapshot || {};
    const fam = escapeHtml(String(snap.active_model_family || ""));
    const hl = escapeHtml(String((snap.message && snap.message.headline) || "").slice(0, 220));
    const rs =
      (json.registry_surface_v1 && typeof json.registry_surface_v1 === "object" && json.registry_surface_v1) ||
      (snap.registry_surface_v1 && typeof snap.registry_surface_v1 === "object" && snap.registry_surface_v1) ||
      null;
    const rsInner = rs ? registrySurfaceStripInnerHtml(rs) : "";
    aside.insertAdjacentHTML(
      "afterbegin",
      `<div id="replay-msg-snapshot" class="meta" style="margin:0 0 0.5rem;padding:0.5rem;background:#101820;border-radius:6px;border:1px solid #2a4a62">` +
        `<div class="brief-label">${escapeHtml(tr("replay.snapshot.title"))}</div>` +
        `<div class="mono" style="font-size:0.72rem">${escapeHtml(sid)}</div>` +
        `<div style="margin-top:0.35rem">${escapeHtml(tr("replay.snapshot.family"))}: ${fam}</div>` +
        `<div>${escapeHtml(tr("replay.snapshot.headline"))}: ${hl}</div>` +
        (rsInner
          ? `<div class="brief-label" style="margin-top:0.45rem">${escapeHtml(tr("replay.registry_surface_block"))}</div><div style="margin-top:0.25rem">${rsInner}</div>`
          : "") +
        `</div>`
    );
  }

  async function loadCounterfactual() {
    const host = $("cf-branches");
    if (!host) return;
    const [{ json: cj }, { json: tj }] = await Promise.all([
      api("/api/replay/contract"),
      api("/api/replay/counterfactual-templates?lang=" + encodeURIComponent(cockpitLang())),
    ]);
    const templates = (tj && tj.templates) || [];
    let aid = "DEMO_KR_A";
    let hz = (lastSpectrumQuery && lastSpectrumQuery.horizon) || "short";
    let mt = (lastSpectrumQuery && lastSpectrumQuery.mock_price_tick) || "0";
    try {
      const a = (sessionStorage.getItem("replayPreviewAssetId") || "").trim();
      if (a) aid = a;
    } catch (_) {}
    let html = `<p class="sub">${escapeHtml(tr("replay.cf.intro_templates"))}</p>`;
    templates.forEach((tpl) => {
      const tid = escapeHtml(tpl.template_id || "");
      html += `<div class="cf-branch cf-template"><strong>${escapeHtml(tpl.label || "")}</strong><div class="sub">${escapeHtml(
        tpl.summary || ""
      )}</div><button type="button" class="btn cf-preview" data-tpl="${tid}">${escapeHtml(tr("replay.cf.preview"))}</button><pre class="mono cf-preview-out" style="display:none;white-space:pre-wrap;font-size:0.72rem;margin-top:0.35rem"></pre></div>`;
    });
    const branches =
      (cj &&
        cj.replay_surface &&
        cj.replay_surface.counterfactual_scaffold &&
        cj.replay_surface.counterfactual_scaffold.branches) ||
      [];
    html += `<p class="meta" style="margin-top:0.75rem">Scaffold branches</p>`;
    branches.forEach((b) => {
      html += `<div class="cf-branch stub">${escapeHtml(b.label || b.id || "")}${b.state === "stub" ? " — stub" : ""}</div>`;
    });
    host.innerHTML = html;
    host.querySelectorAll("button.cf-preview").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const tid = btn.getAttribute("data-tpl") || "";
        const u =
          "/api/replay/counterfactual-preview?template_id=" +
          encodeURIComponent(tid) +
          "&asset_id=" +
          encodeURIComponent(aid) +
          "&horizon=" +
          encodeURIComponent(hz) +
          "&mock_price_tick=" +
          encodeURIComponent(mt) +
          "&lang=" +
          encodeURIComponent(cockpitLang());
        const { json } = await api(u);
        const pre = btn.parentElement && btn.parentElement.querySelector(".cf-preview-out");
        if (pre) {
          pre.style.display = "block";
          pre.textContent = JSON.stringify(json, null, 2);
        }
      });
    });
  }

  async function loadReplay() {
    let highlightAsset = "";
    let previewAsset = "";
    try {
      highlightAsset = (sessionStorage.getItem("replayHighlightAssetId") || "").trim();
      if (highlightAsset) sessionStorage.removeItem("replayHighlightAssetId");
      previewAsset = (sessionStorage.getItem("replayPreviewAssetId") || "").trim();
    } catch (_) {}
    const aidForLineage = highlightAsset || previewAsset;
    let tlPath = "/api/replay/timeline";
    if (aidForLineage) {
      const hz = (lastSpectrumQuery && lastSpectrumQuery.horizon) || "short";
      const mt = (lastSpectrumQuery && lastSpectrumQuery.mock_price_tick) || "0";
      tlPath =
        "/api/replay/timeline?asset_id=" +
        encodeURIComponent(aidForLineage) +
        "&horizon=" +
        encodeURIComponent(hz) +
        "&mock_price_tick=" +
        encodeURIComponent(mt) +
        "&lang=" +
        encodeURIComponent(cockpitLang());
    }
    const { json } = await api(tlPath);
    replayLineageQueryForMicroBrief = "";
    if (!json.ok) {
      renderReplayLineageContext(null, null);
      renderReplayNowThen(null);
      $("replay-event-list").innerHTML = `<li class='empty'>${escapeHtml(json.error || "error")}</li>`;
      return;
    }
    const lj = json.today_lineage_join_v1;
    if (lj && lj.asset_id) {
      const mt0 = (lastSpectrumQuery && lastSpectrumQuery.mock_price_tick) || "0";
      replayLineageQueryForMicroBrief =
        "&asset_id=" +
        encodeURIComponent(String(lj.asset_id)) +
        "&horizon=" +
        encodeURIComponent(String(lj.horizon || "short")) +
        "&mock_price_tick=" +
        encodeURIComponent(String(mt0)) +
        "&lang=" +
        encodeURIComponent(cockpitLang());
    }
    renderReplayLineageContext(lj, json.registry_surface_v1);
    renderReplayNowThen(json.now_then_frame_v1);
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
      li.dataset.assetId = String(ev.asset_id || "");
      const aid = String(ev.asset_id || "").trim();
      const badge = aid
        ? `<br/><span class="mono" style="font-size:0.68rem;color:var(--muted)">${escapeHtml(tr("replay.asset_badge"))}: ${escapeHtml(aid)}</span>`
        : "";
      li.innerHTML =
        `<span class="ev-type">${escapeHtml(ev.event_type)}</span><br/>${escapeHtml(ev.title || "")}<br/><span class="mono" style="font-size:0.72rem">${escapeHtml(
          (ev.timestamp_utc || "").slice(0, 19)
        )}</span>` +
        badge;
      li.addEventListener("click", () => selectReplayEvent(ev.event_id, li));
      ul.appendChild(li);
    });
    let pending = highlightAsset;
    if (pending) {
      const tl = $("replay-sub-timeline");
      const cf = $("replay-sub-counterfactual");
      if (tl) tl.style.display = "block";
      if (cf) cf.style.display = "none";
      document.querySelectorAll("#replay-subtabs button[data-replay-sub]").forEach((b) => {
        b.classList.toggle("on", b.getAttribute("data-replay-sub") === "timeline");
      });
      highlightReplayForAsset(pending);
    }
    const aside0 = $("replay-micro-brief");
    if (aside0) {
      aside0.querySelector("#replay-aging-brief")?.remove();
      aside0.querySelector("#replay-sandbox-hint")?.remove();
      aside0.querySelector("#replay-msg-snapshot")?.remove();
      let sbRun = "";
      try {
        sbRun = (sessionStorage.getItem("sandboxContextRunId") || "").trim();
        if (sbRun) sessionStorage.removeItem("sandboxContextRunId");
      } catch (_) {
        sbRun = "";
      }
      if (sbRun) {
        aside0.insertAdjacentHTML("afterbegin", replaySandboxBannerHtml(sbRun));
      }
      await hydrateReplayMessageSnapshot();
      if (pending) await hydrateReplayAgingBrief(pending);
    }
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

  function registrySurfaceStripInnerHtml(rs) {
    if (!rs || typeof rs !== "object" || rs.contract !== "TODAY_REGISTRY_SURFACE_V1") return "";
    const eid = escapeHtml(String(rs.registry_entry_id || ""));
    const st = escapeHtml(String(rs.status || ""));
    const hz = escapeHtml(String(rs.horizon || ""));
    const afn = escapeHtml(String(rs.active_model_family_name || ""));
    const atf = escapeHtml(String(rs.active_thesis_family || ""));
    const aaid = escapeHtml(String(rs.active_artifact_id || ""));
    const crs = Array.isArray(rs.challengers_resolved) ? rs.challengers_resolved : [];
    let chHtml = "";
    if (!crs.length) {
      chHtml = `<span class="meta">${escapeHtml(tr("spectrum.challenger_none"))}</span>`;
    } else {
      chHtml = crs
        .map((c) => {
          const aid = escapeHtml(String(c.artifact_id || ""));
          const tf = escapeHtml(String(c.thesis_family || ""));
          return `<span class="mono" style="margin-right:0.65rem;display:inline-block">${aid} · ${escapeHtml(tr("spectrum.thesis_family"))}: ${tf}</span>`;
        })
        .join("");
    }
    return (
      `<div><strong>${escapeHtml(tr("spectrum.registry_surface_title"))}</strong> ` +
      `<span class="mono">${eid}</span> · <span class="mono">${hz}</span> · ${escapeHtml(tr("spectrum.registry_status"))}: <span class="mono">${st}</span></div>` +
      `<div style="margin-top:0.35rem">${escapeHtml(tr("spectrum.registry_active_row"))}: <span class="mono">${afn}</span> · ${escapeHtml(tr("spectrum.thesis_family"))}: <span class="mono">${atf}</span> · artifact <span class="mono">${aaid}</span></div>` +
      `<div style="margin-top:0.35rem">${escapeHtml(tr("spectrum.challenger_strip"))}: ${chHtml}</div>`
    );
  }

  function refreshResearchRegistryStrip() {
    const el = $("research-registry-strip");
    if (!el) return;
    const sp = window.__lastSpectrumPayload;
    const rs = sp && sp.registry_surface_v1 && typeof sp.registry_surface_v1 === "object" ? sp.registry_surface_v1 : null;
    const inner = registrySurfaceStripInnerHtml(rs || {});
    if (!inner) {
      el.style.display = "none";
      el.innerHTML = "";
      return;
    }
    el.style.display = "block";
    el.innerHTML =
      `<p class="meta" style="margin:0 0 0.5rem">${escapeHtml(tr("panel.research.registry_strip_intro"))}</p>` + inner;
  }

  function openAskWithPrompt(promptText, autoSubmit) {
    const ta = $("conv-in");
    if (ta) ta.value = String(promptText || "").trim();
    showPanel("ask_ai");
    syncAskAiFromFeed();
    if (autoSubmit) submitConv();
  }

  async function hydrateResearchDeferredPanel() {
    const wrap = $("research-deferred-context");
    const empty = $("research-deferred-empty");
    const inner = $("research-deferred-inner");
    const chips = $("research-ask-chips");
    if (!wrap || !inner || !empty) return;
    let ctx = null;
    try {
      ctx = JSON.parse(sessionStorage.getItem("metis_last_research_context") || "null");
    } catch (_) {
      ctx = null;
    }
    const sbAid = ($("sandbox-asset-id") && $("sandbox-asset-id").value.trim()) || "";
    const aid = (ctx && ctx.asset_id && String(ctx.asset_id).trim()) || sbAid;
    const hz = (ctx && ctx.horizon && String(ctx.horizon)) || (lastSpectrumQuery && lastSpectrumQuery.horizon) || "short";
    const mt = (ctx && ctx.mock_price_tick != null && String(ctx.mock_price_tick)) || (lastSpectrumQuery && lastSpectrumQuery.mock_price_tick) || "0";
    if (!aid) {
      wrap.style.display = "none";
      inner.innerHTML = "";
      empty.style.display = "block";
      if (chips) chips.innerHTML = "";
      return;
    }
    empty.style.display = "none";
    wrap.style.display = "block";
    const lg = encodeURIComponent(cockpitLang());
    const { json } = await api(
      "/api/today/object?asset_id=" +
        encodeURIComponent(aid) +
        "&horizon=" +
        encodeURIComponent(hz) +
        "&mock_price_tick=" +
        encodeURIComponent(mt) +
        "&lang=" +
        lg
    );
    if (!json.ok) {
      inner.innerHTML = `<p class="empty">${escapeHtml(JSON.stringify(json))}</p>`;
      if (chips) chips.innerHTML = "";
      return;
    }
    inner.innerHTML = renderTodayObjectDetailHtml(json);
    if (!chips) return;
    chips.innerHTML =
      `<span class="meta">${escapeHtml(tr("research.ask_chips_hint"))}</span> ` +
      `<button type="button" class="btn research-ask-chip" data-prompt="why now">${escapeHtml(tr("research.ask_chip_why_now"))}</button> ` +
      `<button type="button" class="btn research-ask-chip" data-prompt="what changed">${escapeHtml(tr("research.ask_chip_what_changed"))}</button> ` +
      `<button type="button" class="btn research-ask-chip" data-prompt="what to watch">${escapeHtml(tr("research.ask_chip_what_to_watch"))}</button>`;
    chips.querySelectorAll(".research-ask-chip").forEach((btn) => {
      btn.addEventListener("click", () => openAskWithPrompt(btn.getAttribute("data-prompt") || "", true));
    });
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
    window.__lastSpectrumPayload = json;
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
    function quintileLabel(q) {
      const key = "spectrum.quintile_" + String(q || "neutral");
      const lab = tr(key);
      return lab === key ? String(q || "") : lab;
    }
    function rankMoveLabel(m) {
      if (m === "up") return tr("spectrum.rank_movement_up");
      if (m === "down") return tr("spectrum.rank_movement_down");
      if (m === "unchanged") return tr("spectrum.rank_movement_unchanged");
      return tr("spectrum.rank_movement_steady");
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
      if (prefs.sortVal === "watchlist_first") {
        const wa = watchIdSet.has(String(a.asset_id || "")) ? 0 : 1;
        const wb = watchIdSet.has(String(b.asset_id || "")) ? 0 : 1;
        if (wa !== wb) return wa - wb;
      }
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
      rows = `<tr><td colspan="8" class="empty">${escapeHtml(emptyMsg)}</td></tr>`;
    } else {
      rowObjs.forEach((r) => {
        const b = r.spectrum_band || "center";
        const q = r.spectrum_quintile || "neutral";
        const qLab = escapeHtml(quintileLabel(q));
        const msg = r.message || {};
        const head = escapeHtml(msg.headline || "");
        const sub = escapeHtml(msg.one_line_take || "");
        const aid = escapeHtml(r.asset_id || "");
        const rk = r.rank_index != null ? escapeHtml(String(r.rank_index)) : "—";
        const rkt = r.rank_total != null ? escapeHtml(String(r.rank_total)) : "";
        const rm = escapeHtml(rankMoveLabel(r.rank_movement || "steady"));
        const wcRaw = String(r.what_changed || "");
        const wcEsc = escapeHtml(wcRaw);
        const titleAttr = wcEsc.replace(/"/g, "&quot;");
        const ratRaw = String(r.rationale_summary || "").trim();
        const rat = escapeHtml(ratRaw);
        const ratDetails = ratRaw
          ? `<details class="spectrum-rationale"><summary>${escapeHtml(tr("spectrum.expand_rationale"))}</summary><div>${rat}</div></details>`
          : "";
        const whyRaw = String(msg.why_now || "").trim();
        const whyLine = whyRaw
          ? `<span class="spectrum-msg-why meta" style="display:block;margin-top:0.22rem">${escapeHtml(tr("spectrum.col_why_now"))}: ${escapeHtml(
              whyRaw.slice(0, 220)
            )}</span>`
          : "";
        rows +=
          "<tr><td class='mono'>" +
          `<button type="button" class="spectrum-asset-btn" data-asset="${aid}">${aid}</button>` +
          "</td><td>" +
          bandDot(b) +
          escapeHtml(bandLabel(b)) +
          `<span class="meta"> · ${qLab}</span>` +
          "</td><td>" +
          escapeHtml(String(r.spectrum_position ?? "")) +
          "</td><td class='mono'>" +
          rk +
          (rkt ? `<span class='meta'>/${rkt}</span>` : "") +
          "</td><td>" +
          rm +
          "</td><td>" +
          escapeHtml(r.valuation_tension || "") +
          "</td><td><span class='spectrum-msg-head'>" +
          head +
          "</span><span class='spectrum-msg-sub'>" +
          sub +
          "</span>" +
          whyLine +
          ratDetails +
          "</td><td>" +
          (wcEsc ? `<span class="wc-chip" title="${titleAttr}">${wcEsc}</span>` : `<span class="wc-chip">—</span>`) +
          "</td></tr>";
      });
    }
    const sd = prefs.sortVal === "position_desc" ? " selected" : "";
    const sa = prefs.sortVal === "position_asc" ? " selected" : "";
    const sz = prefs.sortVal === "asset_az" ? " selected" : "";
    const swf = prefs.sortVal === "watchlist_first" ? " selected" : "";
    const wChk = prefs.watchOnly ? " checked" : "";
    const wDis = watchFilterDisabled ? " disabled" : "";
    const regHeroInner = registrySurfaceStripInnerHtml(json.registry_surface_v1 || {});
    wrap.innerHTML =
      `<div class="feed-card today-hero-card"><h3>${escapeHtml(tr("spectrum.hero_title"))}</h3>` +
      `<p class="sub">${escapeHtml(tr("spectrum.demo_meta"))}</p>` +
      `<p class="meta">${escapeHtml(tr("spectrum.as_of"))}: ${escapeHtml(json.as_of_utc || "—")} · ${escapeHtml(tr("spectrum.model_family"))}: <span class="mono">${escapeHtml(
        json.active_model_family || ""
      )}</span></p>` +
      (regHeroInner
        ? `<div class="meta registry-hero-strip" style="margin:0.65rem 0;padding:0.55rem 0.7rem;background:#0d141a;border:1px solid #2a4a62;border-radius:8px;font-size:0.82rem;line-height:1.45">${regHeroInner}</div>`
        : "") +
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
      `<option value="watchlist_first"${swf}>${escapeHtml(tr("spectrum.sort_watchlist_first"))}</option>` +
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
      `<th style="text-align:left;border-bottom:1px solid #2a3544">${escapeHtml(tr("spectrum.col_rank"))}</th>` +
      `<th style="text-align:left;border-bottom:1px solid #2a3544">${escapeHtml(tr("spectrum.col_move"))}</th>` +
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
    refreshResearchRegistryStrip();
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
    const rs = j.registry_surface_v1 && typeof j.registry_surface_v1 === "object" ? j.registry_surface_v1 : null;
    const rsInner = registrySurfaceStripInnerHtml(rs || {});
    const registryBlock = rsInner
      ? `<div class="mir-block"><h4>${escapeHtml(tr("today_detail.section_registry"))}</h4><div class="meta" style="padding:0.45rem 0.55rem;background:#101820;border:1px solid #2a4a62;border-radius:8px;font-size:0.82rem;line-height:1.45">${rsInner}</div></div>`
      : "";
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
    const spectrumBlock =
      `<p style="margin:0 0 0.4rem;font-size:0.78rem;color:var(--muted)"><strong>${escapeHtml(tr("today_detail.spectrum_ctx"))}</strong></p>` +
      `<div class="mir-kv"><span class="k">${escapeHtml(tr("spectrum.col_band"))}</span>${escapeHtml(spec.spectrum_band || "")} · ${escapeHtml(
        tr("spectrum.col_position")
      )}: ${escapeHtml(String(spec.spectrum_position ?? ""))}</div>` +
      `<div class="mir-kv"><span class="k">${escapeHtml(tr("spectrum.col_tension"))}</span>${escapeHtml(spec.valuation_tension || "")}</div>` +
      `<div class="mir-kv"><span class="k">${escapeHtml(tr("spectrum.col_rationale"))}</span>${escapeHtml(spec.rationale_summary || "")}</div>` +
      `<div class="mir-kv"><span class="k">${escapeHtml(tr("spectrum.col_changed"))}</span>${escapeHtml(spec.what_changed || "")}</div>`;
    const infBlock =
      spectrumBlock +
      `<div class="mir-kv"><span class="k">${escapeHtml(tr("today_detail.supporting"))}</span><ul class="feed-list">${ulItems(
        inf.supporting_signals
      )}</ul></div>` +
      `<div class="mir-kv"><span class="k">${escapeHtml(tr("today_detail.opposing"))}</span><ul class="feed-list">${ulItems(
        inf.opposing_signals
      )}</ul></div>` +
      kv("today_detail.evidence", inf.evidence_summary) +
      kv("today_detail.data_note", inf.data_layer_note);
    const prefillEnc = encodeURIComponent(links.prefill_ask_ai || "");
    const lens = Array.isArray(res.horizon_lens_compare) ? res.horizon_lens_compare : [];
    const lensTable =
      lens.length > 0
        ? `<div class="mir-kv" style="margin-top:0.45rem"><span class="k">${escapeHtml(tr("today_detail.horizon_lens_title"))}</span>` +
          `<table style="width:100%;font-size:0.82rem;margin-top:0.25rem;border-collapse:collapse"><thead><tr>` +
          `<th style="text-align:left;border-bottom:1px solid #2a3544">${escapeHtml(tr("today_detail.horizon_lens_col"))}</th>` +
          `<th style="text-align:left;border-bottom:1px solid #2a3544">${escapeHtml(tr("spectrum.col_band"))}</th>` +
          `<th style="text-align:left;border-bottom:1px solid #2a3544">${escapeHtml(tr("spectrum.col_position"))}</th>` +
          `<th style="text-align:left;border-bottom:1px solid #2a3544">${escapeHtml(tr("spectrum.col_message"))}</th>` +
          `</tr></thead><tbody>` +
          lens
            .map(
              (row) =>
                `<tr><td class="mono">${escapeHtml(String(row.horizon_label || row.horizon || ""))}</td>` +
                `<td>${escapeHtml(String(row.spectrum_band || ""))}</td>` +
                `<td>${escapeHtml(row.spectrum_position != null ? String(row.spectrum_position) : "")}</td>` +
                `<td>${escapeHtml(String(row.headline || "").slice(0, 140))}</td></tr>`
            )
            .join("") +
          `</tbody></table></div>`
        : "";
    const dis = res.disagreement_preserving && typeof res.disagreement_preserving.note === "string" ? res.disagreement_preserving.note : "";
    const disBlock = dis
      ? `<div class="mir-kv" style="margin-top:0.45rem"><span class="k">${escapeHtml(tr("today_detail.disagreement_note"))}</span>${escapeHtml(dis)}</div>`
      : "";
    const resBlock =
      `<div class="mir-kv"><span class="k">${escapeHtml(tr("today_detail.deeper_rationale"))}</span>${escapeHtml(
        res.deeper_rationale || ""
      )}</div>` +
      `<div class="mir-kv"><span class="k">${escapeHtml(tr("spectrum.model_family"))}</span>${escapeHtml(
        res.model_family_context || ""
      )}</div>` +
      disBlock +
      lensTable +
      `<div class="row" style="margin-top:0.75rem">` +
      `<button type="button" class="btn" id="today-detail-btn-replay">${escapeHtml(tr("today_detail.link_replay"))}</button>` +
      `<button type="button" class="btn" id="today-detail-btn-journal">${escapeHtml(tr("today_detail.link_journal"))}</button>` +
      `<button type="button" class="btn" id="today-detail-btn-sandbox">${escapeHtml(tr("today_detail.link_sandbox"))}</button>` +
      `<button type="button" class="btn btn-primary" id="today-detail-btn-ask" data-prefill="${prefillEnc}">${escapeHtml(
        tr("today_detail.link_ask")
      )}</button>` +
      `</div>`;

    return (
      `<p class="meta">${metaLine}</p>` +
      `<div class="mir-block"><h4>${escapeHtml(tr("today_detail.section_message"))}</h4>${msgBlock}</div>` +
      registryBlock +
      `<div class="mir-block"><h4>${escapeHtml(tr("today_detail.section_information"))}</h4>${infBlock}</div>` +
      `<div class="mir-block"><h4>${escapeHtml(tr("today_detail.section_research"))}</h4>${resBlock}</div>`
    );
  }

  function wireTodayDetailActions() {
    const br = $("today-detail-btn-replay");
    if (br)
      br.addEventListener("click", () => {
        const p = $("panel-today_detail");
        const aid = (p && p.getAttribute("data-current-asset")) || "";
        const sid = (p && p.getAttribute("data-message-snapshot-id")) || "";
        try {
          if (aid) sessionStorage.setItem("replayHighlightAssetId", aid);
          if (sid) sessionStorage.setItem("replayMessageSnapshotId", sid);
          if (aid) sessionStorage.setItem("replayPreviewAssetId", aid);
        } catch (_) {}
        showPanel("replay");
      });
    const bj = $("today-detail-btn-journal");
    if (bj) {
      bj.addEventListener("click", () => {
        const p = $("panel-today_detail");
        const aid = (p && p.getAttribute("data-current-asset")) || "";
        const ra = $("rec-aid");
        if (ra && aid) ra.value = aid;
        refreshJournalLineageHint();
        showPanel("journal");
      });
    }
    const bs = $("today-detail-btn-sandbox");
    if (bs) {
      bs.addEventListener("click", () => {
        const hyp = $("sandbox-hypothesis");
        if (hyp) hyp.value = tr("sandbox.prefill_stub");
        showPanel("research");
      });
    }
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
    const msg = json.message && typeof json.message === "object" ? json.message : {};
    const headline = String(msg.headline || "").slice(0, 240);
    const oneLine = String(msg.one_line_take || "").slice(0, 300);
    const sp = json.spectrum && typeof json.spectrum === "object" ? json.spectrum : {};
    const rj = json.replay_lineage_join_v1 && typeof json.replay_lineage_join_v1 === "object" ? json.replay_lineage_join_v1 : {};
    const rs0 =
      json.registry_surface_v1 && typeof json.registry_surface_v1 === "object" ? json.registry_surface_v1 : {};
    const crs = Array.isArray(rs0.challengers_resolved) ? rs0.challengers_resolved : [];
    const chH = crs
      .map((c) => `${String(c.artifact_id || "").slice(0, 64)}:${String(c.thesis_family || "").slice(0, 48)}`)
      .filter((s) => s.length > 1)
      .join("; ");
    setCopilotContext({
      source: "today_detail",
      asset_id: String(json.asset_id || assetId),
      horizon: String(json.horizon || ""),
      horizon_label: String(json.horizon_label || ""),
      active_model_family: String(json.active_model_family || ""),
      as_of_utc: String(json.as_of_utc || ""),
      spectrum_band: sp.spectrum_band != null ? String(sp.spectrum_band) : "",
      spectrum_quintile: sp.spectrum_quintile != null ? String(sp.spectrum_quintile) : "",
      spectrum_position: sp.spectrum_position != null ? String(sp.spectrum_position) : "",
      rank_index: sp.rank_index != null ? String(sp.rank_index) : "",
      rank_movement: sp.rank_movement != null ? String(sp.rank_movement) : "",
      headline,
      message_summary: oneLine || headline,
      valuation_tension: sp.valuation_tension != null ? String(sp.valuation_tension) : "",
      why_now: msg.why_now != null ? String(msg.why_now) : "",
      what_to_watch: msg.what_to_watch != null ? String(msg.what_to_watch) : "",
      what_remains_unproven: msg.what_remains_unproven != null ? String(msg.what_remains_unproven) : "",
      replay_lineage_pointer: rj.replay_lineage_pointer != null ? String(rj.replay_lineage_pointer) : "",
      message_snapshot_id: rj.message_snapshot_id != null ? String(rj.message_snapshot_id) : "",
      linked_registry_entry_id: rj.linked_registry_entry_id != null ? String(rj.linked_registry_entry_id) : "",
      linked_artifact_id: rj.linked_artifact_id != null ? String(rj.linked_artifact_id) : "",
      challenger_hint: chH.slice(0, 500),
    });
    if (ptd) {
      ptd.setAttribute("data-current-asset", assetId);
      const sid = rj.message_snapshot_id != null ? String(rj.message_snapshot_id) : "";
      if (sid) ptd.setAttribute("data-message-snapshot-id", sid);
      else ptd.removeAttribute("data-message-snapshot-id");
      try {
        sessionStorage.setItem("replayPreviewAssetId", String(json.asset_id || assetId));
        sessionStorage.setItem(
          "metis_last_research_context",
          JSON.stringify({
            asset_id: String(json.asset_id || assetId),
            horizon: String(json.horizon || q.horizon || "short"),
            mock_price_tick: String(q.mock_price_tick || "0"),
          })
        );
      } catch (_) {}
    }
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

    const fdp = json.frozen_demo_pack;
    if (fdp && fdp.ok && fdp.pack) {
      const pk = fdp.pack;
      const steps = fdp.investor_demo_steps_resolved || [];
      let stepsHtml = '<ol style="margin:0.35rem 0 0 1.1rem;padding:0;font-size:0.88rem">';
      steps.forEach((s) => {
        stepsHtml += `<li>${escapeHtml(s.label || s.id || "")}</li>`;
      });
      stepsHtml += "</ol>";
      const pod = fdp.price_overlay_demo || {};
      const disc = String(pk.disclaimer || "").slice(0, 360);
      parts.push(
        `<div class="feed-card" style="border-color:#3d5a80">` +
          `<h3>${escapeHtml(tr("home.demo.pack_title"))}</h3>` +
          `<p class="meta"><span class="mono">${escapeHtml(String(pk.pack_id || ""))}</span> · ${escapeHtml(String(pk.as_of_utc || ""))}</p>` +
          `<p class="sub">${escapeHtml(tr("home.demo.pack_intro"))}</p>` +
          `<div class="brief-label" style="margin-top:0.5rem">${escapeHtml(tr("home.demo.investor_route"))}</div>` +
          stepsHtml +
          `<p class="meta" style="margin-top:0.5rem">${escapeHtml(tr("home.demo.price_overlay"))}: ` +
          `<span class="mono">${escapeHtml(String(pod.query_param || "mock_price_tick"))}=` +
          `${escapeHtml(String(pod.baseline_value || "0"))}</span> / ` +
          `<span class="mono">${escapeHtml(String(pod.shock_value || "1"))}</span></p>` +
          (disc ? `<p class="sub" style="margin-top:0.4rem">${escapeHtml(disc)}</p>` : "") +
          `</div>`
      );
    }

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
      const sid = String(d.message_snapshot_id || "").trim();
      const snapLine = sid
        ? `<div class="mono" style="font-size:0.7rem;margin-top:0.2rem">${escapeHtml(tr("journal.card_snapshot"))}: ${escapeHtml(
            sid.length > 56 ? sid.slice(0, 56) + "…" : sid
          )}</div>`
        : "";
      jhtml +=
        `<li><span class="mono">${escapeHtml(d.timestamp)}</span> · <strong>${escapeHtml(d.asset_id)}</strong> · ${escapeHtml(
          d.action_framing_plain || d.decision_type
        )}<div class="sub">${escapeHtml(d.why_short || "")}</div>${snapLine}<div class="sub">${escapeHtml(d.replay_hint || "")}</div></li>`;
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

  function hydrateWatchlistReorder(initialIds) {
    const ul = $("wl-reorder-ul");
    const saveBtn = $("wl-reorder-save");
    if (!ul || !saveBtn || !Array.isArray(initialIds) || initialIds.length < 2) return;
    let draft = initialIds.slice();
    function renderList() {
      ul.innerHTML = "";
      draft.forEach((id, idx) => {
        const li = document.createElement("li");
        li.className = "wl-reorder-row";
        li.style.cssText = "display:flex;align-items:center;gap:0.35rem;flex-wrap:wrap;margin:0.25rem 0";
        const lab = document.createElement("span");
        lab.className = "mono";
        lab.textContent = id;
        const up = document.createElement("button");
        up.type = "button";
        up.className = "btn";
        up.textContent = tr("watch.move_up");
        up.disabled = idx === 0;
        up.addEventListener("click", () => {
          if (idx > 0) {
            const t = draft[idx - 1];
            draft[idx - 1] = draft[idx];
            draft[idx] = t;
            renderList();
          }
        });
        const dn = document.createElement("button");
        dn.type = "button";
        dn.className = "btn";
        dn.textContent = tr("watch.move_down");
        dn.disabled = idx === draft.length - 1;
        dn.addEventListener("click", () => {
          if (idx < draft.length - 1) {
            const t = draft[idx + 1];
            draft[idx + 1] = draft[idx];
            draft[idx] = t;
            renderList();
          }
        });
        li.appendChild(lab);
        li.appendChild(up);
        li.appendChild(dn);
        ul.appendChild(li);
      });
    }
    renderList();
    saveBtn.onclick = async () => {
      const url = withLang("/api/today/watchlist-order");
      const r = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ordered_asset_ids: draft }),
      });
      const j = await r.json().catch(() => ({}));
      if (!r.ok || !j.ok) {
        window.alert(tr("watch.save_failed"));
        return;
      }
      await loadHomeFeed();
      await loadWatchlistPanel();
    };
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
    const roIds = Array.isArray(wb.reorderable_asset_ids) ? wb.reorderable_asset_ids.slice() : [];
    const blocks = [];
    if (wempty) {
      blocks.push(
        `<div class="feed-card"><h3>${escapeHtml(wempty.title)}</h3><p class="sub">${escapeHtml(wempty.why)}</p><p class="sub"><em>${escapeHtml(wempty.fills_when)}</em></p></div>`
      );
    }
    if (roIds.length >= 2) {
      blocks.push(
        `<div class="feed-card"><h3>${escapeHtml(tr("watch.reorder_title"))}</h3>` +
          `<p class="meta">${escapeHtml(tr("watch.reorder_explain"))}</p>` +
          `<ul class="feed-list" id="wl-reorder-ul" style="list-style:none;padding-left:0"></ul>` +
          `<button type="button" class="btn" id="wl-reorder-save" style="margin-top:0.5rem">${escapeHtml(tr("watch.save_order"))}</button>` +
          `</div>`
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
    hydrateWatchlistReorder(roIds);
  }

  function syncAskAiFromFeed() {
    const ab = lastFeed && lastFeed.ask_ai_brief;
    $("ask-brief-line").textContent = (ab && ab.daily_line) || "Load Home once to refresh the copilot brief.";
    buildAskShortcuts();
    refreshAskContextStrip();
  }

  function refreshSandboxTodayStrip() {
    const strip = $("sandbox-today-strip");
    const line = $("sandbox-today-line");
    if (!strip || !line) return;
    const ctx = getCopilotContext();
    if (!ctx || !ctx.asset_id) {
      strip.style.display = "none";
      line.textContent = "";
      return;
    }
    strip.style.display = "block";
    line.textContent = [ctx.asset_id, ctx.spectrum_band, ctx.headline].filter(Boolean).join(" · ");
  }

  function syncSandboxFormFromContext() {
    const ctx = getCopilotContext();
    const aidEl = $("sandbox-asset-id");
    const hzEl = $("sandbox-horizon");
    const mtEl = $("sandbox-mock-tick");
    if (ctx && ctx.asset_id && aidEl && !String(aidEl.value || "").trim()) {
      aidEl.value = ctx.asset_id;
    }
    if (ctx && ctx.horizon && hzEl) {
      const v = String(ctx.horizon).toLowerCase();
      if (["short", "medium", "medium_long", "long"].includes(v)) hzEl.value = v;
    }
    if (mtEl) mtEl.value = lastSpectrumQuery.mock_price_tick || "0";
    refreshSandboxTodayStrip();
  }

  function loadResearchPanel() {
    syncSandboxFormFromContext();
    loadSandboxRunsList();
    refreshResearchRegistryStrip();
    hydrateResearchDeferredPanel();
  }

  async function loadSandboxRunsList() {
    const ul = $("sandbox-runs-list");
    if (!ul) return;
    const lg = encodeURIComponent(cockpitLang());
    const { json } = await api("/api/sandbox/runs?limit=25&lang=" + lg);
    if (!json.ok) {
      ul.innerHTML = `<li class="sub">${escapeHtml(JSON.stringify(json))}</li>`;
      return;
    }
    const runs = json.runs || [];
    if (!runs.length) {
      ul.innerHTML = `<li class="sub">${escapeHtml(tr("sandbox.empty_runs"))}</li>`;
      return;
    }
    ul.innerHTML = runs
      .map((r) => {
        const ie = r.inputs_echo || {};
        const fullH = String(ie.hypothesis || "");
        const hyp = fullH.slice(0, 120);
        const tail = fullH.length > 120 ? "…" : "";
        const rid = escapeHtml(r.run_id || "");
        const runIdAttr = escapeHtml(String(r.run_id || ""));
        const when = escapeHtml(String(r.saved_at || "").slice(0, 19));
        const aid = ie.asset_id ? ` · <span class="mono">${escapeHtml(String(ie.asset_id))}</span>` : "";
        return (
          "<li style='list-style:none;margin:0;padding:0'>" +
          "<button type='button' class='btn sandbox-run-pick' style='width:100%;text-align:left;font-size:inherit;margin:0.12rem 0;padding:0.45rem 0.55rem'" +
          " data-run-id='" +
          runIdAttr +
          "'><span class='mono'>" +
          when +
          "</span> <strong class='mono'>" +
          rid +
          "</strong>" +
          aid +
          "<div class='sub' style='margin-top:0.2rem'>" +
          escapeHtml(hyp) +
          tail +
          "</div></button></li>"
        );
      })
      .join("");
  }

  function applySandboxLedgerToForm(run) {
    const ie = run.inputs_echo || {};
    const h = $("sandbox-hypothesis");
    if (h && ie.hypothesis) h.value = String(ie.hypothesis);
    const a = $("sandbox-asset-id");
    if (a && ie.asset_id) a.value = String(ie.asset_id);
    const hz = $("sandbox-horizon");
    if (hz && ie.horizon) {
      const v = String(ie.horizon).toLowerCase();
      if (["short", "medium", "medium_long", "long"].includes(v)) hz.value = v;
    }
    const pit = $("sandbox-pit-mode");
    if (pit && ie.pit_mode && (ie.pit_mode === "snapshot" || ie.pit_mode === "pit_stub")) pit.value = ie.pit_mode;
    const mt = $("sandbox-mock-tick");
    if (mt && ie.mock_price_tick != null) mt.value = String(ie.mock_price_tick) === "1" ? "1" : "0";
  }

  function renderLedgerRunHtml(run) {
    const bullets = run.summary_bullets || [];
    const sample = run.horizon_scan_sample || [];
    const parts = [];
    parts.push(
      `<div class="row" style="justify-content:space-between;align-items:center;flex-wrap:wrap;gap:0.5rem;margin-bottom:0.35rem">` +
        `<strong>${escapeHtml(tr("sandbox.ledger_readonly"))}</strong>` +
        `<span class="mono">${escapeHtml(run.run_id || "")}</span></div>`
    );
    parts.push(`<p class="meta mono" style="margin:0 0 0.5rem">${escapeHtml(String(run.saved_at || "").slice(0, 19))}</p>`);
    parts.push("<ul style='margin:0.25rem 0 0.5rem 1.1rem'>" + bullets.map((b) => "<li>" + escapeHtml(b) + "</li>").join("") + "</ul>");
    if (sample.length) {
      parts.push(`<div class="brief-label" style="margin-top:0.5rem">${escapeHtml(tr("sandbox.scan_title"))}</div>`);
      parts.push(
        "<table><thead><tr>" +
          ["sandbox.col_horizon", "sandbox.col_band", "sandbox.col_pos", "sandbox.col_headline"]
            .map((k) => "<th>" + escapeHtml(tr(k)) + "</th>")
            .join("") +
          "</tr></thead><tbody>"
      );
      sample.forEach((row) => {
        parts.push(
          "<tr><td>" +
            escapeHtml(String(row.horizon_label || row.horizon || "")) +
            "</td><td>" +
            escapeHtml(String(row.spectrum_band ?? "")) +
            "</td><td class='mono'>" +
            escapeHtml(row.spectrum_position != null ? String(row.spectrum_position) : "") +
            "</td><td>" +
            escapeHtml(String(row.headline || "")) +
            "</td></tr>"
        );
      });
      parts.push("</tbody></table>");
    }
    if (run.pit_note) parts.push(`<p class="meta" style="margin-top:0.5rem">${escapeHtml(run.pit_note)}</p>`);
    parts.push(
      `<div class="shortcut-row" style="margin-top:0.65rem">` +
        `<button type="button" class="btn" id="btn-ledger-apply">${escapeHtml(tr("sandbox.apply_to_form"))}</button>` +
        `<button type="button" class="btn" id="btn-ledger-replay">${escapeHtml(tr("sandbox.open_replay"))}</button>` +
        `<button type="button" class="btn" id="btn-ledger-close">${escapeHtml(tr("sandbox.close_ledger_detail"))}</button>` +
        `</div>`
    );
    return parts.join("");
  }

  async function showSandboxLedgerDetail(runId) {
    const box = $("sandbox-ledger-detail");
    if (!box) return;
    const lg = encodeURIComponent(cockpitLang());
    const { json } = await api("/api/sandbox/run?run_id=" + encodeURIComponent(runId) + "&lang=" + lg);
    if (!json.ok) {
      box.style.display = "block";
      box.innerHTML = `<pre class="mono">${escapeHtml(JSON.stringify(json))}</pre>`;
      return;
    }
    const run = json.run || {};
    box.style.display = "block";
    box.innerHTML = renderLedgerRunHtml(run);
    const closeLedger = () => {
      box.style.display = "none";
      box.innerHTML = "";
    };
    box.querySelector("#btn-ledger-close")?.addEventListener("click", closeLedger);
    box.querySelector("#btn-ledger-apply")?.addEventListener("click", () => applySandboxLedgerToForm(run));
    box.querySelector("#btn-ledger-replay")?.addEventListener("click", () => {
      try {
        sessionStorage.setItem("sandboxContextRunId", runId);
      } catch (_) {}
      showPanel("replay");
    });
  }

  function renderSandboxResult(j) {
    const host = $("sandbox-result");
    if (!host) return;
    if (!j.ok) {
      host.innerHTML = `<pre class="mono">${escapeHtml(JSON.stringify(j, null, 2))}</pre>`;
      return;
    }
    const r = j.result || {};
    const parts = [];
    parts.push(`<p class="meta mono" style="margin:0 0 0.5rem">run_id: ${escapeHtml(j.run_id || "")}</p>`);
    if (j.persisted === true) {
      parts.push(`<p class="meta" style="margin:0 0 0.5rem;color:var(--accent)">${escapeHtml(tr("sandbox.persisted_ok"))}</p>`);
    } else if (j.persisted === false) {
      parts.push(`<p class="meta" style="margin:0 0 0.5rem">${escapeHtml(tr("sandbox.persisted_fail"))}</p>`);
    }
    parts.push(`<div class="brief-label" style="margin-top:0.5rem">${escapeHtml(tr("sandbox.result_title"))}</div>`);
    const bullets = r.summary_bullets || [];
    parts.push("<ul>" + bullets.map((b) => "<li>" + escapeHtml(b) + "</li>").join("") + "</ul>");
    const scan = r.horizon_scan;
    if (scan && scan.length) {
      parts.push(`<div class="brief-label" style="margin-top:0.75rem">${escapeHtml(tr("sandbox.scan_title"))}</div>`);
      parts.push(
        "<table><thead><tr>" +
          ["sandbox.col_horizon", "sandbox.col_band", "sandbox.col_pos", "sandbox.col_headline"]
            .map((k) => "<th>" + escapeHtml(tr(k)) + "</th>")
            .join("") +
          "</tr></thead><tbody>"
      );
      scan.forEach((row) => {
        parts.push(
          "<tr><td>" +
            escapeHtml(String(row.horizon_label || row.horizon || "")) +
            "</td><td>" +
            escapeHtml(String(row.spectrum_band ?? "")) +
            "</td><td class='mono'>" +
            escapeHtml(row.spectrum_position != null ? String(row.spectrum_position) : "") +
            "</td><td>" +
            escapeHtml(String(row.headline || "")) +
            "</td></tr>"
        );
      });
      parts.push("</tbody></table>");
    }
    if (r.pit_note) {
      parts.push(`<p class="meta" style="margin-top:0.75rem">${escapeHtml(r.pit_note)}</p>`);
    }
    if (r.disclaimer) {
      parts.push(`<p class="sub" style="margin-top:0.5rem">${escapeHtml(r.disclaimer)}</p>`);
    }
    const actions = j.next_actions || [];
    if (actions.length) {
      parts.push("<div class='shortcut-row' style='margin-top:0.75rem'>");
      const curAid = ($("sandbox-asset-id") && $("sandbox-asset-id").value.trim()) || (getCopilotContext() && getCopilotContext().asset_id) || "";
      actions.forEach((a) => {
        if (a.requires_asset && !curAid) return;
        parts.push(
          "<button type='button' class='btn' data-sandbox-jump='" +
            escapeHtml(a.panel || "") +
            "' data-sandbox-aid='" +
            escapeHtml(curAid) +
            "'>" +
            escapeHtml(a.label || a.panel) +
            "</button>"
        );
      });
      parts.push("</div>");
    }
    host.innerHTML = parts.join("");
    host.querySelectorAll("button[data-sandbox-jump]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const panel = btn.getAttribute("data-sandbox-jump");
        const said = btn.getAttribute("data-sandbox-aid");
        if (panel === "today_detail" && said) {
          openTodayObjectDetail(said);
          return;
        }
        if (panel === "replay") {
          try {
            if (j.run_id) sessionStorage.setItem("sandboxContextRunId", j.run_id);
          } catch (_) {}
        }
        showPanel(panel || "home");
        if (panel === "replay") loadReplay();
        if (panel === "ask_ai") syncAskAiFromFeed();
      });
    });
  }

  async function submitSandboxRun() {
    const hypEl = $("sandbox-hypothesis");
    const saveEl = $("sandbox-save");
    const body = {
      hypothesis: (hypEl && hypEl.value) || "",
      horizon: ($("sandbox-horizon") && $("sandbox-horizon").value) || "short",
      pit_mode: ($("sandbox-pit-mode") && $("sandbox-pit-mode").value) || "snapshot",
      mock_price_tick: ($("sandbox-mock-tick") && $("sandbox-mock-tick").value) || "0",
      save: !saveEl || saveEl.checked,
    };
    const rawAid = ($("sandbox-asset-id") && $("sandbox-asset-id").value.trim()) || "";
    if (rawAid) body.asset_id = rawAid;
    const lg = encodeURIComponent(cockpitLang());
    const r = await api("/api/sandbox/run?lang=" + lg, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    renderSandboxResult(r.json);
    if (r.json && r.json.ok) {
      loadSandboxRunsList();
      hydrateResearchDeferredPanel();
    }
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
      const sid = String(d.message_snapshot_id || "").trim();
      const rlp = String(d.replay_lineage_pointer || "").trim();
      const lm = String(d.linked_message_summary || "").trim();
      let lineageBlock = "";
      if (sid || rlp) {
        const sidShow = sid ? (sid.length > 70 ? sid.slice(0, 70) + "…" : sid) : "—";
        const rlpShow = rlp ? (rlp.length > 92 ? rlp.slice(0, 92) + "…" : rlp) : "—";
        lineageBlock =
          `<div class="brief-label" style="margin-top:0.45rem">${escapeHtml(tr("journal.card_lineage"))}</div>` +
          `<div class="mono" style="font-size:0.68rem">${escapeHtml(tr("journal.card_snapshot"))}: ${escapeHtml(sidShow)}</div>` +
          `<div class="mono" style="font-size:0.68rem">${escapeHtml(tr("journal.card_lineage_ptr"))}: ${escapeHtml(rlpShow)}</div>`;
      }
      const lm160 = lm.slice(0, 160);
      div.innerHTML =
        `<div class="mono" style="font-size:0.75rem">${escapeHtml(String(d.timestamp || "").slice(0, 19))}</div>` +
        `<h3 style="margin:0.35rem 0 0.25rem;font-size:0.95rem">${escapeHtml(String(d.asset_id || "—"))}</h3>` +
        `<div class="sub">${escapeHtml(String(d.decision_type || ""))}</div>` +
        (lm160
          ? `<div class="sub" style="margin-top:0.35rem">${escapeHtml(tr("journal.card_message_line"))}: ${escapeHtml(lm160)}</div>`
          : "") +
        `<div class="body" style="margin-top:0.5rem">${escapeHtml(String(d.founder_note || "").slice(0, 800))}</div>` +
        lineageBlock +
        `<div class="sub" style="margin-top:0.5rem">${escapeHtml(tr("journal.replay_hint"))}</div>` +
        `<button type="button" class="btn journal-open-replay" style="margin-top:0.35rem">${escapeHtml(tr("journal.open_replay"))}</button>`;
      const btn = div.querySelector(".journal-open-replay");
      if (btn) {
        btn.addEventListener("click", () => {
          const aid = String(d.asset_id || "").trim();
          try {
            if (aid) sessionStorage.setItem("replayHighlightAssetId", aid);
            if (sid) sessionStorage.setItem("replayMessageSnapshotId", sid);
            if (aid) sessionStorage.setItem("replayPreviewAssetId", aid);
          } catch (_) {}
          showPanel("replay");
        });
      }
      host.appendChild(div);
    });
  }

  async function submitConv() {
    const payload = { text: $("conv-in").value };
    const cctx = getCopilotContext();
    if (cctx && cctx.asset_id) payload.copilot_context = cctx;
    const r = await api("/api/conversation", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
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
    const ctx = getCopilotContext();
    if (ctx && String(ctx.asset_id || "").trim() === asset_id && ctx.source === "today_detail") {
      const msid = String(ctx.message_snapshot_id || "").trim();
      const rlp = String(ctx.replay_lineage_pointer || "").trim();
      const reg = String(ctx.linked_registry_entry_id || "").trim();
      const art = String(ctx.linked_artifact_id || "").trim();
      if (msid) body.message_snapshot_id = msid;
      if (rlp) body.replay_lineage_pointer = rlp;
      if (reg) body.linked_registry_entry_id = reg;
      if (art) body.linked_artifact_id = art;
      const lm = String(ctx.headline || ctx.message_summary || "").trim();
      if (lm) body.linked_message_summary = lm.slice(0, 2000);
      body.linked_research_provenance = "today_object_detail_v1";
    }
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

  const btnAskCtxClear = $("btn-ask-context-clear");
  if (btnAskCtxClear) {
    btnAskCtxClear.addEventListener("click", () => setCopilotContext(null));
  }

  const btnSandbox = $("btn-sandbox-run");
  if (btnSandbox) btnSandbox.addEventListener("click", submitSandboxRun);

  const runsWrap = $("sandbox-runs-wrap");
  if (runsWrap) {
    runsWrap.addEventListener("click", (ev) => {
      const btn = ev.target.closest("button.sandbox-run-pick");
      if (!btn) return;
      const rid = btn.getAttribute("data-run-id");
      if (rid) showSandboxLedgerDetail(rid);
    });
  }

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
    refreshJournalLineageHint();
    await refreshObjectTabsFromOverview();
    await loadHomeFeed();
    if ($("panel-watchlist").classList.contains("visible")) await loadWatchlistPanel();
    if ($("panel-research").classList.contains("visible")) {
      if (objectSections[0]) await loadObjectSection(objectSections[0].id);
      loadResearchPanel();
    }
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
    refreshAskContextStrip();
    refreshSandboxTodayStrip();
    refreshJournalLineageHint();
    pollNotif();
    setInterval(pollNotif, 8000);
  }

  initCockpit();
})();
