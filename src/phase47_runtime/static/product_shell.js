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

  function setActivePanel(key) {
    STATE.activePanel = key;
    ["today", "research", "replay", "ask_ai"].forEach(function (k) {
      var p = qs("ps-panel-" + (k === "ask_ai" ? "ask-ai" : k));
      if (!p) return;
      if (k === key) p.classList.remove("ps-hidden");
      else p.classList.add("ps-hidden");
    });
    renderNav();
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
        "aria-disabled": "true",
        disabled: "true",
        title: (hc.cta_secondary || {}).hint || "",
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
      grid.appendChild(el("article", { className: "ps-mover-card" }, [
        head, reasonLine, stanceLine,
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
  // Render: stub panels (Research / Replay / Ask AI) — 10B-待
  // -------------------------------------------------------------------

  function renderStub(panelId, stubKey) {
    var host = qs(panelId);
    clear(host);
    var stubs = (STATE.today && STATE.today.stubs) || {};
    var s = stubs[stubKey] || {};
    var card = el("div", { className: "ps-stub-card" }, [
      el("div", { className: "ps-stub-card-title", text: s.title || "Coming soon" }),
      el("div", { className: "ps-stub-card-body", text: s.body || "" }),
      s.eta ? el("div", { className: "ps-caption", text: "ETA · " + s.eta }) : null,
    ]);
    host.appendChild(card);
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
    renderStub("ps-panel-research", "research");
    renderStub("ps-panel-replay", "replay");
    renderStub("ps-panel-ask-ai", "ask_ai");
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
  });
})();
