// Patch 12 — /ops Beta Admin tab renderer.
//
// Pulls from /api/admin/beta/{users,sessions,events,trust}. The endpoints
// require admin/internal role on beta_users_v1 — a beta_user session hits
// 403 and sees the raw status block, which is fine for the ops surface.
//
// We deliberately render with plain DOM + a tiny SVG bar chart so there's
// no external dependency. Matches the ops.js vanilla pattern.

(function () {
  "use strict";

  function $(id) { return document.getElementById(id); }
  function el(tag, attrs, children) {
    var n = document.createElement(tag);
    if (attrs) Object.keys(attrs).forEach(function (k) {
      if (k === "className") n.className = attrs[k];
      else if (k === "style")   Object.assign(n.style, attrs[k] || {});
      else if (k === "text")    n.textContent = attrs[k];
      else                      n.setAttribute(k, String(attrs[k]));
    });
    (children || []).forEach(function (c) { if (c) n.appendChild(c); });
    return n;
  }

  function formatUtc(v) {
    if (!v) return "—";
    try { return String(v).replace("T", " ").replace(/\..*$/, "Z"); }
    catch (_e) { return String(v); }
  }

  async function getJson(url) {
    var resp = await fetch(url, { cache: "no-store", headers: { "Accept": "application/json" } });
    var body = null;
    try { body = await resp.json(); } catch (_e) { /* ignore */ }
    return { ok: resp.ok, status: resp.status, body: body };
  }

  function renderUsers(container, payload) {
    var items = (payload && payload.items) || [];
    var card = el("div", { className: "sandbox-card" });
    card.appendChild(el("h3", { text: "Invited users (" + items.length + ")" }));
    if (!items.length) {
      card.appendChild(el("p", { className: "empty", text: "No beta_users_v1 rows." }));
      container.appendChild(card);
      return;
    }
    var tbl = el("table", { className: "feed-list", style: { width: "100%", fontSize: "0.86rem" } });
    var thead = el("tr", null, [
      el("th", { text: "alias" }), el("th", { text: "email" }), el("th", { text: "status" }),
      el("th", { text: "role" }), el("th", { text: "invited_at" }), el("th", { text: "activated_at" }),
    ]);
    tbl.appendChild(thead);
    items.forEach(function (u) {
      tbl.appendChild(el("tr", null, [
        el("td", { className: "mono", text: u.user_id_alias || "" }),
        el("td", { text: u.email_masked || "" }),
        el("td", { text: u.status || "" }),
        el("td", { text: u.role || "" }),
        el("td", { text: formatUtc(u.invited_at) }),
        el("td", { text: formatUtc(u.activated_at) }),
      ]));
    });
    card.appendChild(tbl);
    container.appendChild(card);
  }

  function renderSessions(container, payload) {
    var items = (payload && payload.items) || [];
    var card = el("div", { className: "sandbox-card", style: { marginTop: "0.75rem" } });
    card.appendChild(el("h3", { text: "Recent sessions (last 24h) — " + items.length }));
    if (!items.length) {
      card.appendChild(el("p", { className: "empty", text: "No sessions in the last 24h." }));
      container.appendChild(card);
      return;
    }
    var tbl = el("table", { className: "feed-list", style: { width: "100%", fontSize: "0.84rem" } });
    tbl.appendChild(el("tr", null, [
      el("th", { text: "alias" }), el("th", { text: "session" }), el("th", { text: "events" }),
      el("th", { text: "started" }), el("th", { text: "last_event" }), el("th", { text: "surfaces" }),
    ]));
    items.forEach(function (s) {
      tbl.appendChild(el("tr", null, [
        el("td", { className: "mono", text: s.user_id_alias || "" }),
        el("td", { className: "mono", text: (s.session_id || "").slice(0, 8) + "…" }),
        el("td", { text: String(s.event_count || 0) }),
        el("td", { text: formatUtc(s.session_started_at) }),
        el("td", { text: formatUtc(s.session_last_event_at) }),
        el("td", { text: (s.surfaces_touched || []).join(", ") }),
      ]));
    });
    card.appendChild(tbl);
    container.appendChild(card);
  }

  function renderEvents(container, payload) {
    var items = (payload && payload.items) || [];
    var card = el("div", { className: "sandbox-card", style: { marginTop: "0.75rem" } });
    card.appendChild(el("h3", { text: "Top events (last 7 days)" }));
    if (!items.length) {
      card.appendChild(el("p", { className: "empty", text: "No events yet." }));
      container.appendChild(card);
      return;
    }
    var max = 1;
    items.forEach(function (e) { if ((e.event_count || 0) > max) max = e.event_count; });
    var svgNS = "http://www.w3.org/2000/svg";
    var svg = document.createElementNS(svgNS, "svg");
    var rowH = 20;
    var w = 520, h = items.length * rowH + 12;
    svg.setAttribute("viewBox", "0 0 " + w + " " + h);
    svg.setAttribute("width", "100%");
    svg.setAttribute("height", String(h));
    items.forEach(function (e, i) {
      var y = i * rowH + 4;
      var label = document.createElementNS(svgNS, "text");
      label.setAttribute("x", "4"); label.setAttribute("y", String(y + 13));
      label.setAttribute("fill", "#cfd4dd"); label.setAttribute("font-size", "11");
      label.textContent = e.event_name;
      svg.appendChild(label);
      var barW = Math.max(1, Math.round((e.event_count / max) * (w - 220)));
      var bar = document.createElementNS(svgNS, "rect");
      bar.setAttribute("x", "210"); bar.setAttribute("y", String(y));
      bar.setAttribute("width", String(barW)); bar.setAttribute("height", String(rowH - 6));
      bar.setAttribute("rx", "2"); bar.setAttribute("fill", "#4cc38a");
      svg.appendChild(bar);
      var countT = document.createElementNS(svgNS, "text");
      countT.setAttribute("x", String(210 + barW + 6)); countT.setAttribute("y", String(y + 13));
      countT.setAttribute("fill", "#cfd4dd"); countT.setAttribute("font-size", "11");
      countT.textContent = e.event_count + " · users=" + (e.unique_users || 0) + " · sess=" + (e.unique_sessions || 0);
      svg.appendChild(countT);
    });
    card.appendChild(svg);
    container.appendChild(card);
  }

  function renderTrust(container, payload) {
    var t = (payload && payload.trust) || {};
    var card = el("div", { className: "sandbox-card", style: { marginTop: "0.75rem" } });
    card.appendChild(el("h3", { text: "Trust signals (last 7 days)" }));
    var dl = el("dl", { style: { display: "grid", gridTemplateColumns: "auto 1fr", gap: "0.25rem 0.75rem", fontSize: "0.88rem" } });
    function row(k, v) {
      dl.appendChild(el("dt", { style: { color: "#9aa3b2" }, text: k }));
      dl.appendChild(el("dd", { className: "mono", style: { margin: 0 }, text: (v == null ? "—" : String(v)) }));
    }
    row("total_ask_events",     t.total_ask_events);
    row("ask_degraded_count",   t.degraded_count);
    row("ask_degraded_rate",    t.ask_degraded_rate);
    row("sandbox_blocked_count",t.blocked_count);
    row("out_of_scope_count",   t.out_of_scope_count);
    row("out_of_scope_rate",    t.out_of_scope_rate);
    card.appendChild(dl);
    container.appendChild(card);
  }

  async function refresh() {
    var root = $("beta-admin-root");
    var status = $("beta-admin-status");
    if (!root) return;
    root.innerHTML = "";
    status.textContent = "Loading…";

    var users = await getJson("/api/admin/beta/users");
    if (!users.ok) {
      status.textContent = users.status === 403 ? "admin role required" : ("error: " + (users.body && users.body.error) || users.status);
      return;
    }
    var sessions = await getJson("/api/admin/beta/sessions");
    var events   = await getJson("/api/admin/beta/events");
    var trust    = await getJson("/api/admin/beta/trust");

    renderUsers(root,    users.body    || {});
    renderSessions(root, sessions.body || {});
    renderEvents(root,   events.body   || {});
    renderTrust(root,    trust.body    || {});
    status.textContent = "OK · " + new Date().toISOString();
  }

  document.addEventListener("DOMContentLoaded", function () {
    var btn = $("btn-beta-admin-refresh");
    if (btn) btn.addEventListener("click", refresh);
  });

  window.__METIS_BETA_ADMIN = { refresh: refresh };
})();
