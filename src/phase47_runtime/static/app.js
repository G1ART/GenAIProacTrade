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
    // AGH v1 Patch 7 A1 — localised aria-label for nav row groups.
    document.querySelectorAll("[data-i18n-aria-label]").forEach((el) => {
      const k = el.getAttribute("data-i18n-aria-label");
      if (k) el.setAttribute("aria-label", tr(k));
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
    // AGH v1 Patch 7 A1 — both nav tiers share active-state styling so a
    // utility panel (Journal / Advanced) still visibly tracks the route.
    document
      .querySelectorAll("#nav button[data-panel]")
      .forEach((b) => {
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

  document.querySelectorAll("#nav button[data-panel]").forEach((btn) => {
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
    // AGH v1 Patch 7 A1 — include <a> elements so demoted utility links
    // (Journal / Advanced) keep the same navigation behaviour as before.
    root.querySelectorAll("[data-jump]").forEach((btn) => {
      btn.addEventListener("click", (ev) => {
        if (btn.tagName === "A") ev.preventDefault();
        showPanel(btn.getAttribute("data-jump"));
      });
    });
    // AGH v1 Patch 8 A2 — Today hero-stack "Next step" CTA scrolls to the
    // Research bounded_next invoke card on the same page. No state is
    // mutated, no panel switch is forced if the card is already visible.
    root.querySelectorAll("[data-tsr-jump-to-invoke]").forEach((btn) => {
      btn.addEventListener("click", (ev) => {
        ev.preventDefault();
        const target = document.querySelector(".tsr-research-invoke");
        if (target && typeof target.scrollIntoView === "function") {
          target.scrollIntoView({ behavior: "smooth", block: "center" });
        }
      });
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
      `<p class="sub">${escapeHtml(tr("spectrum.sample_meta"))}</p>` +
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

  // AGH v1 Patch 6 — shared tooltip primitive (C2). label-not-dump copy.
  (function tsrInstallTooltip() {
    if (window.__tsrTooltipInstalled) return;
    window.__tsrTooltipInstalled = true;
    let tip = null;
    function ensureNode() {
      if (tip) return tip;
      tip = document.createElement("div");
      tip.className = "tsr-tooltip";
      tip.style.display = "none";
      document.body.appendChild(tip);
      return tip;
    }
    // AGH v1 Patch 7 A5 — "sub" can now contain multiple semantic parts
    // joined by " · " (SUB_SEP). When present, we emit each part on its
    // own line so tooltips can carry denser info (e.g. outcome · delta ·
    // from→to) without overflowing horizontally. Hosts that only pass a
    // single string continue to render unchanged.
    const SUB_SEP = " · ";
    window.tooltipAt = function tooltipAt(x, y, label, sub) {
      const el = ensureNode();
      const lbl = String(label || "").trim();
      const sbt = String(sub || "").trim();
      if (!lbl && !sbt) {
        el.style.display = "none";
        return;
      }
      const subParts = sbt ? sbt.split(SUB_SEP).map((s) => s.trim()).filter(Boolean) : [];
      const subHtml = subParts.length
        ? subParts
            .map((p) => `<div class="tt-sub">${escapeHtml(p)}</div>`)
            .join("")
        : "";
      el.innerHTML =
        (lbl ? `<div class="tt-label">${escapeHtml(lbl)}</div>` : "") + subHtml;
      el.style.display = "block";
      const margin = 12;
      const vw = window.innerWidth || 1024;
      const vh = window.innerHeight || 768;
      let left = x + margin;
      let top = y + margin;
      const bb = el.getBoundingClientRect();
      if (left + bb.width > vw - margin) left = Math.max(margin, x - bb.width - margin);
      if (top + bb.height > vh - margin) top = Math.max(margin, y - bb.height - margin);
      el.style.left = left + "px";
      el.style.top = top + "px";
    };
    window.tooltipHide = function tooltipHide() {
      if (tip) tip.style.display = "none";
    };
    // Global delegated hover: any element with data-tsr-tt-label shows tooltip.
    document.addEventListener("mouseover", (ev) => {
      const t = ev.target;
      if (!t || !t.closest) return;
      const host = t.closest("[data-tsr-tt-label]");
      if (!host) return;
      window.tooltipAt(
        ev.clientX,
        ev.clientY,
        host.getAttribute("data-tsr-tt-label") || "",
        host.getAttribute("data-tsr-tt-sub") || ""
      );
    });
    document.addEventListener("mousemove", (ev) => {
      const t = ev.target;
      if (!t || !t.closest) return;
      const host = t.closest("[data-tsr-tt-label]");
      if (!host) {
        window.tooltipHide();
        return;
      }
      window.tooltipAt(
        ev.clientX,
        ev.clientY,
        host.getAttribute("data-tsr-tt-label") || "",
        host.getAttribute("data-tsr-tt-sub") || ""
      );
    });
    document.addEventListener("mouseout", (ev) => {
      const t = ev.target;
      if (!t || !t.closest) return;
      const host = t.closest("[data-tsr-tt-label]");
      if (!host) window.tooltipHide();
    });
  })();

  // AGH v1 Patch 6 — humanize research evidence ref (prefer prefix map).
  function humanizeResearchEvidenceRef(ref, lang) {
    const s = String(ref || "").trim();
    if (!s) return "";
    const isKo = String(lang || "ko").toLowerCase().startsWith("ko");
    const prefix = s.split(":")[0] || s.split("_")[0] || "";
    const knownPrefix = {
      pkt: isKo ? "증거 패킷" : "Evidence packet",
      vpe: isKo ? "검증→승격 평가" : "Validation→promotion eval",
      fvs: isKo ? "검증 통계" : "Validation stats",
      rpa: isKo ? "거버넌스 적용" : "Governed apply",
      SandboxRequestPacketV1: isKo ? "샌드박스 요청" : "Sandbox request",
      SandboxResultPacketV1: isKo ? "샌드박스 결과" : "Sandbox result",
      bundle: isKo ? "번들 상태" : "Bundle state",
      seed: isKo ? "시드 데이터" : "Seed data",
    };
    return knownPrefix[prefix] || (isKo ? "참조" : "Reference");
  }

  // AGH v1 Patch 7 A3 — Research renderer with tr() wiring, 3-cluster
  // visual grouping, humanised evidence chips, bounded-invoke contract
  // card. DOM `data-tsr-sec` keys unchanged (5) so Patch 6 regression
  // tests still lock shape; clustering is CSS-only via
  // `data-tsr-cluster`.
  function renderResearchStructuredSection(j, lang) {
    const isKo = String(lang || "ko").toLowerCase().startsWith("ko");
    const rs = (j && j.research_structured_v1) || null;
    const rsb = (j && j.registry_surface_v1) || {};
    const ridReq = String(rsb.registry_entry_id || "").trim();
    const hzReq = String(j.horizon || "").trim();
    if (!rs || typeof rs !== "object") {
      return (
        `<div class="tsr-research" data-tsr-research-empty="1">` +
        `<h4>${escapeHtml(tr("research_section.head"))}</h4>` +
        `<div class="tsr-empty tsr-empty--premium">` +
        `<span class="tsr-empty-head">${escapeHtml(
          tr("research_section.empty_head")
        )}</span><br/>` +
        `<span class="ev-faint">${escapeHtml(
          tr("research_section.empty_body")
        )}</span>` +
        `<div class="tsr-empty-cta">` +
        `<button type="button" class="btn btn-xs" data-jump="ask_ai">${escapeHtml(
          tr("nav.ask_ai")
        )}</button>` +
        `</div>` +
        `</div></div>`
      );
    }
    const cov = String(rs.locale_coverage || "dual");
    // AGH v1 Patch 7 A3 — product-toned locale coverage copy routed via tr()
    // so the wording stays in one place (phase47e_user_locale SHELL).
    const covLabel = {
      dual: tr("research_section.locale_dual"),
      ko_only: tr("research_section.locale_ko_only"),
      en_only: tr("research_section.locale_en_only"),
      degraded: isKo
        ? tr("research_section.locale_degraded_label_ko")
        : tr("research_section.locale_degraded_label_en"),
    }[cov] || cov;
    const covTip =
      cov === "dual"
        ? isKo ? "양쪽 로캘 모두 제공됨" : "Both locales provided"
        : cov === "degraded"
        ? isKo ? "증거 부족으로 요약 미완성" : "Evidence too thin for a full summary"
        : isKo ? "단일 로캘만 제공됨" : "Only one locale provided";
    const covBadge = `<span class="tsr-research-coverage ${escapeHtml(cov)}" data-tsr-tt-label="${escapeHtml(
      covLabel
    )}" data-tsr-tt-sub="${escapeHtml(covTip)}">${escapeHtml(covLabel)}</span>`;

    const sumKo = Array.isArray(rs.summary_bullets_ko) ? rs.summary_bullets_ko : [];
    const sumEn = Array.isArray(rs.summary_bullets_en) ? rs.summary_bullets_en : [];
    // AGH v1 Patch 8 A1c — what_changed_bullets are the new first layer of
    // the 4-stack. Prefer the requested locale, fall back to the other
    // locale honestly (still badged via covBadge).
    const wcKo = Array.isArray(rs.what_changed_bullets_ko) ? rs.what_changed_bullets_ko : [];
    const wcEn = Array.isArray(rs.what_changed_bullets_en) ? rs.what_changed_bullets_en : [];
    const residual = Array.isArray(rs.residual_uncertainty_bullets)
      ? rs.residual_uncertainty_bullets
      : [];
    const watch = Array.isArray(rs.what_to_watch_bullets) ? rs.what_to_watch_bullets : [];

    function bulletList(items, emptyLabel) {
      if (!items.length) return `<div class="ev-faint">${escapeHtml(emptyLabel)}</div>`;
      return `<ul>${items.map((x) => `<li>${escapeHtml(String(x))}</li>`).join("")}</ul>`;
    }
    const summary = isKo
      ? sumKo.length
        ? sumKo
        : sumEn
      : sumEn.length
      ? sumEn
      : sumKo;
    const summaryEmpty = tr("research_section.no_bullets");
    const whatChanged = isKo
      ? wcKo.length
        ? wcKo
        : wcEn
      : wcEn.length
      ? wcEn
      : wcKo;

    // AGH v1 Patch 7 A3 — evidence chips grouped by packet kind so
    // operators scan by source-of-truth class (apply / proposal / eval /
    // message) before diving into raw IDs. Tooltip sub-line exposes the
    // engineering packet kind so the humanised label never lies.
    const evidenceCited = Array.isArray(rs.evidence_cited) ? rs.evidence_cited : [];
    function evidenceKindOf(ref) {
      const s = String(ref || "").toLowerCase();
      if (!s) return "other";
      if (s.startsWith("registrypatchapplied")) return "apply";
      if (s.startsWith("registrypatchproposal")) return "proposal";
      if (s.startsWith("validationpromotionevaluation")) return "evaluation";
      if (s.startsWith("userqueryactionpacket")) return "message";
      return "other";
    }
    const evGroups = { apply: [], proposal: [], evaluation: [], message: [], other: [] };
    evidenceCited.slice(0, 8).forEach((ref) => {
      evGroups[evidenceKindOf(ref)].push(ref);
    });
    const evOrder = ["apply", "proposal", "evaluation", "message", "other"];
    const evidenceChips = evOrder
      .map((k) => {
        if (!evGroups[k].length) return "";
        return evGroups[k]
          .map((ref) => {
            const label = humanizeResearchEvidenceRef(ref, lang);
            return `<span class="tsr-chip tsr-chip--neutral tsr-evidence-chip" data-tsr-evkind="${escapeHtml(
              k
            )}" data-tsr-tt-label="${escapeHtml(label)}" data-tsr-tt-sub="${escapeHtml(
              String(ref)
            )}">${escapeHtml(label)}</span>`;
          })
          .join(" ");
      })
      .filter(Boolean)
      .join(`<span class="tsr-evidence-sep" aria-hidden="true"> · </span>`);
    const rawEvidenceDetails =
      evidenceCited.length > 0
        ? `<details><summary>${escapeHtml(
            tr("tsr.evidence.raw_ids")
          )}</summary><div class="raw-ids">${evidenceCited
            .map((x) => escapeHtml(String(x)))
            .join("<br/>")}</div></details>`
        : "";

    // Section (e) — bounded next step invoke UI with contract card (Patch 7 B2)
    const ps = rs.proposed_sandbox_request && typeof rs.proposed_sandbox_request === "object"
      ? rs.proposed_sandbox_request
      : null;
    let invokeSec = "";
    if (ps) {
      const sk = String(ps.sandbox_kind || "");
      const rid = String(ps.registry_entry_id || ridReq);
      const hz = String(ps.horizon || hzReq);
      const ts = ps.target_spec && typeof ps.target_spec === "object" ? ps.target_spec : {};
      const fn = String(ts.factor_name || "");
      const un = String(ts.universe_name || "");
      const htp = String(ts.horizon_type || "");
      const rb = String(ts.return_basis || "");
      const cited = Array.isArray(rs.evidence_cited) && rs.evidence_cited.length
        ? rs.evidence_cited
        : (Array.isArray(rs.cited_packet_ids) ? rs.cited_packet_ids : []);
      const citedFlat = cited.map((x) => String(x)).filter(Boolean).join(" ");
      const cli =
        `harness-sandbox-request ` +
        `--registry-entry-id ${rid} ` +
        `--horizon ${hz} ` +
        `--factor-name ${fn} ` +
        `--universe-name ${un} ` +
        `--horizon-type ${htp} ` +
        `--return-basis ${rb} ` +
        (citedFlat ? `--cited-evidence-packet-ids ${citedFlat} ` : "") +
        `--request-id $(uuidgen)`;
      const invokeEnabled = !!window.__metisUiInvokeEnabled;
      const buttonRow = invokeEnabled
        ? `<button type="button" class="btn btn-primary" data-tsr-enqueue-sandbox="1" data-rid="${escapeHtml(
            rid
          )}" data-hz="${escapeHtml(hz)}" data-fn="${escapeHtml(fn)}" data-un="${escapeHtml(
            un
          )}" data-htp="${escapeHtml(htp)}" data-rb="${escapeHtml(
            rb
          )}" data-cited="${escapeHtml(citedFlat)}" data-rationale="${escapeHtml(
            String(ps.rationale || "")
          )}">${escapeHtml(tr("research_section.invoke_enqueue_btn"))}</button>`
        : "";
      const inlineMsg = invokeEnabled
        ? `<span class="invoke-inline-msg">${escapeHtml(
            tr("research_section.invoke_ui_hint")
          )}</span>`
        : `<span class="invoke-inline-msg">${escapeHtml(
            tr("research_section.invoke_copy_hint")
          )}</span>`;
      // AGH v1 Patch 7 B2 — contract card 3 lines (will_do / will_not_do /
      // after_enqueue). Always rendered regardless of `invokeEnabled` so
      // the operator sees the bounded contract even when UI invoke is off.
      const contractCard =
        `<div class="tsr-contract-card" data-tsr-contract="1">` +
        `<div class="tsr-contract-head">${escapeHtml(
          tr("tsr.invoke.contract.head")
        )}</div>` +
        `<ul class="tsr-contract-list">` +
        `<li data-tsr-contract-line="will_do">${escapeHtml(
          tr("tsr.invoke.contract.will_do")
        )}</li>` +
        `<li data-tsr-contract-line="will_not_do">${escapeHtml(
          tr("tsr.invoke.contract.will_not_do")
        )}</li>` +
        `<li data-tsr-contract-line="after_enqueue">${escapeHtml(
          tr("tsr.invoke.contract.after_enqueue")
        )}</li>` +
        // AGH v1 Patch 8 B4 — 4th contract line + a dedicated 4-state
        // chip slot directly under the contract. Keeping the visible
        // state *inside* the contract block makes the promise
        // ("after run you will see these 4 states") testable by the
        // operator at a glance.
        `<li data-tsr-contract-line="status_after">${escapeHtml(
          tr("tsr.invoke.contract.status_after")
        )}</li>` +
        `</ul>` +
        `<div class="tsr-contract-state-slot" data-tsr-contract-state-slot="1">` +
        `<span class="tsr-chip tsr-chip--neutral" data-tsr-contract-state-chip="1">${escapeHtml(
          tr("research_section.invoke_state_unknown")
        )}</span>` +
        `</div>` +
        `</div>`;
      const recentSid = `tsr-recent-sbx-${Math.random().toString(36).slice(2, 9)}`;
      // AGH v1 Patch 8 B3 — per-registry-entry recent sandbox requests
      // (newest-first, 5 rows). Hydrated async so the first render is
      // fast and the list refreshes on every post-invoke auto-refresh.
      setTimeout(
        () => hydrateRecentSandboxRequests(recentSid, rid, hz, lang),
        0
      );
      const recentBlockHtml =
        `<div class="tsr-recent-sandbox-requests" id="${recentSid}" ` +
        `data-tsr-recent-sandbox="1" data-tsr-rid="${escapeHtml(rid)}" ` +
        `data-tsr-hz="${escapeHtml(hz)}">` +
        `<div class="tsr-recent-head">${escapeHtml(
          tr("research_section.recent_requests_head")
        )}</div>` +
        `<div class="tsr-recent-body ev-faint" data-tsr-recent-loading="1">${escapeHtml(
          tr("research_section.invoke_state_loading")
        )}</div>` +
        `</div>`;
      invokeSec = (
        `<div class="tsr-research-invoke" data-tsr-rid="${escapeHtml(
          rid
        )}" data-tsr-hz="${escapeHtml(hz)}" data-tsr-recent-mount="${escapeHtml(
          recentSid
        )}">` +
        contractCard +
        `<div class="invoke-label">${escapeHtml(
          tr("research_section.bounded_next")
        )} · ${escapeHtml(sk)}</div>` +
        `<div class="invoke-cli" data-tsr-cli="1">${escapeHtml(cli)}</div>` +
        `<div class="invoke-row">` +
        `<button type="button" class="btn" data-tsr-copy-cli="1">${escapeHtml(
          tr("research_section.invoke_copy_btn")
        )}</button>` +
        buttonRow +
        inlineMsg +
        `</div>` +
        `<div class="invoke-row invoke-state-row" data-tsr-invoke-state-row="1" hidden>` +
        `<span class="tsr-chip tsr-chip--neutral" data-tsr-invoke-state-chip="1">${escapeHtml(
          tr("research_section.invoke_state_unknown")
        )}</span>` +
        `<button type="button" class="btn btn-xs" data-tsr-invoke-refresh="1">${escapeHtml(
          tr("research_section.invoke_queue_poll")
        )}</button>` +
        `</div>` +
        `<div data-tsr-enqueue-result="1" class="invoke-inline-msg" style="margin-top:0.3rem"></div>` +
        recentBlockHtml +
        `</div>`
      );
    }

    return (
      `<div class="tsr-research" data-tsr-research="1">` +
      `<h4>${escapeHtml(tr("research_section.head"))} ${covBadge}</h4>` +
      // AGH v1 Patch 8 A1c — 4-stack stable order inside the current_read
      // cluster: (1) what_changed new (first, may be empty), (2)
      // why_it_matters (relabeled from "current read"), (3) evidence
      // chips. Two additional sections under open_questions cluster
      // (unproven / watch) + bounded_next stay as-is.
      `<div class="tsr-research-cluster" data-tsr-cluster="current_read">` +
      `<div class="tsr-research-sec" data-tsr-sec="what_changed">` +
      `<div class="sec-title">${escapeHtml(
        tr("research_section.what_changed")
      )}</div>` +
      bulletList(whatChanged, tr("research_section.no_what_changed")) +
      `</div>` +
      `<div class="tsr-research-sec" data-tsr-sec="current_read">` +
      `<div class="sec-title">${escapeHtml(
        tr("research_section.why_it_matters")
      )}</div>` +
      bulletList(summary, summaryEmpty) +
      `</div>` +
      `<div class="tsr-research-sec" data-tsr-sec="why_plausible">` +
      `<div class="sec-title">${escapeHtml(
        tr("research_section.why_plausible")
      )}</div>` +
      (evidenceChips
        ? `<div class="row tsr-evidence-row" style="gap:0.3rem">${evidenceChips}</div>${rawEvidenceDetails}`
        : `<div class="ev-faint">${escapeHtml(
            tr("research_section.no_evidence")
          )}</div>`) +
      `</div>` +
      `</div>` +
      `<div class="tsr-research-cluster" data-tsr-cluster="open_questions">` +
      `<div class="tsr-research-sec" data-tsr-sec="unproven">` +
      `<div class="sec-title">${escapeHtml(
        tr("research_section.unproven")
      )}</div>` +
      bulletList(residual, tr("research_section.no_unproven")) +
      `</div>` +
      `<div class="tsr-research-sec" data-tsr-sec="watch">` +
      `<div class="sec-title">${escapeHtml(
        tr("research_section.watch")
      )}</div>` +
      bulletList(watch, tr("research_section.no_watch")) +
      `</div>` +
      `</div>` +
      `<div class="tsr-research-cluster" data-tsr-cluster="bounded_next">` +
      `<div class="tsr-research-sec" data-tsr-sec="bounded_next">` +
      `<div class="sec-title">${escapeHtml(
        tr("research_section.bounded_next")
      )}</div>` +
      (invokeSec
        ? invokeSec
        : `<div class="ev-faint">${escapeHtml(
            tr("research_section.no_sandbox_action")
          )}</div>`) +
      `</div>` +
      `</div>` +
      `</div>`
    );
  }

  // AGH v1 Patch 8 A5 — shared helper that derives the two "what-is-new"
  // facts used across rail / lineage / plot tooltips:
  //   * what_changed_one_line  — first what_changed bullet (locale-aware,
  //     falling back to the other locale if empty) from research_structured_v1
  //   * confidence_band        — from message.confidence_band
  // Returns an object with pre-trimmed, ≤160-char fragments plus a
  // ready-to-use sub suffix joined with SUB_SEP (" · ").
  function extractTooltipContextFromTsr(j, isKo) {
    const rsS = (j && j.research_structured_v1) || {};
    const ko = Array.isArray(rsS.what_changed_bullets_ko)
      ? rsS.what_changed_bullets_ko
      : [];
    const en = Array.isArray(rsS.what_changed_bullets_en)
      ? rsS.what_changed_bullets_en
      : [];
    const primary = isKo ? (ko.length ? ko : en) : (en.length ? en : ko);
    const whatChanged = String((primary && primary[0]) || "").trim();
    const msg = (j && j.message) || {};
    const confidence = String(msg.confidence_band || "").trim();
    const parts = [];
    if (whatChanged) {
      const snip =
        whatChanged.length > 160 ? whatChanged.slice(0, 157) + "…" : whatChanged;
      parts.push(snip);
    }
    if (confidence) {
      parts.push(
        (isKo ? "신뢰도 " : "Confidence ") + confidence
      );
    }
    return {
      what_changed_one_line: whatChanged,
      confidence_band: confidence,
      sub_suffix: parts.join(" · "),
    };
  }

  // AGH v1 Patch 6 — Replay governance lineage compact renderer (B3).
  // Loads /api/replay/governance-lineage asynchronously and writes into
  // the placeholder container (returned by the sync renderer).
  function renderReplayGovernanceLineageCompactHtml(j, lang) {
    const isKo = String(lang || "ko").toLowerCase().startsWith("ko");
    const rs = (j && j.registry_surface_v1) || {};
    const rid = String(rs.registry_entry_id || "").trim();
    const hz = String(j.horizon || "").trim();
    if (!rid) {
      return "";
    }
    const sid = `tsr-lineage-${Math.random().toString(36).slice(2, 9)}`;
    // AGH v1 Patch 8 A5 — extract the same "what changed" one-liner +
    // confidence band used by the rail/primary panel, so the lineage /
    // plot tooltips can carry that context without a second fetch.
    const ttCtx = extractTooltipContextFromTsr(j, isKo);
    setTimeout(
      () => hydrateReplayGovernanceLineageCompact(sid, rid, hz, isKo, ttCtx),
      0
    );
    return (
      `<div id="${sid}" class="tsr-replay-lineage" data-tsr-replay-lineage="1">` +
      `<h4>${escapeHtml(
        isKo ? "거버넌스 계보 · Governance lineage" : "Governance lineage"
      )}</h4>` +
      `<div class="ev-faint" data-tsr-lineage-loading="1">${escapeHtml(
        isKo ? "로드 중…" : "Loading…"
      )}</div>` +
      `</div>`
    );
  }

  async function hydrateReplayGovernanceLineageCompact(containerId, rid, hz, isKo, ttCtx) {
    const el = document.getElementById(containerId);
    if (!el) return;
    try {
      const qs = `registry_entry_id=${encodeURIComponent(rid)}${
        hz ? `&horizon=${encodeURIComponent(hz)}` : ""
      }`;
      const { ok, json } = await api(`/api/replay/governance-lineage?${qs}`);
      if (!ok || !json || json.ok === false) {
        el.innerHTML =
          `<h4>${escapeHtml(
            isKo ? "거버넌스 계보" : "Governance lineage"
          )}</h4>` +
          `<div class="tsr-empty">${escapeHtml(
            isKo ? "계보 정보를 읽지 못했습니다." : "Lineage unavailable."
          )}</div>`;
        return;
      }
      const total = json.total_applied || json.total_applies || 0;
      const completed = json.total_sandbox_completed || 0;
      const rebuild = json.latest_applied_needs_db_rebuild === true;
      const chains = Array.isArray(json.chains) ? json.chains : [];
      const latest = chains.length ? chains[0] : null;
      // AGH v1 Patch 7 A4 — lineage step rows carry (a) the step outcome,
      // (b) a per-step at_utc so we can compute inter-step time-delta, and
      // (c) a done-count summary rendered at the top of the step indicator.
      const stepAt = (obj) =>
        obj && typeof obj === "object" ? String(obj.created_at_utc || "") : "";
      const steps = [
        {
          key: "proposal",
          outcome:
            latest && latest.proposal && latest.proposal.outcome
              ? String(latest.proposal.outcome)
              : latest && latest.validation_promotion_evaluation && latest.validation_promotion_evaluation.outcome
              ? String(latest.validation_promotion_evaluation.outcome)
              : "",
          at:
            stepAt(latest && latest.proposal) ||
            stepAt(latest && latest.validation_promotion_evaluation),
          label: isKo ? "제안" : "Proposal",
        },
        {
          key: "applied",
          outcome: latest && latest.applied && latest.applied.outcome ? String(latest.applied.outcome) : "",
          at: stepAt(latest && latest.applied),
          label: isKo ? "적용" : "Apply",
        },
        {
          key: "spectrum_refresh",
          outcome:
            latest && latest.spectrum_refresh && latest.spectrum_refresh.outcome
              ? String(latest.spectrum_refresh.outcome)
              : "",
          at: stepAt(latest && latest.spectrum_refresh),
          label: isKo ? "스펙트럼 리프레시" : "Spectrum refresh",
        },
        {
          key: "validation_eval",
          outcome:
            latest && latest.validation_promotion_evaluation && latest.validation_promotion_evaluation.outcome
              ? String(latest.validation_promotion_evaluation.outcome)
              : "",
          at: stepAt(latest && latest.validation_promotion_evaluation),
          label: isKo ? "검증 평가" : "Validation eval",
        },
      ];
      function stepClass(outcome) {
        const s = String(outcome || "").toLowerCase();
        if (!s) return "pending";
        if (s.startsWith("blocked")) return "blocked";
        if (s === "applied" || s === "emitted" || s === "promotion_candidate" || s === "refreshed" || s === "skipped") return "done";
        return "pending";
      }
      function tsrStepDeltaLabel(prevIso, curIso, lang) {
        if (!prevIso || !curIso) return "";
        const a = Date.parse(prevIso);
        const b = Date.parse(curIso);
        if (!isFinite(a) || !isFinite(b) || b <= a) return "";
        const sec = Math.round((b - a) / 1000);
        let token;
        if (sec < 60) token = `${sec}s`;
        else if (sec < 3600) token = `${Math.round(sec / 60)}m`;
        else if (sec < 86400) token = `${Math.round(sec / 3600)}h`;
        else token = `${Math.round(sec / 86400)}d`;
        return tr("lineage.step_after").replace("{delta}", token);
      }
      const doneCount = steps.filter((s) => stepClass(s.outcome) === "done").length;
      const doneSummaryText = tr("lineage.step_count").replace(
        "{done}",
        String(doneCount)
      );
      const doneSummaryHtml = `<div class="tsr-step-summary tsr-foot" data-tsr-step-summary="1">${escapeHtml(
        doneSummaryText
      )}</div>`;
      // AGH v1 Patch 8 A3 — single-line "step note" describing the current
      // frontier of the lineage (last done step, or first pending). This
      // gives operators an instant status read without scanning the four
      // step chips. Keeps the DOM contract stable (tsr-step-note is the
      // new data key).
      let currentStep = null;
      for (let i = steps.length - 1; i >= 0; i--) {
        if (stepClass(steps[i].outcome) === "done") {
          currentStep = steps[i];
          break;
        }
      }
      if (!currentStep) {
        for (let i = 0; i < steps.length; i++) {
          if (steps[i].outcome) {
            currentStep = steps[i];
            break;
          }
        }
      }
      let stepNoteText;
      if (currentStep) {
        stepNoteText = tr("lineage.step_note.current")
          .replace("{label}", currentStep.label)
          .replace(
            "{outcome}",
            currentStep.outcome || tr("lineage.step_pending")
          );
      } else {
        stepNoteText = tr("lineage.step_note.not_started");
      }
      const stepNoteHtml = `<div class="tsr-step-note tsr-foot" data-tsr-step-note="1">${escapeHtml(
        stepNoteText
      )}</div>`;
      const stepsHtml = steps
        .map((s, i) => {
          const cls = `tsr-step ${stepClass(s.outcome)}`;
          const sub = s.outcome ? s.outcome : tr("lineage.step_pending");
          const prevAt = i > 0 ? steps[i - 1].at : "";
          const deltaLabel = tsrStepDeltaLabel(prevAt, s.at, isKo ? "ko" : "en");
          const subBase = deltaLabel ? `${sub} · ${deltaLabel}` : sub;
          // AGH v1 Patch 8 A5 — append the shared "what changed" / "confidence"
          // context (same tokens used on the rail chip / plot event tooltips)
          // so every lineage step hover carries a consistent one-glance read.
          const tipSub =
            ttCtx && ttCtx.sub_suffix
              ? `${subBase} · ${ttCtx.sub_suffix}`
              : subBase;
          const arrow =
            i < steps.length - 1
              ? `<span class="tsr-step-arrow">${
                  deltaLabel && steps[i + 1].at
                    ? escapeHtml("→")
                    : "→"
                }</span>`
              : "";
          return (
            `<span class="${cls}" data-tsr-tt-label="${escapeHtml(
              s.label
            )}" data-tsr-tt-sub="${escapeHtml(tipSub)}"><span class="step-num">${i + 1}</span>${escapeHtml(
              s.label
            )}</span>` + arrow
          );
        })
        .join("");
      const followups = Array.isArray(json.sandbox_followups) ? json.sandbox_followups : [];
      const followupsHtml = followups.length
        ? `<div class="tsr-lineage-followups"><strong>${escapeHtml(
            isKo ? "샌드박스 팔로업" : "Sandbox followups"
          )}</strong><ul>${followups
            .slice(0, 3)
            .map((fu) => {
              const kind = String((fu.request && fu.request.payload && fu.request.payload.sandbox_kind) || "");
              const outcome = String((fu.result && fu.result.payload && fu.result.payload.outcome) || (isKo ? "대기" : "pending"));
              return `<li>${escapeHtml(kind || "validation_rerun")} · ${escapeHtml(outcome)}</li>`;
            })
            .join("")}</ul></div>`
        : `<div class="tsr-lineage-followups ev-faint">${escapeHtml(
            isKo ? "샌드박스 팔로업 없음" : "No sandbox followups"
          )}</div>`;
      const chipTotal = `<span class="tsr-chip tsr-chip--info">${escapeHtml(
        isKo ? `적용 ${total}건` : `Applies: ${total}`
      )}</span>`;
      const chipCompleted = `<span class="tsr-chip ${
        completed ? "tsr-chip--info" : "tsr-chip--neutral"
      }">${escapeHtml(
        isKo ? `샌드박스 완료 ${completed}건` : `Sandbox completed: ${completed}`
      )}</span>`;
      const chipRebuild = rebuild
        ? `<span class="tsr-chip tsr-chip--warn">${escapeHtml(
            isKo ? "DB 재빌드 필요" : "DB rebuild needed"
          )}</span>`
        : "";
      const timeline = renderReplayTimelinePlotSvg(latest, followups, isKo, ttCtx);
      el.innerHTML =
        `<h4>${escapeHtml(isKo ? "거버넌스 계보 · Governance lineage" : "Governance lineage")}</h4>` +
        `<div class="row" style="gap:0.35rem">${chipTotal}${chipCompleted}${chipRebuild}</div>` +
        doneSummaryHtml +
        `<div class="tsr-step-indicator">${stepsHtml}</div>` +
        stepNoteHtml +
        timeline +
        followupsHtml;
    } catch (_e) {
      el.innerHTML =
        `<h4>${escapeHtml(isKo ? "거버넌스 계보" : "Governance lineage")}</h4>` +
        `<div class="tsr-empty">${escapeHtml(
          isKo ? "계보 로드 실패." : "Lineage load failed."
        )}</div>`;
    }
  }

  // AGH v1 Patch 6 — Replay timeline SVG plot (C1). No external charting lib.
  // AGH v1 Patch 7 A4 — upgraded to 3-lane layout so "what happened when"
  // reads at a glance:
  //   lane 1 = governed_apply  (top)
  //   lane 2 = spectrum_refresh (middle)
  //   lane 3 = sandbox_followup (bottom)
  // Each lane has a left-side label in the user's locale. Events still
  // carry tooltip label/sub via data-tsr-tt-* so the existing shared
  // tooltip wiring keeps working unchanged.
  function renderReplayTimelinePlotSvg(latestChain, followups, isKo, ttCtx) {
    // AGH v1 Patch 7 A5 — plot sub lines now carry **multiple** facts,
    // joined by " · " so the shared tooltip splits them into separate
    // rows (outcome / delta / from→to). This gives the hover a richer
    // one-glance read without visible clutter in the SVG itself.
    const events = [];
    if (latestChain && latestChain.applied && latestChain.applied.created_at_utc) {
      const outcome = String(latestChain.applied.outcome || "");
      const fromId = String(latestChain.applied.from_active_artifact_id || "");
      const toId = String(latestChain.applied.to_active_artifact_id || "");
      const transfer = fromId
        ? `${humanizeActiveArtifactLabel({}, fromId)} → ${
            toId ? humanizeActiveArtifactLabel({}, toId) : ""
          }`
        : "";
      const delta = humanizeTimeDelta(
        String(latestChain.applied.created_at_utc),
        isKo ? "ko" : "en"
      );
      events.push({
        lane: 0,
        type: "governed_apply",
        at: String(latestChain.applied.created_at_utc),
        label: tr("plot.governed_apply"),
        sub: [outcome, delta, transfer].filter(Boolean).join(" · "),
      });
    }
    if (latestChain && latestChain.spectrum_refresh && latestChain.spectrum_refresh.created_at_utc) {
      const outcome = String(latestChain.spectrum_refresh.outcome || "");
      const delta = humanizeTimeDelta(
        String(latestChain.spectrum_refresh.created_at_utc),
        isKo ? "ko" : "en"
      );
      events.push({
        lane: 1,
        type: "spectrum_refresh",
        at: String(latestChain.spectrum_refresh.created_at_utc),
        label: tr("plot.spectrum_refresh"),
        sub: [outcome, delta].filter(Boolean).join(" · "),
      });
    }
    if (Array.isArray(followups)) {
      followups.slice(0, 5).forEach((fu) => {
        const res = fu && fu.result ? fu.result : null;
        const req = fu && fu.request ? fu.request : null;
        const at = String(
          (res && res.created_at_utc) || (req && req.created_at_utc) || ""
        );
        if (!at) return;
        const kind =
          (req && req.payload && req.payload.sandbox_kind) || "validation_rerun";
        const outcome =
          (res && res.payload && res.payload.outcome) || tr("lineage.step_pending");
        const delta = humanizeTimeDelta(at, isKo ? "ko" : "en");
        events.push({
          lane: 2,
          type: "sandbox_followup",
          at,
          label: tr("plot.sandbox_followup"),
          sub: [kind, String(outcome), delta].filter(Boolean).join(" · "),
        });
      });
    }
    if (!events.length) {
      return `<div class="ev-faint" style="margin:0.45rem 0">${escapeHtml(
        tr("plot.no_events")
      )}</div>`;
    }
    const times = events
      .map((e) => Date.parse(e.at))
      .filter((t) => !isNaN(t));
    if (!times.length) {
      return "";
    }
    const t0 = Math.min.apply(null, times);
    const t1 = Math.max.apply(null, times);
    const range = Math.max(t1 - t0, 24 * 3600 * 1000);
    const w = 640;
    const laneLabelWidth = 92;
    const laneHeight = 26;
    const laneTopPad = 8;
    const axisH = 18;
    const h = laneTopPad + laneHeight * 3 + axisH;
    const plotLeft = laneLabelWidth;
    const plotRight = w - 12;
    function xOf(ms) {
      return plotLeft + ((ms - t0) / range) * (plotRight - plotLeft);
    }
    function laneY(laneIdx) {
      return laneTopPad + laneHeight * laneIdx + laneHeight / 2;
    }
    const laneNames = [
      tr("plot.lane_apply"),
      tr("plot.lane_spectrum"),
      tr("plot.lane_sandbox"),
    ];
    const laneGuidesSvg = [0, 1, 2]
      .map((i) => {
        const y = laneY(i);
        return (
          `<text class="plot-lane-label" x="4" y="${y + 4}">${escapeHtml(
            laneNames[i]
          )}</text>` +
          `<line class="plot-lane-guide" x1="${plotLeft}" y1="${y}" x2="${plotRight}" y2="${y}" />`
        );
      })
      .join("");
    // AGH v1 Patch 8 A3 — annotate any ≥30-day gap between consecutive
    // chronological events. We sort by ``at`` and emit a tspan text label
    // ("Gap · 45d") midway between the two event x-positions when the
    // delta exceeds the 30-day threshold. Kept subtle (muted color /
    // small font) so it narrates without overpowering the lane dots.
    const GAP_THRESHOLD_MS = 30 * 86400 * 1000;
    const sortedEvents = events
      .map((e) => ({ e, t: Date.parse(e.at) }))
      .filter((x) => !isNaN(x.t))
      .sort((a, b) => a.t - b.t);
    const gapAnnotationsSvg = sortedEvents
      .map((cur, i) => {
        if (i === 0) return "";
        const prev = sortedEvents[i - 1];
        const dt = cur.t - prev.t;
        if (dt < GAP_THRESHOLD_MS) return "";
        const midX = (xOf(prev.t) + xOf(cur.t)) / 2;
        const yTop = laneTopPad - 2;
        const days = Math.round(dt / 86400000);
        const label = `${tr("lineage.gap_annotation_prefix")} · ${days}d`;
        return (
          `<text class="plot-gap-annotation" x="${midX}" y="${yTop}" ` +
          `text-anchor="middle" data-tsr-tt-label="${escapeHtml(
            tr("lineage.gap_30d_plus")
          )}" data-tsr-tt-sub="${escapeHtml(label)}">${escapeHtml(
            label
          )}</text>`
        );
      })
      .join("");
    // AGH v1 Patch 8 A5 — append the shared what_changed / confidence
    // suffix (same tokens rail + lineage use) so timeline-plot hovers
    // stay consistent with the rest of the TSR tooltip surface.
    const ttSuffix = ttCtx && ttCtx.sub_suffix ? ttCtx.sub_suffix : "";
    const eventsSvg = events
      .map((e) => {
        const t = Date.parse(e.at);
        if (isNaN(t)) return "";
        const x = xOf(t);
        const y = laneY(e.lane);
        const dayLabel = e.at.slice(0, 10);
        const tipLabel = `${e.label} · ${dayLabel}`;
        const baseSub = e.sub || "";
        const tipSub = ttSuffix
          ? baseSub
            ? `${baseSub} · ${ttSuffix}`
            : ttSuffix
          : baseSub;
        if (e.type === "governed_apply") {
          return (
            `<line class="plot-govern-apply" x1="${x}" y1="${y - 10}" x2="${x}" y2="${y + 10}" data-tsr-tt-label="${escapeHtml(
              tipLabel
            )}" data-tsr-tt-sub="${escapeHtml(tipSub)}" />` +
            `<circle class="plot-govern-apply-dot" cx="${x}" cy="${y}" r="4" data-tsr-tt-label="${escapeHtml(
              tipLabel
            )}" data-tsr-tt-sub="${escapeHtml(tipSub)}" />`
          );
        }
        if (e.type === "spectrum_refresh") {
          return `<rect class="plot-spectrum-tick" x="${x - 3}" y="${y - 6}" width="6" height="12" data-tsr-tt-label="${escapeHtml(
            tipLabel
          )}" data-tsr-tt-sub="${escapeHtml(tipSub)}" />`;
        }
        return `<circle class="plot-sandbox-tick plot-event" cx="${x}" cy="${y}" r="4" data-tsr-tt-label="${escapeHtml(
          tipLabel
        )}" data-tsr-tt-sub="${escapeHtml(tipSub)}" />`;
      })
      .join("");
    const axisY = laneTopPad + laneHeight * 3;
    const axisLabels =
      `<text class="plot-axis-label" x="${plotLeft}" y="${h - 4}">${escapeHtml(
        new Date(t0).toISOString().slice(0, 10)
      )}</text>` +
      `<text class="plot-axis-label" x="${plotRight - 66}" y="${h - 4}">${escapeHtml(
        new Date(t1).toISOString().slice(0, 10)
      )}</text>`;
    const legend = `<text class="plot-axis-label" x="${plotLeft}" y="${
      laneTopPad - 2
    }">${escapeHtml(tr("plot.lane_legend_note"))}</text>`;
    const svg =
      `<svg class="tsr-timeline-plot" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" data-tsr-timeline-plot="3lane">` +
      legend +
      laneGuidesSvg +
      `<line class="plot-axis" x1="${plotLeft}" y1="${axisY}" x2="${plotRight}" y2="${axisY}" />` +
      gapAnnotationsSvg +
      eventsSvg +
      axisLabels +
      `</svg>`;
    return svg;
  }

  // AGH v1 Patch 7 B1 — enqueue-sandbox click, upgraded from Patch 6:
  // (a) every user-facing string routed through tr() with keys in
  //     phase47e_user_locale SHELL.
  // (b) uses server-returned `cli_hint` + `operator_note` instead of
  //     reconstructing the command text client-side (server is the
  //     single source of truth for what harness-tick to run).
  // (c) one-time, on-demand queue state polling. We poll once 1.5s
  //     after enqueue (post-enqueue delay masks common Supabase commit
  //     lag), then only on explicit operator "Refresh" click. We do
  //     NOT background-poll, because that would erode the operator
  //     gate (Product Spec §4.3: operator decides when harness-tick
  //     runs; the UI must not imply otherwise).
  async function tsrInvokePollState(wrap, requestPacketId) {
    if (!wrap || !requestPacketId) return;
    const row = wrap.querySelector("[data-tsr-invoke-state-row]");
    const chip = wrap.querySelector("[data-tsr-invoke-state-chip]");
    if (!row || !chip) return;
    // AGH v1 Patch 8 B4 — mirror the 4-state into the contract card
    // slot so the operator sees the same chip under the "what this
    // action does" list. We set both via a helper.
    const mirrorChip = wrap.querySelector("[data-tsr-contract-state-chip]");
    function applyChip(cls, text) {
      chip.className = cls;
      chip.textContent = text;
      if (mirrorChip) {
        mirrorChip.className = cls;
        mirrorChip.textContent = text;
      }
    }
    row.hidden = false;
    applyChip(
      "tsr-chip tsr-chip--neutral",
      tr("research_section.invoke_state_loading")
    );
    const rid = wrap.getAttribute("data-tsr-rid") || "";
    const hz = wrap.getAttribute("data-tsr-hz") || "";
    try {
      const qs =
        "?limit=10" +
        (rid ? `&registry_entry_id=${encodeURIComponent(rid)}` : "") +
        (hz ? `&horizon=${encodeURIComponent(hz)}` : "");
      const r = await fetch("/api/sandbox/requests" + qs);
      const j = await r.json().catch(() => ({}));
      const items = (j && j.requests) || [];
      const match = items.find((x) => {
        const req = (x && x.request) || {};
        return String(req.packet_id || "") === String(requestPacketId);
      });
      if (!match) {
        applyChip(
          "tsr-chip tsr-chip--neutral",
          tr("research_section.invoke_state_unknown")
        );
        return;
      }
      // AGH v1 Patch 8 B2 — prefer the server-computed `lifecycle_state`
      // 4-state (queued / running / completed / blocked), which now
      // joins the sandbox_queue job row; fall back to legacy result-only
      // inference if the field is missing (older API / fixture runs).
      const resultPkt = match.result || null;
      const resultPayload = (resultPkt && resultPkt.payload) || {};
      const outcome = String(
        resultPayload.outcome || resultPayload.state || ""
      ).toLowerCase();
      const life = String(match.lifecycle_state || "").toLowerCase();
      const producedSuffix = (() => {
        const refs = humanizeProducedRefs(resultPayload);
        if (!refs) return "";
        return ` · ${refs}`;
      })();
      if (life === "running") {
        applyChip(
          "tsr-chip tsr-chip--warn tsr-invoke-state-running",
          tr("research_section.invoke_state_running")
        );
      } else if (life === "blocked" || outcome === "blocked" || outcome === "dlq" || outcome === "failed") {
        const reasons = Array.isArray(resultPayload.blocking_reasons)
          ? resultPayload.blocking_reasons
          : [];
        const reason = reasons.length ? String(reasons[0]).slice(0, 160) : "";
        applyChip(
          "tsr-chip tsr-chip--degraded tsr-invoke-state-blocked",
          tr("research_section.invoke_state_blocked") +
            (reason ? ` — ${reason}` : "")
        );
      } else if (life === "completed" || resultPkt) {
        applyChip(
          "tsr-chip tsr-chip--info tsr-invoke-state-completed",
          tr("research_section.invoke_state_completed") + producedSuffix
        );
      } else {
        applyChip(
          "tsr-chip tsr-chip--warn tsr-invoke-state-queued",
          tr("research_section.invoke_state_queued")
        );
      }
    } catch (_e) {
      applyChip(
        "tsr-chip tsr-chip--neutral",
        tr("research_section.invoke_state_unknown")
      );
    }
  }

  // AGH v1 Patch 8 B2 — derive a compact, locale-aware summary of the
  // artifact-like refs a SandboxResult produced (e.g. rerun_ref,
  // factor_validation_run_id, produced_artifact_ids). Returns an empty
  // string if there is nothing to summarize.
  // AGH v1 Patch 8 B3 — per-registry-entry recent sandbox requests.
  // Pulls /api/sandbox/requests (server now joins the sandbox_queue job),
  // renders a compact, newest-first 5-row list with 4-state chips,
  // human-readable target_spec labels, and a <details> audit expander.
  // Kept dumb: no auto-poll. The caller triggers re-hydration after an
  // explicit enqueue so the operator gate is preserved.
  async function hydrateRecentSandboxRequests(containerId, rid, hz, lang) {
    const el = document.getElementById(containerId);
    if (!el) return;
    const isKo = String(lang || "ko").toLowerCase().startsWith("ko");
    const body = el.querySelector("[data-tsr-recent-loading], .tsr-recent-body");
    if (body) body.textContent = tr("research_section.invoke_state_loading");
    try {
      const qs =
        "?limit=5" +
        (rid ? `&registry_entry_id=${encodeURIComponent(rid)}` : "") +
        (hz ? `&horizon=${encodeURIComponent(hz)}` : "");
      const { ok, json } = await api("/api/sandbox/requests" + qs);
      if (!ok || !json || json.ok === false) {
        if (body) {
          body.className = "tsr-recent-body tsr-empty";
          body.textContent = tr("research_section.recent_requests_empty");
        }
        return;
      }
      const items = Array.isArray(json.requests) ? json.requests : [];
      if (!items.length) {
        if (body) {
          body.className = "tsr-recent-body tsr-empty";
          body.textContent = tr("research_section.recent_requests_empty");
        }
        return;
      }
      const rows = items
        .slice(0, 5)
        .map((it) => {
          const req = (it && it.request) || {};
          const reqPayload = req.payload || {};
          const life = String(it.lifecycle_state || "queued").toLowerCase();
          const chipMap = {
            queued: "tsr-chip tsr-chip--warn",
            running: "tsr-chip tsr-chip--warn",
            completed: "tsr-chip tsr-chip--info",
            blocked: "tsr-chip tsr-chip--degraded",
          };
          const chipCls = chipMap[life] || "tsr-chip tsr-chip--neutral";
          const chipLabelKey =
            life === "running"
              ? "research_section.invoke_state_running"
              : life === "completed"
              ? "research_section.invoke_state_completed"
              : life === "blocked"
              ? "research_section.invoke_state_blocked"
              : "research_section.invoke_state_queued";
          const ts = reqPayload.target_spec || {};
          const fn = String(ts.factor_name || "");
          const un = String(ts.universe_name || "");
          const htp = String(ts.horizon_type || "");
          const rb = String(ts.return_basis || "");
          const targetLabel = [fn, un, htp, rb].filter(Boolean).join(" · ");
          const when = String(req.created_at_utc || "").slice(0, 16).replace("T", " ");
          const rationale = String(reqPayload.rationale || "").slice(0, 160);
          const resultPayload = (it.result && it.result.payload) || {};
          const produced = humanizeProducedRefs(resultPayload);
          const auditJson = JSON.stringify(
            { request: req, result: it.result || null, job: it.job || null },
            null,
            2
          );
          return (
            `<li class="tsr-recent-row" data-tsr-life="${escapeHtml(life)}">` +
            `<span class="${chipCls}">${escapeHtml(tr(chipLabelKey))}</span> ` +
            `<span class="mono" style="font-size:0.74rem">${escapeHtml(when)}</span> ` +
            (targetLabel
              ? `<span class="meta-sub"> · ${escapeHtml(targetLabel)}</span>`
              : "") +
            (produced
              ? ` <span class="ev-faint" style="font-size:0.72rem">· ${escapeHtml(produced)}</span>`
              : "") +
            (rationale
              ? `<div class="meta-sub" style="margin-top:0.2rem">${escapeHtml(rationale)}</div>`
              : "") +
            `<details style="margin-top:0.2rem"><summary>${escapeHtml(
              isKo ? "감사 로그" : "Audit"
            )}</summary><pre class="raw-ids" style="white-space:pre-wrap">${escapeHtml(
              auditJson
            )}</pre></details>` +
            `</li>`
          );
        })
        .join("");
      if (body) {
        body.className = "tsr-recent-body";
        body.innerHTML = `<ul class="tsr-recent-list">${rows}</ul>`;
      }
    } catch (_e) {
      if (body) {
        body.className = "tsr-recent-body tsr-empty";
        body.textContent = tr("research_section.recent_requests_empty");
      }
    }
  }

  function humanizeProducedRefs(resultPayload) {
    if (!resultPayload || typeof resultPayload !== "object") return "";
    const refs = [];
    const collect = (val) => {
      if (!val) return;
      if (Array.isArray(val)) {
        val.forEach((v) => collect(v));
      } else if (typeof val === "string" && val.trim()) {
        refs.push(val.trim());
      }
    };
    collect(resultPayload.produced_artifact_ids);
    collect(resultPayload.produced_refs);
    collect(resultPayload.rerun_ref);
    collect(resultPayload.factor_validation_run_id);
    if (!refs.length) return "";
    return tr("research_section.produced_refs_summary").replace(
      "{count}",
      String(refs.length)
    );
  }

  document.addEventListener("click", async (ev) => {
    const t = ev.target;
    if (!t || !t.closest) return;
    const copyBtn = t.closest("[data-tsr-copy-cli]");
    if (copyBtn) {
      const wrap = copyBtn.closest(".tsr-research-invoke");
      const cli = wrap ? wrap.querySelector("[data-tsr-cli]") : null;
      const text = cli ? cli.textContent || "" : "";
      try {
        await navigator.clipboard.writeText(text);
      } catch (_) {}
      const res = wrap ? wrap.querySelector("[data-tsr-enqueue-result]") : null;
      if (res) res.textContent = tr("research_section.invoke_copy_done");
      return;
    }
    const refreshBtn = t.closest("[data-tsr-invoke-refresh]");
    if (refreshBtn) {
      const wrap = refreshBtn.closest(".tsr-research-invoke");
      const rpid = wrap ? wrap.getAttribute("data-tsr-request-packet-id") : "";
      if (rpid) await tsrInvokePollState(wrap, rpid);
      return;
    }
    const eqBtn = t.closest("[data-tsr-enqueue-sandbox]");
    if (eqBtn) {
      const wrap = eqBtn.closest(".tsr-research-invoke");
      const res = wrap ? wrap.querySelector("[data-tsr-enqueue-result]") : null;
      if (res) res.textContent = tr("research_section.invoke_state_loading");
      try {
        const cited = String(eqBtn.getAttribute("data-cited") || "")
          .split(/\s+/)
          .filter(Boolean);
        const body = {
          sandbox_kind: "validation_rerun",
          registry_entry_id: eqBtn.getAttribute("data-rid") || "",
          horizon: eqBtn.getAttribute("data-hz") || "",
          target_spec: {
            factor_name: eqBtn.getAttribute("data-fn") || "",
            universe_name: eqBtn.getAttribute("data-un") || "",
            horizon_type: eqBtn.getAttribute("data-htp") || "",
            return_basis: eqBtn.getAttribute("data-rb") || "",
          },
          rationale: eqBtn.getAttribute("data-rationale") || "ui operator enqueue",
          cited_evidence_packet_ids: cited.length ? cited : [eqBtn.getAttribute("data-rid") || "ui"],
        };
        const r = await fetch("/api/sandbox/enqueue", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        const j = await r.json().catch(() => ({}));
        if (!r.ok || !j.ok) {
          const serverErr = j && j.error ? String(j.error) : String(r.status || "");
          let headline = tr("research_section.invoke_error_server");
          if (r.status === 403 || /ui_invoke_disabled/i.test(serverErr)) {
            headline = tr("research_section.invoke_error_disabled");
          } else if (r.status === 400) {
            headline = tr("research_section.invoke_error_validation");
          }
          if (res) {
            res.innerHTML =
              `<span class="tsr-chip tsr-chip--degraded">${escapeHtml(
                headline
              )}</span> ` +
              `<details style="display:inline-block;margin-left:0.3rem"><summary>${escapeHtml(
                tr("research_section.invoke_error_raw")
              )}</summary><code>${escapeHtml(serverErr)}</code></details>`;
          }
        } else {
          const rpid = String(j.request_packet_id || "");
          const operatorNote = String(j.operator_note || "");
          const cliHint = String(j.cli_hint || "");
          if (wrap && rpid) {
            wrap.setAttribute("data-tsr-request-packet-id", rpid);
          }
          if (res) {
            res.innerHTML =
              `<span class="tsr-chip tsr-chip--info tsr-invoke-state-queued">${escapeHtml(
                tr("research_section.invoke_state_queued")
              )}</span>` +
              (operatorNote
                ? ` <span class="invoke-inline-msg">${escapeHtml(
                    operatorNote
                  )}</span>`
                : "") +
              (cliHint
                ? ` <code class="invoke-cli-hint">${escapeHtml(cliHint)}</code>`
                : "");
          }
          // One deferred poll — gives Supabase commit time to settle,
          // then surfaces the server-authoritative queue state. The
          // operator can re-poll manually; we do not loop.
          if (wrap && rpid) {
            window.setTimeout(() => tsrInvokePollState(wrap, rpid), 1500);
          }
          // AGH v1 Patch 8 B3 — auto-refresh the per-entry recent list
          // exactly ONCE after a successful enqueue, so the new request
          // shows up without the operator clicking a manual refresh.
          // Kept to a single shot to preserve the operator gate (no
          // background polling loop).
          if (wrap) {
            const recentSid = wrap.getAttribute("data-tsr-recent-mount") || "";
            const rid2 = wrap.getAttribute("data-tsr-rid") || "";
            const hz2 = wrap.getAttribute("data-tsr-hz") || "";
            if (recentSid) {
              const langAttr =
                document.documentElement.getAttribute("data-lang") || "ko";
              window.setTimeout(
                () =>
                  hydrateRecentSandboxRequests(recentSid, rid2, hz2, langAttr),
                1500
              );
            }
          }
        }
      } catch (e) {
        if (res)
          res.innerHTML =
            `<span class="tsr-chip tsr-chip--degraded">${escapeHtml(
              tr("research_section.invoke_error_server")
            )}</span> <code>${escapeHtml(String(e))}</code>`;
      }
    }
  });

  // AGH v1 Patch 6 — helper: human-readable active artifact label
  function humanizeActiveArtifactLabel(rs, aaid) {
    if (!rs || typeof rs !== "object") return String(aaid || "");
    const fam = String(rs.active_model_family_name || "").trim();
    const tf = String(rs.active_thesis_family || "").trim();
    const univ = String(rs.universe || "").trim();
    const parts = [fam || "active_artifact", tf || "", univ || ""].filter(Boolean);
    return parts.join(" · ") || String(aaid || "");
  }

  // AGH v1 Patch 6 — severity → chip class
  function tsrBadgeChipClass(sev) {
    const s = String(sev || "").toLowerCase();
    if (s === "warning" || s === "warn") return "tsr-chip tsr-chip--warn";
    if (s === "info") return "tsr-chip tsr-chip--info";
    if (s === "neutral") return "tsr-chip tsr-chip--neutral";
    if (s === "degraded" || s === "danger") return "tsr-chip tsr-chip--degraded";
    return "tsr-chip tsr-chip--neutral";
  }

  // AGH v1 Patch 6 — Top summary rail (block 1 of 4).
  // Inputs: research_status_badges_v1 + recent_governed_applies_for_horizon.
  // Output: calm chip row (change chip + badge chips + active_artifact chip),
  // with NO raw packet ids or engineering codes — only label_ko / label_en.
  // AGH v1 Patch 7 A5 — humanise "time since event" for rail / lineage
  // sub-lines so tooltip density carries information instead of raw ISO.
  function humanizeTimeDelta(isoStr, lang) {
    const isKo = String(lang || "ko").toLowerCase().startsWith("ko");
    if (!isoStr) return "";
    const then = Date.parse(String(isoStr));
    if (!isFinite(then)) return "";
    const deltaSec = Math.max(0, (Date.now() - then) / 1000);
    if (deltaSec < 60) return isKo ? "방금 전" : "just now";
    const m = Math.round(deltaSec / 60);
    if (m < 60) return isKo ? `${m}분 전` : `${m}m ago`;
    const h = Math.round(m / 60);
    if (h < 48) return isKo ? `${h}시간 전` : `${h}h ago`;
    const d = Math.round(h / 24);
    if (d < 14) return isKo ? `${d}일 전` : `${d}d ago`;
    const w = Math.round(d / 7);
    return isKo ? `${w}주 전` : `${w}w ago`;
  }

  function renderTodaySummaryRailHtml(j, lang) {
    const isKo = String(lang || "ko").toLowerCase().startsWith("ko");
    const rsb = (j && j.research_status_badges_v1) || {};
    const badges = Array.isArray(rsb.badges) ? rsb.badges : [];
    const rs = (j && j.registry_surface_v1) || {};
    const recent = Array.isArray(rs.recent_governed_applies_for_horizon)
      ? rs.recent_governed_applies_for_horizon
      : [];
    const needsRebuild =
      rs && rs.needs_db_rebuild === true ? true : false;
    const changeChip = (() => {
      if (!recent.length) return "";
      const top = recent[0] || {};
      const when = String(top.applied_at_utc || "").slice(0, 10);
      const delta = humanizeTimeDelta(top.applied_at_utc, lang);
      const outcome = String(top.outcome || "").trim();
      const fromAid = humanizeActiveArtifactLabel(rs, top.from_active_artifact_id || "");
      const toAid = humanizeActiveArtifactLabel(rs, top.to_active_artifact_id || "");
      const labelText = isKo
        ? `오늘 거버넌스 적용: ${when}`
        : `Governed apply today: ${when}`;
      // AGH v1 Patch 7 A2·A5 — rail tooltip sub is now a multi-part
      // string joined by " · " so the shared tooltip renders each fact
      // on its own row: outcome · delta · from→to.
      const subParts = [];
      if (outcome) subParts.push(outcome);
      if (delta) subParts.push(delta);
      if (fromAid && toAid) subParts.push(`${fromAid} → ${toAid}`);
      else if (toAid) subParts.push(`→ ${toAid}`);
      // AGH v1 Patch 8 A5 — enrich the rail tooltip sub content with
      // the shared what_changed one-liner + confidence_band, so the hover
      // preview gives operators "why this matters" without click-through.
      const ttCtx = extractTooltipContextFromTsr(j, isKo);
      if (ttCtx && ttCtx.sub_suffix) subParts.push(ttCtx.sub_suffix);
      const sub = subParts.join(" · ");
      const chipClass = needsRebuild
        ? "tsr-chip tsr-chip--warn"
        : "tsr-chip tsr-chip--change";
      return `<span class="${chipClass}" title="${escapeHtml(sub)}" data-tsr-tt-label="${escapeHtml(labelText)}" data-tsr-tt-sub="${escapeHtml(sub)}"><span class="chip-dot"></span>${escapeHtml(labelText)}</span>`;
    })();
    const badgeChips = badges
      .map((b) => {
        if (!b || typeof b !== "object") return "";
        const sev = String(b.severity || "neutral");
        const lab = isKo ? String(b.label_ko || "") : String(b.label_en || "");
        if (!lab) return "";
        return `<span class="${tsrBadgeChipClass(sev)}">${escapeHtml(lab)}</span>`;
      })
      .filter(Boolean)
      .join("");
    const aaid = String(rs.active_artifact_id || "").trim();
    const aaidLabel = humanizeActiveArtifactLabel(rs, aaid);
    const activeChip = aaid
      ? `<span class="tsr-chip" title="${escapeHtml(aaid)}"><span class="chip-dot"></span>${escapeHtml(aaidLabel)}</span>`
      : "";
    const body = [changeChip, badgeChips, activeChip].filter(Boolean).join("");
    if (!body) {
      return `<div class="tsr-rail tsr-empty"><span class="tsr-empty-head">${escapeHtml(
        isKo ? "오늘 요약" : "Today summary"
      )}</span> · ${escapeHtml(
        isKo ? "최근 거버넌스 이벤트 없음" : "no recent governed events"
      )}</div>`;
    }
    return `<div class="tsr-rail" role="region" aria-label="${escapeHtml(
      isKo ? "오늘 요약" : "Today summary"
    )}">${body}</div>`;
  }

  // AGH v1 Patch 6 — Primary object panel (block 2 of 4).
  // AGH v1 Patch 7 A2 — typography hierarchy added: hero (h2) = asset +
  // one-line take; subhead/body split for "why now" / "what changed";
  // foot line for horizon · model family · as-of timestamp. The raw
  // strings are unchanged; only visual weight and grouping change.
  function renderTodayPrimaryPanelHtml(j, lang) {
    const isKo = String(lang || "ko").toLowerCase().startsWith("ko");
    const msg = (j && j.message) || {};
    const title = String(j.asset_id || "");
    const oneLine = String(msg.one_line_take || "").trim();
    const horizonLabel = String(j.horizon_label || "");
    const fam = String(j.active_model_family || "");
    const foot = [horizonLabel, fam, String(j.as_of_utc || "")]
      .filter(Boolean)
      .map(escapeHtml)
      .join(" · ");
    const whyNow = String(msg.why_now || "").trim();
    const whatChanged = String(msg.what_changed || "").trim();
    const heroHeadline = oneLine
      ? `<h2 class="tsr-hero" data-tsr-hero="1">${escapeHtml(title)} — ${escapeHtml(oneLine)}</h2>`
      : `<h2 class="tsr-hero" data-tsr-hero="1">${escapeHtml(title)}</h2>`;
    const whyNowBlock = whyNow
      ? `<div class="tsr-subhead" data-tsr-subhead="why_now">${escapeHtml(
          isKo ? "Why now" : "Why now"
        )}</div><p class="tsr-body" data-tsr-body="why_now">${escapeHtml(whyNow)}</p>`
      : `<p class="tsr-body ev-faint" data-tsr-body="why_now_empty">${escapeHtml(
          tr("tsr.primary.why_now_empty")
        )}</p>`;
    const whatChangedBlock = whatChanged
      ? `<div class="tsr-subhead" data-tsr-subhead="what_changed">${escapeHtml(
          isKo ? "무엇이 바뀌었나" : "What changed"
        )}</div><p class="tsr-body" data-tsr-body="what_changed">${escapeHtml(whatChanged)}</p>`
      : "";
    // AGH v1 Patch 8 A2 — hero stack (why_now / confidence / caveat / next).
    const stackHtml = renderTodayWhyNowConfidenceCaveatNextHtml(j, lang);
    return (
      `<div class="tsr-primary">` +
      heroHeadline +
      `<div class="tsr-foot meta-sub" data-tsr-foot="primary_meta">${foot}</div>` +
      whyNowBlock +
      whatChangedBlock +
      stackHtml +
      `</div>`
    );
  }

  // AGH v1 Patch 8 A2 — Today hero-stack renderer.
  //
  // Surfaces the 4 things a user needs to decide, directly below the hero
  // headline, without drilling into `<details>`:
  //   1. why_now    — from `message.why_now`
  //   2. confidence — from `message.confidence_band`
  //   3. caveat     — from `message.what_remains_unproven`
  //   4. next_step  — from `sandbox_options_v1.options[0]` (bounded CTA)
  //
  // No autonomy copy. The "next step" is a visible CTA that scrolls to
  // the Research bounded_next invoke card — it NEVER mutates registry
  // state. If there is no active bounded option, we render an empty
  // note rather than fabricating one.
  function renderTodayWhyNowConfidenceCaveatNextHtml(j, lang) {
    const isKo = String(lang || "ko").toLowerCase().startsWith("ko");
    const msg = (j && j.message) || {};
    const whyNow = String(msg.why_now || "").trim();
    const confidenceBand = String(msg.confidence_band || "").trim();
    const caveat = String(msg.what_remains_unproven || "").trim();
    const so = (j && j.sandbox_options_v1) || {};
    const soOpts = Array.isArray(so.options) ? so.options : [];
    const firstOpt = soOpts.length ? soOpts[0] : null;
    function row(key, headKey, body, emptyKey) {
      const content = body
        ? `<div class="tsr-why-now-body" data-tsr-stack-body="${escapeHtml(key)}">${escapeHtml(body)}</div>`
        : `<div class="tsr-why-now-body ev-faint" data-tsr-stack-empty="${escapeHtml(key)}">${escapeHtml(
            tr(emptyKey)
          )}</div>`;
      return (
        `<div class="tsr-why-now-row" data-tsr-stack-row="${escapeHtml(key)}">` +
        `<div class="tsr-why-now-head" data-tsr-stack-head="${escapeHtml(key)}">${escapeHtml(
          tr(headKey)
        )}</div>` +
        content +
        `</div>`
      );
    }
    const whyNowRow = row(
      "why_now",
      "tsr.today.why_now.head",
      whyNow,
      "tsr.today.why_now.empty"
    );
    const confidenceRow = row(
      "confidence",
      "tsr.today.confidence.head",
      confidenceBand,
      "tsr.today.confidence.empty"
    );
    const caveatRow = row(
      "caveat",
      "tsr.today.caveat.head",
      caveat,
      "tsr.today.caveat.empty"
    );
    let nextBody = "";
    if (firstOpt && typeof firstOpt === "object") {
      const label = String(
        (isKo ? firstOpt.label_ko : firstOpt.label_en) || ""
      ).trim();
      const ctaLabel = label
        ? `${tr("tsr.today.next.cta_prefix")} · ${label}`
        : tr("tsr.today.next.cta_prefix");
      nextBody =
        `<div class="tsr-why-now-body" data-tsr-stack-body="next_step">` +
        `<button type="button" class="btn btn-xs" data-tsr-jump-to-invoke="1">${escapeHtml(
          ctaLabel
        )}</button>` +
        `<div class="tsr-why-now-operator-note" data-tsr-stack-op-note="1">${escapeHtml(
          tr("tsr.today.next.operator_note")
        )}</div>` +
        `</div>`;
    } else {
      nextBody = `<div class="tsr-why-now-body ev-faint" data-tsr-stack-empty="next_step">${escapeHtml(
        tr("tsr.today.next.empty")
      )}</div>`;
    }
    const nextRow =
      `<div class="tsr-why-now-row" data-tsr-stack-row="next_step">` +
      `<div class="tsr-why-now-head" data-tsr-stack-head="next_step">${escapeHtml(
        tr("tsr.today.next.head")
      )}</div>` +
      nextBody +
      `</div>`;
    return (
      `<div class="tsr-why-now-stack" data-tsr-why-now-stack="1">` +
      `<div class="tsr-subhead" data-tsr-subhead="today_stack">${escapeHtml(
        tr("tsr.today.stack.head")
      )}</div>` +
      whyNowRow +
      confidenceRow +
      caveatRow +
      nextRow +
      `</div>`
    );
  }

  // AGH v1 Patch 6 — Decision-depth stack (block 3 of 4, progressive disclosure).
  function renderTodayDecisionStackHtml(j, lang) {
    const isKo = String(lang || "ko").toLowerCase().startsWith("ko");
    const msg = (j && j.message) || {};
    const inf = (j && j.information) || {};
    const res = (j && j.research) || {};
    function ul(arr) {
      const a = Array.isArray(arr) ? arr : [];
      if (!a.length) return `<li class="sub">—</li>`;
      return a.map((x) => `<li>${escapeHtml(String(x))}</li>`).join("");
    }
    const oneLine = String(msg.one_line_take || "").trim();
    const oneLineHtml = oneLine
      ? `<p class="one-line">${escapeHtml(oneLine)}</p>`
      : `<p class="one-line ev-faint">${escapeHtml(
          isKo ? "한 줄 요약 준비되지 않음" : "One-line take not ready"
        )}</p>`;
    const deeper = String(res.deeper_rationale || "").trim();
    const unproven = String(msg.what_remains_unproven || "").trim();
    const watch = String(msg.what_to_watch || "").trim();
    function section(labelKo, labelEn, bodyHtml) {
      return (
        `<details><summary>${escapeHtml(isKo ? labelKo : labelEn)}</summary>` +
        `<div class="tsr-drill">${bodyHtml}</div></details>`
      );
    }
    const deeperSec = deeper
      ? section(
          "해석 근거 자세히",
          "Why plausible — deeper rationale",
          `<p>${escapeHtml(deeper)}</p>`
        )
      : "";
    const signalsSec = section(
      "뒷받침 · 반증 신호",
      "Supporting and opposing signals",
      `<span class="k">${escapeHtml(isKo ? "뒷받침" : "Supporting")}</span><ul>${ul(
        inf.supporting_signals
      )}</ul><span class="k">${escapeHtml(isKo ? "반증" : "Opposing")}</span><ul>${ul(
        inf.opposing_signals
      )}</ul>`
    );
    const unprovenSec = unproven
      ? section(
          "아직 미증명",
          "What remains unproven",
          `<p>${escapeHtml(unproven)}</p>`
        )
      : "";
    const watchSec = watch
      ? section("계속 볼 것", "What to watch", `<p>${escapeHtml(watch)}</p>`)
      : "";
    return (
      `<div class="tsr-decision">` +
      oneLineHtml +
      deeperSec +
      signalsSec +
      unprovenSec +
      watchSec +
      `</div>`
    );
  }

  // AGH v1 Patch 6 — Audit-only helper. Emits raw engineering identifiers
  // inside a <details> progressive-disclosure block. Deliberately kept
  // outside the primary-UI TSR renderer surface so raw snake_case tokens
  // (active_artifact_id / registry_entry_id / message_snapshot_id) don't
  // tip into user-visible copy.
  // AGH v1 Patch 7 A2 — now renders the *inner* rows only; the outer
  // <details> shell is emitted by the consolidated audit block so we end
  // up with a single audit disclosure instead of one-per-block.
  function renderTodayEvidenceRawIdsAuditHtml(rs, rlj, isKo) {
    const aaid = String((rs && rs.active_artifact_id) || "").trim();
    const rid = String((rs && rs.registry_entry_id) || "").trim();
    const mid = String((rlj && rlj.message_snapshot_id) || "").trim();
    const rows = [];
    if (aaid) rows.push(`active_artifact_id: ${aaid}`);
    if (rid) rows.push(`registry_entry_id: ${rid}`);
    if (mid) rows.push(`message_snapshot_id: ${mid}`);
    if (!rows.length) return "";
    const escaped = rows.map(escapeHtml).join("<br/>");
    return `<div class="raw-ids">${escaped}</div>`;
  }

  // AGH v1 Patch 7 A2 — compact "recent governance activity" mini-list.
  // Shows up to 3 most-recent governed applies with a humanised time
  // delta (e.g. "2d ago") and the from→to active-artifact flow.
  function renderTodayRecentActivityHtml(j, lang) {
    const isKo = String(lang || "ko").toLowerCase().startsWith("ko");
    const rs = (j && j.registry_surface_v1) || {};
    const recent = Array.isArray(rs.recent_governed_applies_for_horizon)
      ? rs.recent_governed_applies_for_horizon.slice(0, 3)
      : [];
    const head = tr("tsr.recent.head");
    if (!recent.length) {
      return (
        `<div class="tsr-recent-activity" data-tsr-recent="empty">` +
        `<div class="tsr-subhead">${escapeHtml(head)}</div>` +
        `<div class="ev-faint tsr-foot">${escapeHtml(
          tr("tsr.recent.empty")
        )}</div>` +
        `</div>`
      );
    }
    const rows = recent
      .map((r) => {
        if (!r || typeof r !== "object") return "";
        const delta = humanizeTimeDelta(r.applied_at_utc, lang);
        const when = String(r.applied_at_utc || "").slice(0, 16);
        const toAid = humanizeActiveArtifactLabel(rs, r.to_active_artifact_id || "");
        const fromAid = humanizeActiveArtifactLabel(rs, r.from_active_artifact_id || "");
        const flow =
          fromAid && toAid
            ? `${fromAid} → ${toAid}`
            : toAid
              ? `→ ${toAid}`
              : "";
        const timeLabel = delta || when;
        const kindLabel = tr("tsr.recent.apply");
        return (
          `<div class="tsr-mini-row" title="${escapeHtml(when)}">` +
          `<span class="tsr-mini-time">${escapeHtml(timeLabel)}</span>` +
          `<span class="tsr-mini-flow">` +
          `<span class="tsr-chip tsr-chip--apply"><span class="chip-dot"></span>${escapeHtml(kindLabel)}</span>` +
          `<span class="tsr-mini-arrow">${escapeHtml(flow)}</span>` +
          `</span>` +
          `</div>`
        );
      })
      .filter(Boolean)
      .join("");
    return (
      `<div class="tsr-recent-activity" data-tsr-recent="list">` +
      `<div class="tsr-subhead">${escapeHtml(head)}</div>` +
      rows +
      `</div>`
    );
  }

  // AGH v1 Patch 6 — Evidence strip (block 4 of 4).
  // AGH v1 Patch 7 A2 — audit disclosure is now *consolidated*: the old
  // standalone raw-ids <details> is folded into a single "Audit · raw
  // identifiers" block that lives at the bottom of the Today surface.
  // The evidence strip itself is now about the *evidence*, not audit.
  function renderTodayEvidenceStripHtml(j, lang) {
    const isKo = String(lang || "ko").toLowerCase().startsWith("ko");
    const rs = (j && j.registry_surface_v1) || {};
    const aaid = String(rs.active_artifact_id || "").trim();
    const aaidLabel = humanizeActiveArtifactLabel(rs, aaid);
    const fam = String(rs.active_model_family_name || "");
    const tf = String(rs.active_thesis_family || "");
    const univ = String(rs.universe || "");
    const ridHead = tr("tsr.evidence.head");
    const labelLine = aaid
      ? `<div><span class="ev-label">${escapeHtml(
          tr("tsr.evidence.active_artifact")
        )}:</span> ${escapeHtml(aaidLabel)}</div>`
      : `<div class="ev-faint">${escapeHtml(
          tr("tsr.evidence.no_artifact")
        )}</div>`;
    const metaLine =
      (fam || tf || univ)
        ? `<div class="ev-faint tsr-foot">${[fam, tf, univ]
            .filter(Boolean)
            .map(escapeHtml)
            .join(" · ")}</div>`
        : "";
    const recentHtml = renderTodayRecentActivityHtml(j, lang);
    return (
      `<div class="tsr-evidence">` +
      `<h4 class="tsr-subhead">${escapeHtml(ridHead)}</h4>` +
      labelLine +
      metaLine +
      recentHtml +
      `</div>`
    );
  }

  // AGH v1 Patch 7 A2 — consolidated audit block. Pulls raw identifiers
  // from registry_surface_v1 + replay_lineage_join_v1 into ONE <details>
  // at the bottom of the Today surface. This replaces:
  //   - the per-block raw_ids <details> that used to live inside the
  //     evidence strip
  //   - the "Show legacy MIR detail (advanced)" block at the very bottom
  //     of renderTodayObjectDetailHtml, which is now folded inside this
  //     same audit disclosure as an inner <details>.
  function renderTodayConsolidatedAuditHtml(j, lang, innerLegacyHtml) {
    const isKo = String(lang || "ko").toLowerCase().startsWith("ko");
    const rs = (j && j.registry_surface_v1) || {};
    const rlj = (j && j.replay_lineage_join_v1) || {};
    const rawIds = renderTodayEvidenceRawIdsAuditHtml(rs, rlj, isKo);
    if (!rawIds && !innerLegacyHtml) return "";
    const head = tr("tsr.audit.head");
    const note = tr("tsr.audit.note");
    const rawSection = rawIds
      ? `<section class="tsr-audit-section" data-tsr-audit="raw_ids">` +
        `<div class="tsr-subhead">${escapeHtml(tr("tsr.evidence.raw_ids"))}</div>` +
        rawIds +
        `</section>`
      : "";
    const legacySection = innerLegacyHtml
      ? `<section class="tsr-audit-section" data-tsr-audit="legacy_mir">${innerLegacyHtml}</section>`
      : "";
    return (
      `<details class="tsr-audit" data-tsr-audit="1">` +
      `<summary>${escapeHtml(head)}</summary>` +
      `<div class="tsr-audit-body">` +
      `<p class="ev-faint tsr-foot">${escapeHtml(note)}</p>` +
      rawSection +
      legacySection +
      `</div>` +
      `</details>`
    );
  }

  function renderTodayObjectDetailHtml(j) {
    const msg = j.message || {};
    const inf = j.information || {};
    const res = j.research || {};
    const links = res.links || {};
    const spec = j.spectrum || {};
    const lang = cockpitLang();
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
    const railHtml = renderTodaySummaryRailHtml(j, lang);
    const primaryHtml = renderTodayPrimaryPanelHtml(j, lang);
    const decisionHtml = renderTodayDecisionStackHtml(j, lang);
    const evidenceHtml = renderTodayEvidenceStripHtml(j, lang);
    const researchStructuredHtml = renderResearchStructuredSection(j, lang);
    const replayLineageHtml = renderReplayGovernanceLineageCompactHtml(j, lang);
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

    // AGH v1 Patch 7 A2 — fold the "legacy MIR detail" progressive-disclosure
    // block into the consolidated audit <details>. Raw identifiers + legacy
    // MIR now live in ONE audit shell at the bottom instead of two.
    const legacyInner =
      `<p class="meta tsr-foot">${metaLine}</p>` +
      `<div class="mir-block"><h4>${escapeHtml(tr("today_detail.section_message"))}</h4>${msgBlock}</div>` +
      registryBlock +
      `<div class="mir-block"><h4>${escapeHtml(tr("today_detail.section_information"))}</h4>${infBlock}</div>` +
      `<div class="mir-block"><h4>${escapeHtml(tr("today_detail.section_research"))}</h4>${resBlock}</div>`;
    const auditHtml = renderTodayConsolidatedAuditHtml(j, lang, legacyInner);
    return (
      railHtml +
      primaryHtml +
      decisionHtml +
      evidenceHtml +
      researchStructuredHtml +
      replayLineageHtml +
      auditHtml
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
          `<h3>${escapeHtml(tr("home.sample.pack_title"))}</h3>` +
          `<p class="meta"><span class="mono">${escapeHtml(String(pk.pack_id || ""))}</span> · ${escapeHtml(String(pk.as_of_utc || ""))}</p>` +
          `<p class="sub">${escapeHtml(tr("home.sample.pack_intro"))}</p>` +
          `<div class="brief-label" style="margin-top:0.5rem">${escapeHtml(tr("home.sample.investor_route"))}</div>` +
          stepsHtml +
          `<p class="meta" style="margin-top:0.5rem">${escapeHtml(tr("home.sample.price_overlay"))}: ` +
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
        `<a href="#" class="feed-utility-link" data-jump="advanced">${escapeHtml(tr("home.jump.manage_alerts"))}</a></div>`
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
        `<a href="#" class="feed-utility-link" data-jump="journal">${escapeHtml(tr("home.jump.open_journal"))}</a></div>`
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
    // AGH v1 Patch 6 — operator-gated UI enqueue toggle.
    // Enable via URL ?ui_invoke=1 (e.g. dev / demo) OR via a runtime
    // probe by calling the enqueue endpoint with an invalid body and
    // observing whether the server responds 403 (disabled) vs 400/200.
    try {
      const u = new URL(window.location.href);
      const flag = u.searchParams.get("ui_invoke");
      if (flag === "1") window.__metisUiInvokeEnabled = true;
    } catch (_) {}
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
    hydrateBundleTierChip();
    pollNotif();
    setInterval(pollNotif, 8000);
  }

  // AGH v1 Patch 8 D3 — bundle-tier badge (demo / sample / production) in
  // the utility nav row. One-shot hydration from /api/runtime/health on
  // startup; no background polling. The chip is hidden until the tier is
  // known so we never flash a default label.
  async function hydrateBundleTierChip() {
    const el = document.getElementById("tsr-bundle-tier");
    if (!el) return;
    try {
      const { ok, json } = await api(
        "/api/runtime/health?lang=" + encodeURIComponent(cockpitLang() || "ko")
      );
      if (!ok || !json || json.ok === false) return;
      const tier = String(
        (((json || {}).mvp_brain_gate || {}).brain_bundle_tier || "")
      ).toLowerCase();
      if (!tier) return;
      const key =
        tier === "production"
          ? "tsr.bundle_tier.production"
          : tier === "sample"
          ? "tsr.bundle_tier.sample"
          : "tsr.bundle_tier.demo";
      el.textContent = tr(key);
      const cls =
        tier === "production"
          ? "tsr-chip tsr-chip--info tsr-bundle-tier-chip"
          : tier === "sample"
          ? "tsr-chip tsr-chip--neutral tsr-bundle-tier-chip"
          : "tsr-chip tsr-chip--warn tsr-bundle-tier-chip";
      el.className = cls;
      el.setAttribute("title", tr("tsr.bundle_tier.tip"));
      el.setAttribute("data-tier", tier);
      el.hidden = false;
    } catch (_e) {}
  }

  initCockpit();
})();
