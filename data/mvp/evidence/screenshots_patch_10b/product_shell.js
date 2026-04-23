/*
 * METIS Product Shell — customer-facing client
 * Patch 10A (2026-04-23)
 *
 * This file is served to anonymous / customer visitors at `/`.
 *
 * Invariants enforced here:
 * - Never show engineering IDs (``art_*`` / ``reg_*`` / ``factor_*`` /
 *   raw provenance enums). The only data source is ``/api/product/today``
 *   which is produced by the view_models mapper that already strips
 *   those tokens; this file never falls back to raw ``/api/*`` endpoints.
 * - Never say "buy" / "sell". Only stance direction phrasing.
 * - Honest degraded language: when ``confidence.source_key`` is
 *   ``sample`` or ``preparing``, the UI matches that tone rather than
 *   rendering as if the reading were live.
 * - Research / Replay / Ask AI are rendered as stub cards — they will
 *   be formally redesigned in Patch 10B.
 *
 * Implementation style: hand-rolled Vanilla JS IIFE, zero build, zero
 * dependencies. SVG sparklines are rendered by string concatenation.
 */
(function () {
  "use strict";

  // -------------------------------------------------------------------
  // State
  // -------------------------------------------------------------------

  var STATE = {
    lang: (function () {
      try {
        var saved = window.localStorage.getItem("ps.lang");
        if (saved === "ko" || saved === "en") return saved;
      } catch (e) { /* ignore */ }
      var nav = (navigator.language || "ko").toLowerCase();
      return nav.indexOf("ko") === 0 ? "ko" : "en";
    })(),
    activePanel: "today",
    today: null,       // last PRODUCT_TODAY_V1 payload
    loading: false,
    error: null,
    // Patch 10B: focus carried across Research/Replay/Ask AI panels
    focus: { asset_id: null, horizon_key: null },
    research:  { loading: false, error: null, presentation: "landing", dto: null },
    replay:    { loading: false, error: null, dto: null },
    ask:       { loading: false, error: null, dto: null, selected_intent: null, free_text: "", answer: null, submitting: false },
    requests:  { loading: false, error: null, dto: null },
  };

  var COPY = {
    ko: {
      nav: {
        today:    "오늘",
        research: "리서치",
        replay:   "리플레이",
        ask_ai:   "Ask AI",
      },
      loading:           "불러오는 중…",
      error_headline:    "지금 결과를 불러올 수 없습니다",
      error_body:        "잠시 후 다시 시도해 주세요. 이 메시지가 계속되면 운영자에게 문의하세요.",
      retry:             "다시 시도",
      movers_title:      "오늘의 선정된 변동",
      footer:            "METIS — 과장된 확신이 아니라, 정직한 근거를 드리는 것이 원칙입니다.",
      advanced_open:     "고급 세부 보기 (접힘)",
      evidence_title:    "근거 살펴보기",
      evidence_what:     "무엇이 바뀌었나",
      evidence_support:  "가장 강한 지지 근거",
      evidence_why:      "이 확신의 근거",
      close:             "닫기",
      no_movers:         "오늘은 의미 있는 변동이 없습니다.",
      no_watchlist:      "관심종목을 추가하면 여기에 표시됩니다.",
      horizon_mini_title:"구간",
      as_of_prefix:      "데이터 기준: ",
      research: {
        breadcrumbs_home: "리서치",
        landing_title:    "오늘의 리서치 관점",
        deep_dive_title:  "이 종목의 근거를 자세히",
        column_top_claims:"이 구간의 대표 관점",
        tile_deeplink:    "자세히 보기 →",
        back_to_landing:  "← 리서치로 돌아가기",
        claim_title:      "이번 관점",
        evidence_title:   "근거 5가지",
        action_title:     "다음 행동",
        evidence_what:    "무엇이 바뀌었나",
        evidence_support: "가장 강한 지지",
        evidence_counter: "반대·보완 시각",
        evidence_missing: "빠졌거나 준비중인 근거",
        evidence_peer:    "같은 범주의 다른 사례",
        action_open_replay: "리플레이로 보기",
        action_ask_ai:      "Ask AI 에게 더 묻기",
        action_back_today:  "오늘 화면으로 돌아가기",
        empty_tiles:        "이 구간에 드릴 만한 관점이 아직 없습니다.",
      },
      replay: {
        title:           "어떻게 여기까지 왔는지",
        summary_events:  "이벤트",
        summary_span:    "기간",
        timeline_title:  "변화의 타임라인",
        scenarios_title: "시나리오 보기",
        scenario_baseline:"현재 근거",
        scenario_weakened:"근거가 약해지면",
        scenario_stressed:"시장이 흔들리면",
        gap_days:        "일 공백",
        checkpoint_decision: "결정 지점",
        advanced_label:  "원문 페이로드 (민감정보 마스킹됨)",
        back_to_today:   "오늘 화면으로 돌아가기",
        empty_timeline:  "이 종목에 대해 아직 보여드릴 변화 이력이 없습니다.",
      },
      ask_ai: {
        context_prefix:    "지금 보고 계신 것",
        quick_title:       "자주 묻는 질문",
        freetext_title:    "직접 물어보기",
        freetext_placeholder:"예: 이 신호가 왜 이전보다 강해졌나요?",
        submit:            "물어보기",
        answer_claim:      "요약 답변",
        answer_evidence:   "근거",
        answer_missing:    "부족한 부분",
        degraded_banner:   "지금은 자동 답변 모듈이 준비중입니다. 아래 근거 자료로 안내드립니다.",
        requests_title:    "내 요청 현황",
        requests_empty:    "아직 보낸 요청이 없습니다.",
        back_to_today:     "오늘 화면으로 돌아가기",
        quick_intents: {
          why_grade_up:     "왜 등급이 올랐나요?",
          why_grade_down:   "왜 등급이 내려갔나요?",
          compare_horizon:  "다른 구간과 어떻게 다른가요?",
          request_replay:   "리플레이 한 번 더 보기",
          compare_peer:     "같은 범주의 다른 종목과 비교",
          what_would_flip:  "무엇이 바뀌면 판단이 뒤집히나요?",
        },
      },
    },
    en: {
      nav: {
        today:    "Today",
        research: "Research",
        replay:   "Replay",
        ask_ai:   "Ask AI",
      },
      loading:           "Loading…",
      error_headline:    "We couldn't load results right now",
      error_body:        "Please try again in a moment. If this persists, contact an operator.",
      retry:             "Retry",
      movers_title:      "Selected movers today",
      footer:            "METIS — honest evidence, not overconfident claims.",
      advanced_open:     "Advanced details (collapsed)",
      evidence_title:    "Look inside the evidence",
      evidence_what:     "What changed",
      evidence_support:  "Strongest supporting reason",
      evidence_why:      "Why this confidence",
      close:             "Close",
      no_movers:         "No material movers today.",
      no_watchlist:      "Add tickers to your watchlist to see them here.",
      horizon_mini_title:"Horizon",
      as_of_prefix:      "Data as of: ",
      research: {
        breadcrumbs_home: "Research",
        landing_title:    "Today's research perspectives",
        deep_dive_title:  "A closer look at this thesis",
        column_top_claims:"Top claims in this horizon",
        tile_deeplink:    "See detail →",
        back_to_landing:  "← Back to research",
        claim_title:      "This perspective",
        evidence_title:   "Five pieces of evidence",
        action_title:     "Next step",
        evidence_what:    "What changed",
        evidence_support: "Strongest support",
        evidence_counter: "Counter / companion view",
        evidence_missing: "Missing or preparing evidence",
        evidence_peer:    "Peer cases in the same family",
        action_open_replay: "See it in Replay",
        action_ask_ai:      "Ask AI about this",
        action_back_today:  "Back to Today",
        empty_tiles:        "No grounded perspectives to show for this horizon yet.",
      },
      replay: {
        title:           "How we got here",
        summary_events:  "events",
        summary_span:    "span",
        timeline_title:  "Timeline of changes",
        scenarios_title: "Scenarios",
        scenario_baseline:"Today's reading",
        scenario_weakened:"If the evidence weakens",
        scenario_stressed:"If the market turns",
        gap_days:        "day gap",
        checkpoint_decision: "Decision point",
        advanced_label:  "Raw payload (redacted)",
        back_to_today:   "Back to Today",
        empty_timeline:  "No governance history to show for this asset yet.",
      },
      ask_ai: {
        context_prefix:    "What you're looking at",
        quick_title:       "Common questions",
        freetext_title:    "Ask in your own words",
        freetext_placeholder:"e.g., Why is this signal stronger than before?",
        submit:            "Ask",
        answer_claim:      "Summary answer",
        answer_evidence:   "Evidence",
        answer_missing:    "What's missing",
        degraded_banner:   "The automated answerer is preparing right now. Here is the evidence we can cite.",
        requests_title:    "Your requests",
        requests_empty:    "You haven't sent any requests yet.",
        back_to_today:     "Back to Today",
        quick_intents: {
          why_grade_up:     "Why did the grade go up?",
          why_grade_down:   "Why did the grade go down?",
          compare_horizon:  "How is it different from other horizons?",
          request_replay:   "Show me one more replay",
          compare_peer:     "Compare to peers in the same family",
          what_would_flip:  "What would flip this verdict?",
        },
      },
    },
  };

  function T(key) {
    // dotted path lookup in COPY[lang]
    var parts = key.split(".");
    var node = COPY[STATE.lang];
    for (var i = 0; i < parts.length; i++) {
      if (node && typeof node === "object" && parts[i] in node) {
        node = node[parts[i]];
      } else {
        return "";
      }
    }
    return typeof node === "string" ? node : "";
  }

  // -------------------------------------------------------------------
  // DOM helpers (tiny, dependency-free)
  // -------------------------------------------------------------------

  function el(tag, attrs, children) {
    var n = document.createElement(tag);
    if (attrs) {
      Object.keys(attrs).forEach(function (k) {
        var v = attrs[k];
        if (v === null || v === undefined || v === false) return;
        if (k === "className") {
          n.className = v;
        } else if (k === "dataset") {
          Object.keys(v).forEach(function (dk) { n.dataset[dk] = v[dk]; });
        } else if (k === "onClick") {
          n.addEventListener("click", v);
        } else if (k === "style") {
          Object.keys(v).forEach(function (sk) { n.style[sk] = v[sk]; });
        } else if (k === "text") {
          n.textContent = v;
        } else if (k === "html") {
          n.innerHTML = v;
        } else if (k.indexOf("aria") === 0 || k === "role" || k === "href" || k === "title" || k === "tabindex" || k === "type") {
          n.setAttribute(k, v);
        } else {
          n.setAttribute(k, v);
        }
      });
    }
    if (children) {
      if (!Array.isArray(children)) children = [children];
      children.forEach(function (c) {
        if (c === null || c === undefined) return;
        if (typeof c === "string" || typeof c === "number") {
          n.appendChild(document.createTextNode(String(c)));
        } else {
          n.appendChild(c);
        }
      });
    }
    return n;
  }

  function clear(node) { while (node && node.firstChild) node.removeChild(node.firstChild); }

  function qs(id) { return document.getElementById(id); }

  // -------------------------------------------------------------------
  // Data fetch
  // -------------------------------------------------------------------

  function fetchTodayDto() {
    STATE.loading = true;
    STATE.error = null;
    renderAll();
    var url = "/api/product/today?lang=" + encodeURIComponent(STATE.lang);
    return fetch(url, {
      headers: { "Accept": "application/json", "X-User-Language": STATE.lang },
    })
      .then(function (r) {
        if (!r.ok) throw new Error("http_" + r.status);
        return r.json();
      })
      .then(function (dto) {
        STATE.today = dto;
        STATE.loading = false;
        renderAll();
      })
      .catch(function (e) {
        STATE.error = String(e && e.message || e);
        STATE.loading = false;
        renderAll();
      });
  }

  function _qsParams() {
    var params = ["lang=" + encodeURIComponent(STATE.lang)];
    if (STATE.focus.asset_id) params.push("asset_id=" + encodeURIComponent(STATE.focus.asset_id));
    if (STATE.focus.horizon_key) params.push("horizon_key=" + encodeURIComponent(STATE.focus.horizon_key));
    return "?" + params.join("&");
  }

  function fetchResearchDto() {
    STATE.research.loading = true;
    STATE.research.error = null;
    var presentation = STATE.focus.asset_id ? "deepdive" : "landing";
    STATE.research.presentation = presentation;
    renderResearchPanel();
    var url = "/api/product/research" + _qsParams() + "&presentation=" + encodeURIComponent(presentation);
    return fetch(url, { headers: { "Accept": "application/json", "X-User-Language": STATE.lang } })
      .then(function (r) { if (!r.ok) throw new Error("http_" + r.status); return r.json(); })
      .then(function (dto) {
        STATE.research.dto = dto;
        STATE.research.loading = false;
        renderResearchPanel();
      })
      .catch(function (e) {
        STATE.research.error = String(e && e.message || e);
        STATE.research.loading = false;
        renderResearchPanel();
      });
  }

  function fetchReplayDto() {
    STATE.replay.loading = true;
    STATE.replay.error = null;
    renderReplayPanel();
    var url = "/api/product/replay" + _qsParams();
    return fetch(url, { headers: { "Accept": "application/json", "X-User-Language": STATE.lang } })
      .then(function (r) { if (!r.ok) throw new Error("http_" + r.status); return r.json(); })
      .then(function (dto) {
        STATE.replay.dto = dto;
        STATE.replay.loading = false;
        renderReplayPanel();
      })
      .catch(function (e) {
        STATE.replay.error = String(e && e.message || e);
        STATE.replay.loading = false;
        renderReplayPanel();
      });
  }

  function fetchAskDto() {
    STATE.ask.loading = true;
    STATE.ask.error = null;
    renderAskPanel();
    var url = "/api/product/ask" + _qsParams();
    return fetch(url, { headers: { "Accept": "application/json", "X-User-Language": STATE.lang } })
      .then(function (r) { if (!r.ok) throw new Error("http_" + r.status); return r.json(); })
      .then(function (dto) {
        STATE.ask.dto = dto;
        STATE.ask.loading = false;
        renderAskPanel();
      })
      .catch(function (e) {
        STATE.ask.error = String(e && e.message || e);
        STATE.ask.loading = false;
        renderAskPanel();
      })
      .then(fetchRequestsDto);
  }

  function fetchRequestsDto() {
    STATE.requests.loading = true;
    STATE.requests.error = null;
    var url = "/api/product/requests?lang=" + encodeURIComponent(STATE.lang);
    return fetch(url, { headers: { "Accept": "application/json", "X-User-Language": STATE.lang } })
      .then(function (r) { if (!r.ok) throw new Error("http_" + r.status); return r.json(); })
      .then(function (dto) {
        STATE.requests.dto = dto;
        STATE.requests.loading = false;
        renderAskPanel();
      })
      .catch(function (e) {
        STATE.requests.error = String(e && e.message || e);
        STATE.requests.loading = false;
        renderAskPanel();
      });
  }

  function fetchQuickAnswer(intent) {
    var url = "/api/product/ask/quick" + _qsParams() + "&intent=" + encodeURIComponent(intent);
    STATE.ask.selected_intent = intent;
    STATE.ask.answer = { status: "loading" };
    renderAskPanel();
    return fetch(url, { headers: { "Accept": "application/json", "X-User-Language": STATE.lang } })
      .then(function (r) { if (!r.ok) throw new Error("http_" + r.status); return r.json(); })
      .then(function (dto) {
        var list = (dto && dto.answers) || [];
        var found = null;
        for (var i = 0; i < list.length; i++) {
          if (list[i].intent === intent) { found = list[i]; break; }
        }
        STATE.ask.answer = found || { status: "degraded", claim: "", evidence: [], missing: [] };
        renderAskPanel();
      })
      .catch(function () {
        STATE.ask.answer = { status: "degraded", claim: T("ask_ai.degraded_banner"), evidence: [], missing: [] };
        renderAskPanel();
      });
  }

  function postFreeText() {
    var text = (STATE.ask.free_text || "").trim();
    if (!text) return;
    STATE.ask.submitting = true;
    STATE.ask.answer = { status: "loading" };
    renderAskPanel();
    var body = JSON.stringify({
      message: text,
      asset_id: STATE.focus.asset_id || null,
      horizon_key: STATE.focus.horizon_key || null,
      lang: STATE.lang,
    });
    return fetch("/api/product/ask", {
      method: "POST",
      headers: {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-User-Language": STATE.lang,
      },
      body: body,
    })
      .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, body: j }; }); })
      .then(function (res) {
        STATE.ask.answer = res.body || { status: "degraded", claim: "", evidence: [], missing: [] };
        STATE.ask.submitting = false;
        renderAskPanel();
      })
      .catch(function () {
        STATE.ask.answer = { status: "degraded", claim: T("ask_ai.degraded_banner"), evidence: [], missing: [] };
        STATE.ask.submitting = false;
        renderAskPanel();
      });
  }

  // -------------------------------------------------------------------
  // Render: navigation + lang toggle
  // -------------------------------------------------------------------

  function renderNav() {
    var nav = qs("ps-nav");
    clear(nav);
    ["today", "research", "replay", "ask_ai"].forEach(function (k) {
      var b = el("button", {
        type: "button",
        text: T("nav." + k),
        "aria-current": STATE.activePanel === k ? "page" : null,
        onClick: function () { setActivePanel(k); },
      });
      nav.appendChild(b);
    });
  }

  function renderLangToggle() {
    var tog = qs("ps-lang-toggle");
    clear(tog);
    ["ko", "en"].forEach(function (lg) {
      var b = el("button", {
        type: "button",
        text: lg.toUpperCase(),
        "aria-current": STATE.lang === lg ? "true" : "false",
        onClick: function () { setLang(lg); },
      });
      tog.appendChild(b);
    });
  }

  function setLang(lg) {
    if (lg !== "ko" && lg !== "en") return;
    if (STATE.lang === lg) return;
    STATE.lang = lg;
    try { window.localStorage.setItem("ps.lang", lg); } catch (e) { /* ignore */ }
    document.documentElement.lang = lg;
    fetchTodayDto();
  }

  function setActivePanel(key, opts) {
    opts = opts || {};
    STATE.activePanel = key;
    if (opts.asset_id !== undefined) STATE.focus.asset_id = opts.asset_id;
    if (opts.horizon_key !== undefined) STATE.focus.horizon_key = opts.horizon_key;
    ["today", "research", "replay", "ask_ai"].forEach(function (k) {
      var p = qs("ps-panel-" + (k === "ask_ai" ? "ask-ai" : k));
      if (!p) return;
      if (k === key) p.classList.remove("ps-hidden");
      else p.classList.add("ps-hidden");
    });
    renderNav();
    if (!opts.skipHash) updateHashFromState();
    if (key === "research") fetchResearchDto();
    else if (key === "replay") fetchReplayDto();
    else if (key === "ask_ai") fetchAskDto();
  }

  function updateHashFromState() {
    var key = STATE.activePanel;
    var hash;
    if (key === "today") {
      hash = "#today";
    } else {
      var panel = key === "ask_ai" ? "ask" : key;
      var params = [];
      if (STATE.focus.asset_id) params.push("asset=" + encodeURIComponent(STATE.focus.asset_id));
      if (STATE.focus.horizon_key) params.push("h=" + encodeURIComponent(STATE.focus.horizon_key));
      hash = "#" + panel + (params.length ? ("?" + params.join("&")) : "");
    }
    if (window.location.hash !== hash) {
      try { window.history.replaceState(null, "", hash); } catch (e) { window.location.hash = hash; }
    }
  }

  function parseHash() {
    var raw = String(window.location.hash || "").replace(/^#/, "");
    if (!raw) return null;
    var idx = raw.indexOf("?");
    var path = idx >= 0 ? raw.slice(0, idx) : raw;
    var query = idx >= 0 ? raw.slice(idx + 1) : "";
    var map = {};
    query.split("&").filter(Boolean).forEach(function (pair) {
      var kv = pair.split("=");
      map[decodeURIComponent(kv[0] || "")] = decodeURIComponent(kv[1] || "");
    });
    var panel = path === "ask" ? "ask_ai" : path;
    if (["today", "research", "replay", "ask_ai"].indexOf(panel) < 0) return null;
    return { panel: panel, asset_id: map.asset || null, horizon_key: map.h || null };
  }

  function applyHash() {
    var parsed = parseHash();
    if (!parsed) return;
    setActivePanel(parsed.panel, {
      asset_id: parsed.asset_id,
      horizon_key: parsed.horizon_key,
      skipHash: true,
    });
  }

  // -------------------------------------------------------------------
  // Render: trust strip
  // -------------------------------------------------------------------

  function renderTrustStrip(dto) {
    var ts = dto && dto.trust_strip || null;
    var host = qs("ps-trust-strip");
    clear(host);
    if (!ts) {
      host.appendChild(el("span", { className: "ps-caption", text: T("loading") }));
      return;
    }
    var tierChip = el("span", {
      className: "ps-tier-chip ps-tooltip",
      "data-tier": ts.tier_kind || "sample",
      "data-ps-tooltip": ts.tier_tooltip || "",
      text: ts.tier_label || "",
    });
    var lastBuilt = el("span", {
      className: "ps-trust-strip-value",
      text: ts.last_built_label || "—",
    });
    host.appendChild(el("span", { className: "ps-trust-strip-item" }, [
      el("span", { className: "ps-trust-strip-label", text: STATE.lang === "ko" ? "데이터 근거" : "Data tier" }),
      tierChip,
    ]));
    host.appendChild(el("span", { className: "ps-trust-strip-item" }, [
      el("span", { className: "ps-trust-strip-label", text: STATE.lang === "ko" ? "최신 갱신" : "Last refresh" }),
      lastBuilt,
    ]));
    // Degraded banner sits directly under the trust strip.
    var banner = qs("ps-degraded-banner");
    var glance = (dto && dto.today_at_a_glance) || {};
    if (glance.degraded_note) {
      banner.className = "ps-degraded-banner";
      banner.textContent = glance.degraded_note;
    } else {
      banner.className = "ps-hidden";
      banner.textContent = "";
    }
  }

  // -------------------------------------------------------------------
  // Render: Today
  // -------------------------------------------------------------------

  function renderToday(dto) {
    var host = qs("ps-panel-today");
    clear(host);
    if (STATE.loading) {
      host.appendChild(el("div", { className: "ps-stub-card" }, [
        el("div", { className: "ps-stub-card-title", text: T("loading") }),
      ]));
      return;
    }
    if (STATE.error) {
      host.appendChild(el("div", { className: "ps-stub-card" }, [
        el("div", { className: "ps-stub-card-title", text: T("error_headline") }),
        el("div", { className: "ps-stub-card-body", text: T("error_body") }),
        el("div", { className: "ps-stub-card-cta-row" }, [
          el("button", {
            className: "ps-hero-card-cta",
            "data-kind": "primary",
            text: T("retry"),
            onClick: fetchTodayDto,
          }),
        ]),
      ]));
      return;
    }
    if (!dto) return;

    host.appendChild(renderTodayGlance(dto.today_at_a_glance));
    host.appendChild(renderHeroGrid(dto.hero_cards || []));
    host.appendChild(renderSelectedMovers(dto.selected_movers || []));
    host.appendChild(renderWatchlistStrip(dto.watchlist_strip));
    host.appendChild(renderAdvancedDisclosure(dto.advanced_disclosure));
    if (dto.as_of) {
      host.appendChild(el("div", { className: "ps-caption", text: T("as_of_prefix") + dto.as_of }));
    }
  }

  function renderTodayGlance(glance) {
    glance = glance || {};
    var bullets = (glance.bullets || []).map(function (b) { return el("li", { text: b }); });
    return el("section", { className: "ps-today-glance" }, [
      el("div", { className: "ps-today-glance-title", text: glance.title || "" }),
      el("h1", { className: "ps-today-glance-headline", text: glance.headline || "" }),
      el("ul", { className: "ps-today-glance-bullets" }, bullets),
    ]);
  }

  function renderHeroGrid(heroCards) {
    var grid = el("div", { className: "ps-hero-grid", id: "ps-hero-grid" });
    heroCards.forEach(function (hc, idx) {
      grid.appendChild(renderHeroCard(hc, idx));
    });
    return grid;
  }

  function renderHeroCard(hc, idx) {
    hc = hc || {};
    var grade = hc.grade || { key: "c", label: "C" };
    var stance = hc.stance || { key: "neutral", label: "" };
    var conf = hc.confidence || { source_key: "preparing", label: "", tooltip: "" };

    var header = el("div", { className: "ps-hero-card-header" }, [
      el("div", { className: "ps-hero-card-horizon-label", text: hc.horizon_caption || "" }),
      el("div", { className: "ps-hero-card-family", text: hc.family_name || (hc.horizon_label || "") }),
    ]);

    var signalRow = el("div", { className: "ps-hero-card-signal-row" }, [
      el("span", {
        className: "ps-grade-chip ps-tooltip",
        "data-grade": grade.key,
        "data-ps-tooltip": STATE.lang === "ko"
          ? "신호 강도 등급입니다. A+ 가 가장 강하고, F 는 근거가 부족함을 뜻합니다."
          : "Signal strength grade. A+ is the strongest; F means evidence is insufficient.",
        text: grade.label,
      }),
      el("span", {
        className: "ps-stance-label",
        "data-stance": stance.key,
        text: stance.label,
      }),
      el("span", {
        className: "ps-confidence-badge ps-tooltip",
        "data-source": conf.source_key,
        "data-ps-tooltip": conf.tooltip || "",
        text: conf.label || "",
      }),
    ]);

    var story = el("div", { className: "ps-hero-card-story", text: hc.story || "" });

    var positionBar = renderPositionBar(hc.position_strength || 0);

    var sparkline = renderSparkline(hc.sparkline || { points: [], direction: "neutral" });

    // Evidence drawer (Today-local, R1: no page navigation)
    var drawer = renderEvidenceDrawer(hc);

    var cta = el("div", { className: "ps-hero-card-footer" }, [
      el("button", {
        className: "ps-hero-card-cta",
        "data-kind": "primary",
        type: "button",
        text: (hc.cta_primary || {}).label || "",
        onClick: function (ev) {
          ev.preventDefault();
          var det = drawer; // <details> element
          if (det && det.tagName === "DETAILS") det.open = !det.open;
        },
      }),
      el("button", {
        className: "ps-hero-card-cta",
        "data-kind": "secondary",
        type: "button",
        text: (hc.cta_secondary || {}).label || "",
        title: (hc.cta_secondary || {}).hint || "",
        onClick: function () {
          setActivePanel("research", {
            asset_id: null,
            horizon_key: hc.horizon_key || null,
          });
        },
      }),
    ]);

    return el("article", { className: "ps-hero-card", "data-horizon": hc.horizon_key || "" }, [
      header, signalRow, story, positionBar, sparkline, cta, drawer,
    ]);
  }

  function renderPositionBar(strength) {
    var s = Math.max(-1, Math.min(1, Number(strength) || 0));
    var wrap = el("div", { className: "ps-hero-position-bar" });
    var fill = el("div", { className: "ps-hero-position-bar-fill" });
    if (s >= 0) {
      var w = Math.round(s * 50);
      fill.style.width = w + "%";
      fill.style.left = "50%";
    } else {
      var w2 = Math.round(-s * 50);
      fill.style.width = w2 + "%";
      fill.style.left = (50 - w2) + "%";
      fill.setAttribute("data-stance-sign", "negative");
    }
    wrap.appendChild(fill);
    return wrap;
  }

  function renderSparkline(spec) {
    var pts = (spec && spec.points) || [];
    var direction = (spec && spec.direction) || "neutral";
    var w = 240, h = 36, pad = 2;
    if (!pts.length) {
      // Empty placeholder (degraded) — muted flat line
      var placeholderSvg = '<svg class="ps-mini-sparkline" viewBox="0 0 ' + w + ' ' + h + '" preserveAspectRatio="none" aria-hidden="true">' +
        '<line x1="' + pad + '" y1="' + (h / 2) + '" x2="' + (w - pad) + '" y2="' + (h / 2) +
        '" stroke="var(--ps-text-muted)" stroke-width="1.25" stroke-dasharray="3 3" /></svg>';
      var box = document.createElement("div");
      box.innerHTML = placeholderSvg;
      return box.firstChild;
    }
    var min = Math.min.apply(null, pts);
    var max = Math.max.apply(null, pts);
    var span = (max - min) || 1;
    var innerW = w - 2 * pad;
    var innerH = h - 2 * pad;
    var step = pts.length > 1 ? innerW / (pts.length - 1) : innerW;
    var coords = pts.map(function (p, i) {
      var x = pad + step * i;
      var y = pad + innerH - ((p - min) / span) * innerH;
      return [x, y];
    });
    var linePath = coords.map(function (c, i) {
      return (i === 0 ? "M" : "L") + c[0].toFixed(2) + " " + c[1].toFixed(2);
    }).join(" ");
    var areaPath = linePath +
      " L " + (pad + innerW).toFixed(2) + " " + (h - pad).toFixed(2) +
      " L " + pad.toFixed(2) + " " + (h - pad).toFixed(2) + " Z";
    var last = coords[coords.length - 1];
    var svgStr = '<svg class="ps-mini-sparkline" data-direction="' + direction +
      '" viewBox="0 0 ' + w + ' ' + h + '" preserveAspectRatio="none" aria-hidden="true">' +
      '<path class="ps-spark-area" d="' + areaPath + '" />' +
      '<path class="ps-spark-line" d="' + linePath + '" />' +
      '<circle class="ps-spark-dot" cx="' + last[0].toFixed(2) + '" cy="' + last[1].toFixed(2) + '" r="2.25" />' +
      '</svg>';
    var wrap = document.createElement("div");
    wrap.innerHTML = svgStr;
    return wrap.firstChild;
  }

  function renderEvidenceDrawer(hc) {
    var ev = hc.evidence || {};
    var details = el("details", { className: "ps-disclosure-drawer" });
    var summary = el("summary", { text: T("evidence_title") });
    details.appendChild(summary);
    var body = el("div", { className: "ps-disclosure-drawer-body" }, [
      el("div", { className: "ps-evidence-drawer-title", text: T("evidence_what") }),
      el("div", { className: "ps-evidence-card-body", text: ev.what_changed || "" }),
      el("div", { className: "ps-evidence-card" }, [
        el("div", { className: "ps-evidence-card-label", text: T("evidence_support") }),
        el("div", { className: "ps-evidence-card-body", text: ev.strongest_support || "" }),
      ]),
      el("div", { className: "ps-evidence-card" }, [
        el("div", { className: "ps-evidence-card-label", text: T("evidence_why") }),
        el("div", { className: "ps-evidence-card-body", text: ev.why_confidence || "" }),
      ]),
    ]);
    details.appendChild(body);
    return details;
  }

  function renderSelectedMovers(movers) {
    var section = el("section", { className: "ps-stack" });
    section.appendChild(el("div", { className: "ps-caption", text: T("movers_title") }));
    if (!movers.length) {
      section.appendChild(el("div", { className: "ps-body-small", text: T("no_movers") }));
      return section;
    }
    var grid = el("div", { className: "ps-mover-grid" });
    movers.forEach(function (m) {
      var grade = m.grade || { key: "c", label: "C" };
      var stance = m.stance || { key: "neutral", label: "" };
      var head = el("div", { className: "ps-mover-card-head" }, [
        el("div", { className: "ps-mover-card-ticker", text: m.ticker || "" }),
        el("span", {
          className: "ps-grade-chip",
          "data-grade": grade.key,
          text: grade.label,
        }),
      ]);
      var reasonLine = el("div", { className: "ps-mover-card-reason", text: m.reason || "" });
      var stanceLine = el("span", {
        className: "ps-stance-label",
        "data-stance": stance.key,
        text: stance.label,
      });
      var deepLink = el("button", {
        type: "button",
        className: "ps-research-tile__deeplink",
        text: T("research.tile_deeplink"),
        onClick: function () {
          setActivePanel("research", {
            asset_id: m.ticker || null,
            horizon_key: m.horizon_key || null,
          });
        },
      });
      grid.appendChild(el("article", { className: "ps-mover-card" }, [
        head, reasonLine, stanceLine, deepLink,
      ]));
    });
    section.appendChild(grid);
    return section;
  }

  function renderWatchlistStrip(strip) {
    strip = strip || {};
    var section = el("section", { className: "ps-watchlist-strip" });
    section.appendChild(el("div", { className: "ps-watchlist-strip-title", text: strip.title || "" }));
    var chipsWrap = el("div", { className: "ps-watchlist-strip-chips" });
    var tickers = (strip.tickers || []);
    if (!tickers.length) {
      section.appendChild(el("div", { className: "ps-caption", text: T("no_watchlist") }));
      return section;
    }
    tickers.forEach(function (t) {
      var grade = t.grade || { key: "c", label: "C" };
      var stance = t.stance || { key: "neutral", label: "—" };
      chipsWrap.appendChild(el("span", { className: "ps-watchlist-chip" }, [
        el("span", { className: "ps-watchlist-chip-ticker", text: t.ticker || "" }),
        el("span", {
          className: "ps-grade-chip",
          "data-grade": grade.key,
          text: grade.label,
        }),
        el("span", {
          className: "ps-stance-label",
          "data-stance": stance.key,
          text: stance.label || "",
        }),
      ]));
    });
    section.appendChild(chipsWrap);
    if (strip.caption) {
      section.appendChild(el("div", { className: "ps-caption", text: strip.caption }));
    }
    return section;
  }

  function renderAdvancedDisclosure(adv) {
    adv = adv || {};
    var det = el("details", { className: "ps-disclosure-drawer" });
    det.appendChild(el("summary", { text: adv.label || T("advanced_open") }));
    det.appendChild(el("div", { className: "ps-disclosure-drawer-body ps-body-small", text: adv.hint || "" }));
    return det;
  }

  // -------------------------------------------------------------------
  // Render: Research (landing + deep-dive 3-rail)
  // -------------------------------------------------------------------

  function _signalBadges(item) {
    var grade = item.grade || { key: "c", label: "C" };
    var stance = item.stance || { key: "neutral", label: "" };
    var conf = item.confidence || { source_key: "preparing", label: "" };
    return [
      el("span", { className: "ps-grade-chip", "data-grade": grade.key, text: grade.label }),
      el("span", { className: "ps-stance-label", "data-stance": stance.key, text: stance.label }),
      el("span", {
        className: "ps-confidence-badge",
        "data-source": conf.source_key,
        text: conf.label || "",
      }),
    ];
  }

  function renderResearchPanel() {
    var host = qs("ps-panel-research");
    if (!host) return;
    clear(host);
    if (STATE.research.loading) {
      host.appendChild(el("div", { className: "ps-stub-card" }, [
        el("div", { className: "ps-stub-card-title", text: T("loading") }),
      ]));
      return;
    }
    if (STATE.research.error) {
      host.appendChild(el("div", { className: "ps-stub-card" }, [
        el("div", { className: "ps-stub-card-title", text: T("error_headline") }),
        el("div", { className: "ps-stub-card-body", text: T("error_body") }),
      ]));
      return;
    }
    var dto = STATE.research.dto;
    if (!dto) return;
    if (dto.presentation === "deepdive") {
      host.appendChild(renderResearchDeepDive(dto));
    } else {
      host.appendChild(renderResearchLanding(dto));
    }
  }

  function renderResearchLanding(dto) {
    var wrap = el("section", { className: "ps-research-landing" });
    wrap.appendChild(el("h1", { className: "ps-h2", text: T("research.landing_title") }));
    if (dto.headline) {
      wrap.appendChild(el("div", { className: "ps-research-headline", text: dto.headline }));
    }
    var grid = el("div", { className: "ps-research-landing-grid" });
    (dto.columns || []).forEach(function (col) {
      grid.appendChild(renderResearchColumn(col));
    });
    wrap.appendChild(grid);
    return wrap;
  }

  function renderResearchColumn(col) {
    var wrap = el("div", { className: "ps-research-column" });
    wrap.appendChild(el("div", { className: "ps-research-column__head" }, [
      el("div", { className: "ps-research-column__caption", text: col.horizon_caption || "" }),
      el("div", { className: "ps-research-column__title", text: col.horizon_label || col.family_name || "" }),
      col.claim_headline
        ? el("div", { className: "ps-research-column__headline", text: col.claim_headline })
        : null,
    ]));
    var tiles = col.tiles || [];
    if (!tiles.length) {
      var emptyMsg = (col.empty_state && col.empty_state.body) || T("research.empty_tiles");
      wrap.appendChild(el("div", { className: "ps-research-empty", text: emptyMsg }));
      return wrap;
    }
    tiles.forEach(function (tile) {
      var card = el("div", { className: "ps-research-tile" }, [
        el("div", { className: "ps-research-tile__row" }, [
          el("div", { className: "ps-research-tile__ticker", text: tile.ticker || "" }),
          el("div", { className: "ps-row", style: { gap: "4px", alignItems: "center" } }, _signalBadges(tile)),
        ]),
        el("div", { className: "ps-research-tile__summary", text: tile.summary || "" }),
        el("button", {
          type: "button",
          className: "ps-research-tile__deeplink",
          text: T("research.tile_deeplink"),
          onClick: function () {
            setActivePanel("research", {
              asset_id: tile.ticker || null,
              horizon_key: col.horizon_key || null,
            });
          },
        }),
      ]);
      wrap.appendChild(card);
    });
    return wrap;
  }

  function renderResearchDeepDive(dto) {
    var wrap = el("section", { className: "ps-research-deepdive" });
    wrap.appendChild(renderBreadcrumbs([
      { label: T("research.breadcrumbs_home"), onClick: function () {
        setActivePanel("research", { asset_id: null, horizon_key: null });
      }},
      { label: (dto.claim && dto.claim.ticker) || "" },
    ]));
    var rails = el("div", { className: "ps-rails" });
    rails.appendChild(renderClaimCard(dto.claim || {}));
    rails.appendChild(renderEvidenceRail(dto.evidence || []));
    rails.appendChild(renderActionRail(dto.actions || [], dto));
    wrap.appendChild(rails);
    return wrap;
  }

  function renderBreadcrumbs(crumbs) {
    var c = el("nav", { className: "ps-breadcrumbs" });
    crumbs.forEach(function (b, idx) {
      if (idx > 0) c.appendChild(el("span", { className: "ps-breadcrumbs__sep", text: "/" }));
      if (b.onClick) {
        c.appendChild(el("button", { type: "button", text: b.label, onClick: b.onClick }));
      } else {
        c.appendChild(el("span", { text: b.label }));
      }
    });
    return c;
  }

  function renderClaimCard(claim) {
    var card = el("article", {
      className: "ps-claim-card",
      "data-row-matched": claim.row_matched === false ? "false" : "true",
    }, [
      el("div", { className: "ps-claim-card__horizon", text: claim.horizon_caption || "" }),
      el("div", { className: "ps-claim-card__ticker", text: claim.ticker || "" }),
      el("div", { className: "ps-claim-card__row" }, _signalBadges(claim)),
      el("div", { className: "ps-claim-card__summary", text: claim.summary || "" }),
    ]);
    return card;
  }

  function _evidenceTitleFor(kind) {
    switch (kind) {
      case "what_changed":           return T("research.evidence_what");
      case "strongest_support":      return T("research.evidence_support");
      case "counter_or_companion":   return T("research.evidence_counter");
      case "missing_or_preparing":   return T("research.evidence_missing");
      case "peer_context":           return T("research.evidence_peer");
      default:                       return kind || "";
    }
  }

  function renderEvidenceRail(cards) {
    var wrap = el("div", { className: "ps-evidence-rail" });
    wrap.appendChild(el("div", { className: "ps-research-column__caption", text: T("research.evidence_title") }));
    cards.forEach(function (c) {
      wrap.appendChild(renderEvidenceCard(c));
    });
    return wrap;
  }

  function renderEvidenceCard(c) {
    var card = el("article", { className: "ps-evidence-card", "data-kind": c.kind || "" });
    var titleRow = el("div", { className: "ps-evidence-card__title" }, [
      document.createTextNode(c.title || _evidenceTitleFor(c.kind)),
    ]);
    if (c.kind === "missing_or_preparing") {
      titleRow.appendChild(el("span", { className: "ps-missing-badge", text: c.badge_label || "preparing" }));
    }
    card.appendChild(titleRow);
    if (c.body) {
      card.appendChild(el("div", { className: "ps-evidence-card__body", text: c.body }));
    }
    if (Array.isArray(c.peers) && c.peers.length) {
      var peersRow = el("div", { className: "ps-claim-card__row" });
      c.peers.forEach(function (p) {
        peersRow.appendChild(el("span", { className: "ps-peer-chip", text: (p && p.ticker) || "" }));
      });
      card.appendChild(peersRow);
    }
    return card;
  }

  function renderActionRail(actions, dto) {
    var wrap = el("div", { className: "ps-action-rail" });
    wrap.appendChild(el("div", { className: "ps-research-column__caption", text: T("research.action_title") }));
    (actions || []).forEach(function (a) {
      wrap.appendChild(el("button", {
        type: "button",
        className: "ps-action-chip",
        onClick: function () { performActionKind(a.kind, a, dto); },
      }, [
        el("span", { text: a.label || a.kind || "" }),
        a.hint ? el("span", { className: "ps-action-chip__hint", text: a.hint }) : null,
      ]));
    });
    return wrap;
  }

  function performActionKind(kind, action, dto) {
    var asset = STATE.focus.asset_id;
    var hz = STATE.focus.horizon_key;
    if (kind === "open_replay") {
      setActivePanel("replay", { asset_id: asset, horizon_key: hz });
    } else if (kind === "ask_ai") {
      setActivePanel("ask_ai", { asset_id: asset, horizon_key: hz });
    } else if (kind === "back_to_today") {
      setActivePanel("today", { asset_id: null, horizon_key: null });
    }
  }

  // -------------------------------------------------------------------
  // Render: Replay (timeline + scenarios + advanced drawer)
  // -------------------------------------------------------------------

  function renderReplayPanel() {
    var host = qs("ps-panel-replay");
    if (!host) return;
    clear(host);
    if (STATE.replay.loading) {
      host.appendChild(el("div", { className: "ps-stub-card" }, [
        el("div", { className: "ps-stub-card-title", text: T("loading") }),
      ]));
      return;
    }
    if (STATE.replay.error) {
      host.appendChild(el("div", { className: "ps-stub-card" }, [
        el("div", { className: "ps-stub-card-title", text: T("error_headline") }),
        el("div", { className: "ps-stub-card-body", text: T("error_body") }),
      ]));
      return;
    }
    var dto = STATE.replay.dto;
    if (!dto) return;
    var wrap = el("section", { className: "ps-replay" });
    wrap.appendChild(renderBreadcrumbs([
      { label: T("nav.today"), onClick: function () {
        setActivePanel("today", { asset_id: null, horizon_key: null });
      }},
      { label: T("nav.replay") },
    ]));

    var focus = dto.focus || {};
    var header = el("div", { className: "ps-replay-header" }, [
      el("h1", { className: "ps-h2", text: T("replay.title") }),
      dto.headline ? el("div", { className: "ps-body-small", text: dto.headline }) : null,
      focus.horizon_caption ? el("div", { className: "ps-caption", text: focus.horizon_caption + (focus.asset_id ? " · " + focus.asset_id : "") }) : null,
    ]);
    wrap.appendChild(header);

    if (dto.summary_counts) {
      var s = dto.summary_counts;
      var row = el("div", { className: "ps-replay-summary" }, [
        el("span", {}, [
          el("strong", { text: String(s.total_events || 0) }),
          document.createTextNode(" " + T("replay.summary_events")),
        ]),
      ]);
      wrap.appendChild(row);
    }

    wrap.appendChild(renderReplayTimeline(dto.timeline || [], dto.empty_state));
    if ((dto.scenarios || []).length) {
      wrap.appendChild(renderReplayScenarios(dto.scenarios));
    }
    if (dto.advanced_disclosure) {
      wrap.appendChild(renderAdvancedPayload(dto.advanced_disclosure));
    }

    host.appendChild(wrap);
  }

  function renderReplayTimeline(items, emptyState) {
    var section = el("section", { className: "ps-stack" });
    section.appendChild(el("div", { className: "ps-caption", text: T("replay.timeline_title") }));
    if (!items.length) {
      var msg = (emptyState && emptyState.body) || T("replay.empty_timeline");
      section.appendChild(el("div", { className: "ps-research-empty", text: msg }));
      return section;
    }
    var timeline = el("div", { className: "ps-replay-timeline" });
    items.forEach(function (it) {
      if (it.kind === "gap") {
        timeline.appendChild(el("div", { className: "ps-timeline-gap", text: it.title || ((it.days || 0) + " " + T("replay.gap_days")) }));
        return;
      }
      if (it.kind === "checkpoint") {
        timeline.appendChild(el("div", { className: "ps-timeline-checkpoint", text: it.title || T("replay.checkpoint_decision") }));
        return;
      }
      var node = el("div", { className: "ps-timeline-event", "data-tag": it.tag || "" }, [
        el("div", { className: "ps-timeline-event__row" }, [
          el("span", { className: "ps-timeline-event__ts", text: it.ts || "" }),
          el("span", { className: "ps-timeline-event__title", text: it.title || "" }),
        ]),
        it.body ? el("div", { className: "ps-timeline-event__body", text: it.body }) : null,
      ]);
      timeline.appendChild(node);
    });
    section.appendChild(timeline);
    return section;
  }

  function renderReplayScenarios(scenarios) {
    var section = el("section", { className: "ps-stack" });
    section.appendChild(el("div", { className: "ps-caption", text: T("replay.scenarios_title") }));
    var grid = el("div", { className: "ps-scenarios" });
    scenarios.forEach(function (sc) {
      var meta = el("div", { className: "ps-scenario-card__meta" }, _signalBadges(sc));
      grid.appendChild(el("article", { className: "ps-scenario-card", "data-kind": sc.kind || "" }, [
        el("div", { className: "ps-scenario-card__title", text: sc.title || "" }),
        el("div", { className: "ps-scenario-card__body", text: sc.body || "" }),
        meta,
        (sc.hint && sc.hint.body)
          ? el("div", { className: "ps-scenario-card__hint", text: sc.hint.body })
          : null,
      ]));
    });
    section.appendChild(grid);
    return section;
  }

  function renderAdvancedPayload(advanced) {
    var det = el("details", { className: "ps-advanced-drawer" });
    det.appendChild(el("summary", { className: "ps-advanced-drawer__summary", text: advanced.label || T("replay.advanced_label") }));
    det.appendChild(el("div", { className: "ps-advanced-drawer__body", text: advanced.hint || "" }));
    return det;
  }

  // -------------------------------------------------------------------
  // Render: Ask AI
  // -------------------------------------------------------------------

  function renderAskPanel() {
    var host = qs("ps-panel-ask-ai");
    if (!host) return;
    clear(host);
    if (STATE.ask.loading) {
      host.appendChild(el("div", { className: "ps-stub-card" }, [
        el("div", { className: "ps-stub-card-title", text: T("loading") }),
      ]));
      return;
    }
    if (STATE.ask.error) {
      host.appendChild(el("div", { className: "ps-stub-card" }, [
        el("div", { className: "ps-stub-card-title", text: T("error_headline") }),
        el("div", { className: "ps-stub-card-body", text: T("error_body") }),
      ]));
      return;
    }
    var dto = STATE.ask.dto || {};
    var wrap = el("section", { className: "ps-ask" });

    var main = el("div", { className: "ps-ask-main" });
    main.appendChild(renderBreadcrumbs([
      { label: T("nav.today"), onClick: function () {
        setActivePanel("today", { asset_id: null, horizon_key: null });
      }},
      { label: T("nav.ask_ai") },
    ]));
    main.appendChild(renderAskContextCard(dto.context || {}));
    if (dto.contract_banner) {
      main.appendChild(el("div", { className: "ps-caption", text: dto.contract_banner.body || "" }));
    }
    main.appendChild(renderAskQuickActions(dto.quick_chips || []));
    main.appendChild(renderAskFreeText(dto.free_text || {}));
    if (STATE.ask.answer) main.appendChild(renderAskAnswer(STATE.ask.answer));
    wrap.appendChild(main);

    wrap.appendChild(renderAskSide());
    host.appendChild(wrap);
  }

  function renderAskContextCard(ctx) {
    return el("div", { className: "ps-ask-context-card" }, [
      el("div", { className: "ps-research-column__caption", text: T("ask_ai.context_prefix") }),
      el("div", { className: "ps-ask-context-card__frame", text: ctx.frame || ctx.summary || "" }),
      el("div", { className: "ps-ask-context-card__row" }, _signalBadges(ctx)),
    ]);
  }

  function renderAskQuickActions(actions) {
    var section = el("section", { className: "ps-stack" });
    section.appendChild(el("div", { className: "ps-caption", text: T("ask_ai.quick_title") }));
    var grid = el("div", { className: "ps-ask-quick-grid" });
    (actions || []).forEach(function (a) {
      var pressed = STATE.ask.selected_intent === a.intent;
      grid.appendChild(el("button", {
        type: "button",
        className: "ps-ask-action-chip",
        "aria-pressed": pressed ? "true" : "false",
        text: a.label || T("ask_ai.quick_intents." + (a.intent || "")) || a.intent || "",
        onClick: function () { fetchQuickAnswer(a.intent); },
      }));
    });
    section.appendChild(grid);
    return section;
  }

  function renderAskFreeText(freeTextSpec) {
    var section = el("section", { className: "ps-stack" });
    section.appendChild(el("div", { className: "ps-caption", text: T("ask_ai.freetext_title") }));
    var box = el("div", { className: "ps-ask-freetext" });
    var placeholder = STATE.lang === "ko"
      ? (freeTextSpec.placeholder_ko || T("ask_ai.freetext_placeholder"))
      : (freeTextSpec.placeholder_en || T("ask_ai.freetext_placeholder"));
    var ta = el("textarea", {
      placeholder: placeholder,
      "aria-label": T("ask_ai.freetext_title"),
      maxlength: freeTextSpec.max_length || 400,
    });
    ta.value = STATE.ask.free_text || "";
    ta.addEventListener("input", function () { STATE.ask.free_text = ta.value; });
    box.appendChild(ta);
    var row = el("div", { className: "ps-ask-freetext__row" }, [
      el("span", { text: "" }),
      el("button", {
        type: "button",
        className: "ps-ask-freetext__submit",
        text: T("ask_ai.submit"),
        disabled: STATE.ask.submitting ? "true" : null,
        onClick: postFreeText,
      }),
    ]);
    box.appendChild(row);
    section.appendChild(box);
    return section;
  }

  function renderAskAnswer(ans) {
    if (!ans) return null;
    if (ans.status === "loading") {
      return el("div", { className: "ps-ask-answer", text: T("loading") });
    }
    var grounded = ans.grounded === true || ans.kind === "grounded";
    var kind = grounded ? "grounded" : "degraded";
    var wrap = el("article", { className: "ps-ask-answer", "data-kind": kind });
    if (ans.banner) {
      wrap.appendChild(el("div", { className: "ps-ask-answer__banner", text: ans.banner }));
    } else if (!grounded) {
      wrap.appendChild(el("div", { className: "ps-ask-answer__banner", text: T("ask_ai.degraded_banner") }));
    }
    var claim = ans.claim || [];
    if (typeof claim === "string") claim = [claim];
    if (claim.length) {
      wrap.appendChild(el("div", { className: "ps-ask-answer__section-title", text: T("ask_ai.answer_claim") }));
      var ulc = el("ul", {});
      claim.forEach(function (c) {
        ulc.appendChild(el("li", { text: typeof c === "string" ? c : (c && c.body) || "" }));
      });
      wrap.appendChild(ulc);
    }
    var evidence = ans.evidence || [];
    if (evidence.length) {
      wrap.appendChild(el("div", { className: "ps-ask-answer__section-title", text: T("ask_ai.answer_evidence") }));
      var ul = el("ul", {});
      evidence.forEach(function (e) {
        ul.appendChild(el("li", { text: typeof e === "string" ? e : (e && e.body) || "" }));
      });
      wrap.appendChild(ul);
    }
    var missing = ans.insufficiency || ans.missing || [];
    if (missing.length) {
      wrap.appendChild(el("div", { className: "ps-ask-answer__section-title", text: T("ask_ai.answer_missing") }));
      var ul2 = el("ul", {});
      missing.forEach(function (m) {
        ul2.appendChild(el("li", { text: typeof m === "string" ? m : (m && m.body) || "" }));
      });
      wrap.appendChild(ul2);
    }
    return wrap;
  }

  function renderAskSide() {
    var side = el("aside", { className: "ps-ask-side" });
    side.appendChild(el("div", { className: "ps-caption", text: T("ask_ai.requests_title") }));
    var embedded = (STATE.ask.dto && STATE.ask.dto.requests) || {};
    var standalone = STATE.requests.dto || {};
    var cards = (standalone.cards && standalone.cards.length)
      ? standalone.cards
      : (embedded.cards || []);
    if (!cards.length) {
      var empty = standalone.empty_state || embedded.empty_state;
      side.appendChild(el("div", {
        className: "ps-request-state-empty",
        text: (empty && empty.body) || T("ask_ai.requests_empty"),
      }));
      return side;
    }
    cards.forEach(function (c) {
      side.appendChild(el("div", { className: "ps-request-state-card", "data-status": c.status_key || "" }, [
        el("div", { className: "ps-request-state-card__status", text: c.status_label || "" }),
        el("div", { className: "ps-request-state-card__summary", text: c.summary || "" }),
      ]));
    });
    return side;
  }

  // -------------------------------------------------------------------
  // Footer
  // -------------------------------------------------------------------

  function renderFooter() {
    var f = qs("ps-footer");
    clear(f);
    f.textContent = T("footer");
  }

  // -------------------------------------------------------------------
  // Orchestration
  // -------------------------------------------------------------------

  function renderAll() {
    renderNav();
    renderLangToggle();
    renderTrustStrip(STATE.today || {});
    renderToday(STATE.today);
    renderResearchPanel();
    renderReplayPanel();
    renderAskPanel();
    renderFooter();
  }

  // Exposed for regression harness only — not a public API.
  window.__PS__ = {
    STATE: STATE,
    render: renderAll,
    fetch: fetchTodayDto,
    setLang: setLang,
    setActivePanel: setActivePanel,
  };

  document.addEventListener("DOMContentLoaded", function () {
    document.documentElement.lang = STATE.lang;
    renderAll();
    fetchTodayDto();
    window.addEventListener("hashchange", applyHash);
    applyHash();
  });
})();
