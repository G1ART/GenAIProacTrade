// Patch 12 — login.html controller (supabase-js ESM via CDN).
//
// Flow:
//   1. fetch /api/runtime/auth-config to learn SUPABASE_URL + anon key.
//   2. boot supabase-js and call signInWithOtp({ email }) to start magic link.
//   3. when the user returns via redirect (#access_token=... hash),
//      hand the token to /api/auth/session so the server can verify HS256
//      and upsert the profile, then redirect to / (Product Shell).
//
// The page never writes the access_token anywhere user-visible; the
// token lives in supabase.auth.getSession() (which supabase-js stores in
// localStorage under the sb-*-auth-token key by default).

import { createClient } from "https://esm.sh/@supabase/supabase-js@2.45.0";

const $ = (id) => document.getElementById(id);
const STATUS = $("lg-status");
const FORM = $("lg-form");
const EMAIL = $("lg-email");
const SUBMIT = $("lg-submit");

function detectInitialLang() {
  const nav = (navigator.language || "ko").toLowerCase();
  return nav.startsWith("ko") ? "ko" : "en";
}
function applyLang(lang) {
  document.body.dataset.lgLang = lang === "ko" ? "ko" : "en";
  window.__lg_lang = lang;
}
applyLang(detectInitialLang());
$("lg-lang-toggle").addEventListener("click", (ev) => {
  ev.preventDefault();
  applyLang(window.__lg_lang === "ko" ? "en" : "ko");
});

function say(kind, msg) {
  STATUS.classList.remove("is-error", "is-success");
  if (kind === "error")   STATUS.classList.add("is-error");
  if (kind === "success") STATUS.classList.add("is-success");
  STATUS.textContent = msg || "";
}

const T = {
  configuring:  { ko: "초기화 중…", en: "Initializing…" },
  not_configured: {
    ko: "아직 이 환경에 Supabase Auth 가 설정되지 않았어요. 운영 팀에 문의해 주세요.",
    en: "Supabase Auth is not configured on this deployment yet. Ping the operator.",
  },
  ready_ko:     { ko: "초대된 이메일을 입력하세요.", en: "Enter your invited email." },
  sending:      { ko: "로그인 링크 보내는 중…", en: "Sending sign-in link…" },
  sent:         {
    ko: "링크를 보냈어요. 이메일을 확인하고 이 탭으로 돌아와 주세요.",
    en: "Link sent. Check your inbox and come back to this tab.",
  },
  link_invalid: {
    ko: "로그인 링크가 올바르지 않거나 만료되었습니다. 다시 요청해 주세요.",
    en: "The sign-in link was invalid or expired. Please request a new one.",
  },
  activating:   { ko: "세션을 활성화하고 있어요…", en: "Activating your session…" },
  not_on_allowlist: {
    ko: "아직 초대 목록에 포함되어 있지 않아요. 초대해 준 담당자에게 문의해 주세요.",
    en: "You are not on the beta allowlist yet. Please reach the teammate who invited you.",
  },
  rejected_generic: {
    ko: "로그인 요청이 거부되었습니다. 다시 시도하거나 담당자에게 문의해 주세요.",
    en: "Sign-in was rejected. Try again or contact the operator.",
  },
  network_error: {
    ko: "네트워크 오류가 발생했어요. 잠시 후 다시 시도해 주세요.",
    en: "Network error. Please try again shortly.",
  },
};
function tr(key) { return T[key][window.__lg_lang] || T[key].en; }

let supabase = null;

async function boot() {
  say("info", tr("configuring"));
  let cfg;
  try {
    const resp = await fetch("/api/runtime/auth-config", { cache: "no-store" });
    cfg = await resp.json();
  } catch (_err) {
    say("error", tr("network_error"));
    return;
  }
  if (!cfg || !cfg.ok || !cfg.configured) {
    say("error", tr("not_configured"));
    return;
  }
  supabase = createClient(cfg.supabase_url, cfg.anon_key, {
    auth: {
      persistSession: true,
      detectSessionInUrl: true,
      autoRefreshToken: true,
    },
  });
  const maybeSession = await supabase.auth.getSession();
  if (maybeSession && maybeSession.data && maybeSession.data.session) {
    await completeSignIn(maybeSession.data.session, cfg);
    return;
  }
  say("info", tr("ready_ko"));
  SUBMIT.disabled = false;
}

async function completeSignIn(session, cfg) {
  say("info", tr("activating"));
  SUBMIT.disabled = true;
  const token = session && session.access_token;
  if (!token) {
    say("error", tr("link_invalid"));
    SUBMIT.disabled = false;
    return;
  }
  let resp, body;
  try {
    resp = await fetch("/api/auth/session", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        access_token: token,
        preferred_lang: window.__lg_lang || "ko",
      }),
    });
    body = await resp.json();
  } catch (_err) {
    say("error", tr("network_error"));
    SUBMIT.disabled = false;
    return;
  }
  if (!resp.ok || !body || !body.ok) {
    const reason = (body && body.reason) || "";
    if (reason === "not_on_allowlist" || reason === "allowlist_revoked" || reason === "allowlist_paused") {
      say("error", tr("not_on_allowlist"));
    } else {
      say("error", tr("rejected_generic"));
    }
    SUBMIT.disabled = false;
    return;
  }
  try {
    sessionStorage.setItem("metis_user_alias", body.user.user_id_alias || "");
    sessionStorage.setItem("metis_user_lang",  body.user.preferred_lang || "ko");
    sessionStorage.setItem("metis_session_id", body.session_id || "");
  } catch (_err) { /* storage blocked — safe to continue */ }
  say("success", tr("activating"));
  window.location.replace("/");
}

EMAIL.addEventListener("input", () => {
  const ok = /[^\s@]+@[^\s@]+\.[^\s@]+/.test(EMAIL.value.trim());
  SUBMIT.disabled = !ok || !supabase;
});

FORM.addEventListener("submit", async (ev) => {
  ev.preventDefault();
  if (!supabase) return;
  const email = EMAIL.value.trim();
  if (!email) return;
  SUBMIT.disabled = true;
  say("info", tr("sending"));
  try {
    const redirect = window.location.origin + "/login.html#callback";
    const { error } = await supabase.auth.signInWithOtp({
      email,
      options: { emailRedirectTo: redirect },
    });
    if (error) {
      say("error", tr("rejected_generic"));
      SUBMIT.disabled = false;
      return;
    }
    say("success", tr("sent"));
  } catch (_err) {
    say("error", tr("network_error"));
    SUBMIT.disabled = false;
  }
});

boot();
