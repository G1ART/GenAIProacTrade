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

  async function api(path, opts) {
    const r = await fetch(path, opts);
    const j = await r.json().catch(() => ({}));
    return { ok: r.ok, status: r.status, json: j };
  }

  function showPanel(name) {
    document.querySelectorAll(".panel").forEach((p) => p.classList.remove("visible"));
    const el = document.getElementById("panel-" + name);
    if (el) el.classList.add("visible");
    document.querySelectorAll("#nav button.nav-main[data-panel]").forEach((b) => {
      b.classList.toggle("active", b.dataset.panel === name);
    });
  }

  document.querySelectorAll("#nav button.nav-main[data-panel]").forEach((btn) => {
    btn.addEventListener("click", () => {
      showPanel(btn.dataset.panel);
      if (btn.dataset.panel === "replay") loadReplay();
    });
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

  function badgeClass(kind) {
    if (kind === "closed_research_fixture") return "fixture";
    if (kind === "watchlist_item") return "watch";
    return "default";
  }

  function renderBrief(uf, runtimeHealth) {
    const b = uf && uf.brief;
    const host = $("brief-body");
    if (!b) {
      host.innerHTML = "<p class='empty'>Brief unavailable — reload bundle.</p>";
      return;
    }
    const badge = `<span class="badge ${badgeClass(b.object_kind)}">${escapeHtml(b.object_kind_label || b.object_kind)}</span>`;
    const sym = (b.symbols_preview || []).length
      ? `<div class="brief-block"><div class="brief-label">Cohort symbols</div><div class="brief-value">${escapeHtml(b.symbols_preview.join(", "))}</div></div>`
      : "";
    let rhBlock = "";
    const rh = runtimeHealth;
    if (rh && rh.ok) {
      const lines = (rh.plain_lines || []).map((l) => `<li>${escapeHtml(l)}</li>`).join("");
      rhBlock =
        `<div class="brief-block" style="margin-top:1rem;border-top:1px solid #2a3544;padding-top:0.85rem">` +
        `<div class="brief-label">Research runtime (Phase 51)</div>` +
        `<div class="brief-value"><strong>${escapeHtml(rh.headline || "")}</strong><br/>${escapeHtml(rh.subtext || "")}</div>` +
        `<ul style="margin:0.5rem 0 0 1rem;font-size:0.88rem;color:var(--muted)">${lines}</ul>` +
        `<details style="margin-top:0.5rem"><summary>Advanced (machine summary)</summary><pre class="mono" style="max-height:10rem;overflow:auto">${escapeHtml(
          JSON.stringify(rh.advanced || {}, null, 2)
        )}</pre></details></div>`;
    }
    host.innerHTML =
      badge +
      sym +
      `<div class="brief-block"><div class="brief-label">What is this?</div><div class="brief-value">${escapeHtml(b.object_kind_hint || "")}</div></div>` +
      `<div class="brief-block"><div class="brief-label">Current stance (plain)</div><div class="brief-value">${escapeHtml(b.stance_plain || "")}</div></div>` +
      `<div class="brief-block"><div class="brief-label">What the system is saying</div><div class="brief-value">${escapeHtml(b.one_line_explanation || "")}</div></div>` +
      `<div class="brief-block"><div class="brief-label">Evidence state</div><div class="brief-value">${escapeHtml(b.evidence_state_plain || "—")}</div></div>` +
      `<div class="action-line">What to do now: ${escapeHtml(b.action_framing || "")}</div>` +
      rhBlock;
  }

  function escapeHtml(s) {
    if (!s) return "";
    const d = document.createElement("div");
    d.textContent = s;
    return d.innerHTML;
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
    if (j.reopen_note) parts.push(`<div class='brief-block'><div class='brief-label'>Reopen</div><div class='brief-value'>${escapeHtml(j.reopen_note)}</div></div>`);
    if (j.closeout_plain) parts.push(`<div class='brief-block'><div class='brief-label'>Closeout</div><div class='brief-value'>${escapeHtml(j.closeout_plain)}</div></div>`);
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

  async function refreshBriefFromOverview() {
    const { json } = await api("/api/overview");
    if (!json.ok && json.error) {
      $("brief-body").textContent = JSON.stringify(json, null, 2);
      return;
    }
    renderBrief(json.user_first, json.runtime_health);
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
        });
        li.appendChild(btn);
      });
      ul.appendChild(li);
    });
  }

  async function loadDecisions() {
    const { json } = await api("/api/decisions");
    const rows = json.decisions || [];
    $("decisions-empty").style.display = rows.length ? "none" : "block";
    $("dec-list").textContent = rows.length ? JSON.stringify(rows, null, 2) : "";
  }

  function buildAskShortcuts() {
    const shortcuts = [
      { label: "Explain this briefly", text: "decision summary" },
      { label: "Show key evidence", text: "information layer" },
      { label: "Why is this closed?", text: "why is this closed" },
      { label: "What changed?", text: "what changed" },
      { label: "What remains unproven?", text: "what remains unproven" },
      { label: "Show research layer", text: "research layer" },
      { label: "Show provenance", text: "show provenance" },
    ];
    const host = $("ask-shortcuts");
    host.innerHTML = "";
    shortcuts.forEach((s) => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "btn";
      b.textContent = s.label;
      b.addEventListener("click", () => {
        $("conv-in").value = s.text;
        submitConv();
      });
      host.appendChild(b);
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
    loadDecisions();
  });

  $("btn-conv").addEventListener("click", submitConv);

  $("btn-reload").addEventListener("click", async () => {
    await api("/api/reload", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
    await refreshMeta();
    await refreshBriefFromOverview();
    if ($("panel-replay").classList.contains("visible")) await loadReplay();
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
  refreshBriefFromOverview();
  loadAlerts();
  loadDecisions();
  pollNotif();
  setInterval(pollNotif, 8000);
})();
