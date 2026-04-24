// Patch 12 — Product Shell auth bootstrap + telemetry helper.
//
// Responsibilities:
//   1. Before the Product Shell renders, check for a Supabase session.
//      If the deployment has Auth configured and there's no session,
//      redirect to /login.html. (If auth isn't configured the server
//      downgrades gracefully and this module no-ops.)
//   2. Rewrite window.fetch so every `/api/*` call gets an
//      `Authorization: Bearer <jwt>` header when a session exists.
//   3. Expose `window.metisEmitEvent(name, meta)` — the Product Shell
//      calls this at a small set of anchor points to accumulate
//      per-account usage telemetry.

(function () {
  "use strict";

  const SESSION_KEY   = "metis_session_id";
  const ALIAS_KEY     = "metis_user_alias";
  const LANG_KEY      = "metis_user_lang";
  const DISABLED_FLAG = "metis_auth_disabled";

  const state = {
    supabase: null,
    token: null,
    authRequired: false,
    ready: false,
    sessionId: safeGet(SESSION_KEY) || "",
    userAlias: safeGet(ALIAS_KEY)   || "",
    userLang:  safeGet(LANG_KEY)    || (navigator.language || "").toLowerCase().startsWith("ko") ? "ko" : "en",
    eventsEnabled: true,
  };

  window.metisAuthState = state;

  function safeGet(k) { try { return sessionStorage.getItem(k) || ""; } catch (_e) { return ""; } }
  function safeSet(k, v) { try { sessionStorage.setItem(k, v); } catch (_e) { /* storage blocked */ } }

  function uuidv4() {
    if (window.crypto && window.crypto.randomUUID) {
      try { return window.crypto.randomUUID(); } catch (_e) { /* fallthrough */ }
    }
    const rnd = (n) => Math.floor(Math.random() * n);
    const hex = (n) => rnd(n).toString(16);
    const seg = (len) => Array.from({ length: len }, () => hex(16)).join("");
    return `${seg(8)}-${seg(4)}-4${seg(3)}-${(8 + rnd(4)).toString(16)}${seg(3)}-${seg(12)}`;
  }

  function ensureSessionId() {
    if (!state.sessionId) {
      state.sessionId = uuidv4();
      safeSet(SESSION_KEY, state.sessionId);
    }
    return state.sessionId;
  }

  const originalFetch = window.fetch.bind(window);
  window.fetch = function (input, init) {
    try {
      const url = typeof input === "string" ? input : (input && input.url) || "";
      if (state.token && url.indexOf("/api/") >= 0) {
        init = init || {};
        const headers = new Headers(init.headers || (typeof input !== "string" ? input.headers : null) || {});
        if (!headers.has("Authorization")) {
          headers.set("Authorization", `Bearer ${state.token}`);
        }
        init.headers = headers;
      }
    } catch (_e) { /* fall through to original */ }
    return originalFetch(input, init);
  };

  async function fetchAuthConfig() {
    try {
      const resp = await originalFetch("/api/runtime/auth-config", { cache: "no-store" });
      return await resp.json();
    } catch (_e) { return { ok: false, configured: false }; }
  }

  async function loadSupabaseSdk() {
    try {
      const mod = await import("https://esm.sh/@supabase/supabase-js@2.45.0");
      return mod.createClient;
    } catch (_e) { return null; }
  }

  async function ensureSession(cfg) {
    const createClient = await loadSupabaseSdk();
    if (!createClient) return null;
    state.supabase = createClient(cfg.supabase_url, cfg.anon_key, {
      auth: {
        persistSession: true,
        detectSessionInUrl: true,
        autoRefreshToken: true,
      },
    });
    const sess = await state.supabase.auth.getSession();
    const data = sess && sess.data && sess.data.session;
    if (!data) return null;
    state.token = data.access_token || null;
    return data;
  }

  async function probeMe() {
    if (!state.token) return null;
    try {
      const resp = await originalFetch("/api/auth/me", {
        cache: "no-store",
        headers: { "Authorization": `Bearer ${state.token}` },
      });
      if (!resp.ok) return null;
      const body = await resp.json();
      if (body && body.ok && body.user) {
        state.userAlias = body.user.user_id_alias || state.userAlias;
        state.userLang  = body.user.preferred_lang || state.userLang;
        safeSet(ALIAS_KEY, state.userAlias);
        safeSet(LANG_KEY,  state.userLang);
      }
      return body;
    } catch (_e) { return null; }
  }

  async function bootstrap() {
    const cfg = await fetchAuthConfig();
    if (!cfg || !cfg.ok || !cfg.configured) {
      // Graceful downgrade — server runs without auth.
      window[DISABLED_FLAG] = true;
      state.authRequired = false;
      state.ready = true;
      ensureSessionId();
      return { authed: false, authRequired: false };
    }
    state.authRequired = true;
    const sess = await ensureSession(cfg);
    if (!sess) {
      window.location.replace("/login.html");
      return { authed: false, authRequired: true };
    }
    const me = await probeMe();
    if (!me || !me.ok) {
      window.location.replace("/login.html");
      return { authed: false, authRequired: true };
    }
    ensureSessionId();
    state.ready = true;
    return { authed: true, authRequired: true, me };
  }

  window.metisAuthBootstrap = bootstrap;

  window.metisEmitEvent = async function emitEvent(eventName, meta) {
    if (!state.eventsEnabled) return;
    try {
      const body = {
        event_name: String(eventName || "").trim(),
        session_id: ensureSessionId(),
        surface:    (meta && meta.surface)    || "system",
        route:      (meta && meta.route)      || (typeof location !== "undefined" ? location.pathname : ""),
        asset_id:   (meta && meta.asset_id)   || null,
        horizon_key:(meta && meta.horizon_key)|| null,
        result_state:(meta && meta.result_state) || null,
        lang:       (meta && meta.lang)       || state.userLang || "ko",
        metadata:   (meta && meta.metadata)   || {},
      };
      if (!body.event_name) return;
      await window.fetch("/api/events", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        keepalive: true,
      });
    } catch (_e) { /* telemetry is best-effort */ }
  };
})();
