/* global fetch */
(function () {
  const $ = (id) => document.getElementById(id);

  const OBJECT_SECTIONS = [
    { id: "brief", label: "Brief" },
    { id: "why_now", label: "Why now" },
    { id: "what_could_change", label: "What could change" },
    { id: "evidence", label: "Evidence" },
    { id: "history", label: "History" },
    { id: "ask_ai", label: "Ask AI" },
    { id: "advanced", label: "Advanced" },
  ];

  /** @type {Record<string, unknown> | null} */
  let lastFeed = null;

  async function api(path, opts) {
    const r = await fetch(path, opts);
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

  async function loadHomeFeed() {
    const { json } = await api("/api/home/feed");
    lastFeed = json && json.ok ? json : lastFeed;
    const root = $("home-feed-root");
    if (!json.ok) {
      root.innerHTML = `<p class="empty">${escapeHtml(JSON.stringify(json))}</p>`;
      return;
    }

    const t = json.today || {};
    const act = t.action_needed;
    const actHtml = act
      ? `<div class="action-flag">Review or action may be warranted on the surface above.</div>`
      : `<div class="action-flag passive">No urgent cockpit action implied from this loadout — scan blocks below.</div>`;

    const parts = [];
    parts.push(
      `<div class="feed-card"><h3>Today</h3><div class="sub" style="font-weight:600;color:var(--text)">${escapeHtml(t.title || "")}</div>` +
        `<div class="body" style="margin-top:0.5rem">${fmtBody(t.body || "")}</div>${actHtml}</div>`
    );

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
      `<div class="feed-card"><h3>Watchlist</h3>` +
        (wempty
          ? `<p class="sub"><strong>${escapeHtml(wempty.title)}</strong> — ${escapeHtml(wempty.why)} <em>${escapeHtml(wempty.fills_when)}</em></p>`
          : "") +
        (whtml ? `<ul class="feed-list">${whtml}</ul>` : "") +
        (wch ? `<div class="brief-label" style="margin-top:0.5rem">What changed</div><ul class="feed-list">${wch}</ul>` : "") +
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
      `<div class="feed-card"><h3>Research in progress</h3>` +
        (rempty
          ? `<p class="sub"><strong>${escapeHtml(rempty.title)}</strong> — ${escapeHtml(rempty.why)} <em>${escapeHtml(rempty.fills_when)}</em></p>`
          : "") +
        (rhtml ? `<ul class="feed-list">${rhtml}</ul>` : `<p class="sub">No recent thread rows in the job registry.</p>`) +
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
      `<div class="feed-card"><h3>Alerts</h3>` +
        (ahtml
          ? `<ul class="feed-list">${ahtml}</ul>`
          : `<p class="sub"><strong>${escapeHtml(ae.title || "No alerts")}</strong> — ${escapeHtml(ae.why || "")} <em>${escapeHtml(ae.fills_when || "")}</em></p>`) +
        `<button type="button" class="btn" data-jump="advanced">Manage alerts in Advanced</button></div>`
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
      `<div class="feed-card"><h3>Decision journal</h3>` +
        (jhtml
          ? `<ul class="feed-list">${jhtml}</ul>`
          : je
            ? `<p class="sub"><strong>${escapeHtml(je.title)}</strong> — ${escapeHtml(je.why)} <em>${escapeHtml(je.fills_when)}</em></p>`
            : "") +
        `<button type="button" class="btn" data-jump="journal">Open full Journal</button></div>`
    );

    const ab = json.ask_ai_brief || {};
    const sc = ab.shortcuts || [];
    let sclist = "";
    sc.forEach((s) => {
      sclist += `<li>${escapeHtml(s.label)}</li>`;
    });
    parts.push(
      `<div class="feed-card"><h3>Ask AI brief</h3><p class="body">${escapeHtml(ab.daily_line || "")}</p>` +
        `<ul class="feed-list" style="font-size:0.82rem">${sclist}</ul>` +
        `<button type="button" class="btn" data-jump="ask_ai">Open Ask AI</button></div>`
    );

    const ps = json.portfolio_snapshot || {};
    parts.push(
      `<div class="feed-card"><h3>Portfolio snapshot</h3><p class="sub">${escapeHtml(ps.copy || "")}</p>` +
        `<span class="badge default">${escapeHtml(ps.state || "stub")}</span></div>`
    );

    root.innerHTML = parts.join("");
    wireHomeJumpButtons(root);
    syncAskAiFromFeed();
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
    if (wch) blocks.push(`<div class="feed-card"><h3>What changed</h3><ul class="feed-list">${wch}</ul></div>`);
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
    host.innerHTML = "";
    OBJECT_SECTIONS.forEach((S, i) => {
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
    loadObjectSection(OBJECT_SECTIONS[0].id);
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

  buildObjectTabs();
  buildAskShortcuts();
  refreshMeta();
  loadHomeFeed();
  loadJournalDecisions();
  pollNotif();
  setInterval(pollNotif, 8000);
})();
