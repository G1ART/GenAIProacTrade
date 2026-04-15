"""Phase 47e — key-based KO/EN user language (product copy, not literal translation)."""

from __future__ import annotations

from typing import Any

SUPPORTED_LANGS: tuple[str, ...] = ("ko", "en")

# Internal stance / gate tokens → user-facing (per language). Codes never shown in primary UI.
STATUS_TRANSLATIONS_KO: dict[str, str] = {
    "deferred_due_to_proxy_limited_falsifier_substrate": "근거가 아직 좁아 더 강한 주장은 보류 중입니다",
    "closed_pending_new_evidence": "새 근거가 들어오기 전까지 종료된 상태입니다",
    "material_falsifier_improvement: false": "최근 검증에서 의사결정 품질을 끌어올릴 만한 개선은 확인되지 않았습니다",
    "optimistic_sector_relabel_only": "진단 표현은 다듬어졌으나, 결정 상태의 본질은 크게 바뀌지 않았습니다",
    "narrow_claims_document_proxy_limits_operator_closeout_v1": "주장 범위를 좁히고, 더 강한 근거가 나올 때까지 유지합니다",
    "hold_closeout_until_named_new_source_or_new_evidence_v1": "새로 명명된 출처나 새 근거가 등록될 때까지 클로즈아웃을 유지합니다",
    "deferred": "보류 — 더 단단한 근거를 기다립니다",
    "watching_for_new_evidence": "새 근거를 주시하는 중입니다",
    "claim_narrowed_closed": "주장이 좁혀졌고, 현재 근거 범위에서는 사실상 종료로 봅니다",
}

STATUS_TRANSLATIONS_EN: dict[str, str] = {
    "deferred_due_to_proxy_limited_falsifier_substrate": "Evidence is still too thin for a stronger claim",
    "closed_pending_new_evidence": "Closed until new evidence arrives",
    "material_falsifier_improvement: false": "The latest pass did not materially improve decision-quality evidence",
    "optimistic_sector_relabel_only": "Labels moved, but the decision state did not materially improve",
    "narrow_claims_document_proxy_limits_operator_closeout_v1": "Keep claims narrow and wait for stronger evidence",
    "hold_closeout_until_named_new_source_or_new_evidence_v1": "Hold the closeout until a new named source or evidence lands",
    "deferred": "Deferred — waiting on stronger evidence",
    "watching_for_new_evidence": "Watching for new evidence",
    "claim_narrowed_closed": "Claims are narrowed; treated as closed under current evidence",
}

OBJECT_KIND_LABELS: dict[str, dict[str, str]] = {
    "ko": {
        "opportunity": "주목할 기회",
        "watchlist_item": "워치리스트 항목",
        "closed_research_fixture": "종료된 연구 기록",
        "alert": "알림",
        "decision_log_entry": "결정 기록",
        "cohort_research_object": "코호트 연구 객체",
    },
    "en": {
        "opportunity": "Opportunity",
        "watchlist_item": "Watchlist item",
        "closed_research_fixture": "Closed research record",
        "alert": "Alert",
        "decision_log_entry": "Decision entry",
        "cohort_research_object": "Cohort research object",
    },
}

OBJECT_KIND_HINTS: dict[str, dict[str, str]] = {
    "ko": {
        "opportunity": "진지하게 살펴볼 만한 근거가 있습니다(곧바로 매수 신호는 아닙니다).",
        "watchlist_item": "지켜볼 가치는 있으나, 지금 결정하기엔 이릅니다.",
        "closed_research_fixture": "종료·보류·주장 축소 등 — 실행 가능한 제안으로 포장되지 않습니다.",
        "alert": "시간이나 상태 변화에 따른 신호입니다.",
        "decision_log_entry": "기록된 결정입니다.",
        "cohort_research_object": "권위 번들 기준 코호트 연구 객체입니다.",
    },
    "en": {
        "opportunity": "Worth serious attention — not necessarily a buy signal.",
        "watchlist_item": "Worth tracking; not decision-ready yet.",
        "closed_research_fixture": "Closed, deferred, or narrowed — not sold as an actionable pitch.",
        "alert": "A time- or state-based signal.",
        "decision_log_entry": "A recorded decision.",
        "cohort_research_object": "Cohort research object for the authoritative bundle.",
    },
}

# Flat shell keys for API + optional data-i18n in HTML
SHELL: dict[str, dict[str, str]] = {
    "ko": {
        "shell.title": "투자 운영 콕핏",
        "shell.lang_switch": "언어",
        "shell.subtitle": "오늘의 우선순위, 워치리스트, 진행 중 연구, 결정, 그리고 범위가 정해진 AI까지 — 내부 연구 뷰어가 아닙니다.",
        "shell.lang_ko": "한국어",
        "shell.lang_en": "English",
        "nav.home": "홈",
        "nav.watchlist": "워치리스트",
        "nav.research": "연구",
        "nav.replay": "리플레이",
        "nav.journal": "저널",
        "nav.ask_ai": "Ask AI",
        "nav.advanced": "고급",
        "nav.reload": "번들 다시 읽기",
        "panel.home.title": "홈 — 오늘의 화면",
        "panel.home.meta": "요약만 보여 드립니다. 원시 JSON은 고급 탭에서 확인하세요.",
        "panel.home.today_hero_meta": "MVP Sprint 3: Today 스펙트럼을 홈 상단에 둡니다. 아래 카드는 맥락·워치·연구·저널 요약입니다.",
        "panel.watchlist.title": "워치리스트",
        "panel.watchlist.meta": "추적 중인 이름·코호트와, 아직 기회로 올리지 않는 이유를 쉬운 말로 정리합니다.",
        "panel.research.title": "연구",
        "panel.research.meta": "코호트 상세·근거·아카이브 맥락입니다. 종료된 연구 기록의 본문은 홈 히어로가 아닙니다.",
        "panel.journal.title": "저널 — 결정 기록",
        "panel.journal.meta": "무엇을 왜 결정했는지 읽기 쉬운 카드로 보여 줍니다.",
        "panel.journal.record": "결정 남기기",
        "panel.journal.empty": "아직 기록된 결정이 없습니다. 아래에서 보류·관찰·연기 등을 남기면 카드로 쌓이며, 리플레이 맥락과 연결됩니다.",
        "panel.replay.title": "리플레이 — 시간 순 추적",
        "panel.replay.meta": "그 시점에 알 수 있었던 것만 보여 줍니다. **당시 결정 품질**과 **이후 결과**는 구분합니다.",
        "panel.replay.tab_timeline": "리플레이",
        "panel.replay.tab_cf": "반사실 검토실",
        "panel.replay.micro": "요약 브리프",
        "panel.replay.micro_empty": "이벤트를 선택하면 당시 입장·근거·‘그때까지 알려진 것’이 정리됩니다.",
        "panel.replay.chart_note": "점선은 참고용 리듬(실시간 시세 아님). 마커는 입장 코드에서 만든 지표입니다.",
        "panel.replay.cf_intro": "가설 분기 — 리플레이 축에 그리지 않습니다. 이 빌드에는 수치 엔진이 없습니다.",
        "panel.ask_ai.title": "Ask AI — 결정 보조",
        "panel.ask_ai.meta": "번들에 근거한 제한된 질문만 다룹니다. 일반 채팅 앱이 아닙니다.",
        "panel.ask_ai.brief_label": "지금 한 줄 브리프",
        "panel.ask_ai.shortcuts": "바로가기",
        "panel.ask_ai.placeholder": "또는 허용된 프롬프트를 직접 입력하세요(예: 결정 요약, 근거 레이어)…",
        "panel.ask_ai.submit": "보내기",
        "panel.advanced.title": "고급 — 알림·기계 상세",
        "panel.advanced.meta": "전체 알림 흐름과 필터입니다. 홈에는 짧은 미리보기만 있습니다.",
        "panel.advanced.empty": "이 조건에 맞는 알림이 없습니다. 런타임이 변화·재개 조건·운영 신호를 기록하면 나타납니다.",
        "six_q.title": "이 화면이 답해야 할 질문",
        "six_q.1": "지금 무엇이 중요한가요?",
        "six_q.2": "무엇이 바뀌었나요?",
        "six_q.3": "무엇을 추적 중인가요?",
        "six_q.4": "어떤 연구가 움직이고 있나요?",
        "six_q.5": "무엇을 결정했나요?",
        "six_q.6": "다음으로 무엇을 검토하면 좋을까요?",
        "footer.tagline": "Phase 47e 이중 언어 · DESIGN_V3",
        "journal.label_type": "유형",
        "journal.label_asset": "자산 ID",
        "journal.label_note": "메모",
        "journal.btn_log": "결정 기록",
        "advanced.filter_status": "상태",
        "advanced.filter_asset": "자산",
        "advanced.btn_refresh": "새로고침",
        "home.card.today": "오늘",
        "home.card.watchlist": "워치리스트",
        "home.card.research": "진행 중 연구",
        "home.card.alerts": "알림",
        "home.card.journal": "결정 저널",
        "home.card.ask_ai": "Ask AI 브리프",
        "home.card.replay": "리플레이 미리보기",
        "home.card.portfolio": "포트폴리오 스냅샷",
        "home.section.what_changed": "무엇이 바뀌었나",
        "home.jump.manage_alerts": "고급에서 알림 관리",
        "home.jump.open_journal": "저널 전체 열기",
        "home.jump.open_ask_ai": "Ask AI 열기",
        "home.jump.open_replay": "리플레이 전체 열기",
        "home.research.no_threads": "잡 레지스트리에 최근 행이 없습니다.",
        "spectrum.demo_title": "Today 스펙트럼 (데모 시드)",
        "spectrum.demo_meta": "MVP Sprint 1 스텁 — 시간축마다 다른 모델군·순위를 보여 줍니다. 투자 권유가 아닙니다.",
        "spectrum.as_of": "기준 시각",
        "spectrum.model_family": "활성 모델군",
        "spectrum.col_asset": "종목",
        "spectrum.col_position": "위치 (0–1)",
        "spectrum.col_tension": "밸류 긴장",
        "spectrum.col_rationale": "한 줄",
        "spectrum.col_changed": "변화",
        "spectrum.col_band": "밴드",
        "spectrum.col_message": "메시지",
        "spectrum.band_left": "낮음",
        "spectrum.band_center": "중간",
        "spectrum.band_right": "높음",
        "spectrum.h_short": "단기",
        "spectrum.h_medium": "중기",
        "spectrum.h_medium_long": "중장기",
        "spectrum.h_long": "장기",
        "spectrum.horizon_picker": "시간축",
        "spectrum.mock_tick_note": "데모: 가격 충격을 0–1 스펙트럼 축 반전으로 모사했습니다(실시간 시세 아님).",
        "spectrum.mock_mode": "가격 오버레이(모형)",
        "spectrum.mock_base": "기본 시드",
        "spectrum.mock_shock": "모의 충격(축 반전)",
        "spectrum.open_detail": "종목 상세",
        "spectrum.row_click_hint": "종목 ID를 누르면 메시지 → 정보 → 연구 순서로 열립니다.",
        "spectrum.hero_title": "Today 보드",
        "spectrum.sort_by": "정렬",
        "spectrum.sort_position_desc": "스펙트럼 위치 (높음 우선)",
        "spectrum.sort_position_asc": "스펙트럼 위치 (낮음 우선)",
        "spectrum.sort_asset_az": "종목 ID (가나다·A–Z)",
        "spectrum.watch_only": "워치리스트만 보기",
        "spectrum.watch_filter_empty": "워치리스트 ID와 겹치는 시드 행이 없습니다. 필터를 끄거나 번들의 추적 종목을 확인하세요.",
        "spectrum.expand_rationale": "한 줄 근거 펼치기",
        "spectrum.label_bundle": "번들 워치 ID 수",
        "spectrum.label_filter_tokens": "필터 토큰(별칭 포함)",
        "spectrum.label_seed_board": "시드 종목 수",
        "spectrum.label_match_on_seed": "시드와 매칭",
        "spectrum.hint_alias_active": "선택 별칭 파일이 번들 ID·심볼을 Today 시드(DEMO_*)에 연결했습니다. 워치만 필터는 이 매칭을 사용합니다.",
        "spectrum.hint_no_overlap": "번들 워치와 시드가 직접 겹치지 않고 별칭도 없습니다. data/mvp/today_spectrum_watch_aliases_v1.json 을 쓰거나 전체 보드를 보세요.",
        "panel.today_detail.title": "Today — 종목 상세",
        "panel.today_detail.meta": "MVP Sprint 4: 메시지 → 정보 → 연구 순서(시드·데모).",
        "today_detail.back": "← 홈으로",
        "today_detail.section_message": "1. 메시지",
        "today_detail.section_information": "2. 정보",
        "today_detail.section_research": "3. 연구",
        "today_detail.supporting": "찬성 신호",
        "today_detail.opposing": "반대·주의 신호",
        "today_detail.evidence": "증거 요약",
        "today_detail.data_note": "데이터 레이어",
        "today_detail.spectrum_ctx": "스펙트럼 맥락",
        "today_detail.link_replay": "리플레이 패널 열기",
        "today_detail.link_ask": "Ask AI에 붙여넣기",
        "today_detail.tension_prefix": "밸류 긴장",
        "today_detail.fallback_opposing": "단기 노이즈·유동성 이벤트는 항상 남습니다.",
        "today_detail.fallback_evidence": "시드에 전용 정보 블록이 없을 때: 스펙트럼 행의 요약만 표시합니다.",
        "today_detail.fallback_data_note": "이 빌드는 스냅샷·시연 데이터입니다.",
        "today_detail.fallback_deeper": "추가 연구 서술은 시드의 research_layer를 채우면 확장됩니다.",
        "today_detail.model_stub_prefix": "모델군 맥락(스텁):",
        "today_detail.prefill_ranked_here": "이 종목이 이 시간축에서 왜 이 위치인가요?",
        "today_detail.f_headline": "헤드라인",
        "today_detail.f_one_line": "한 줄 요약",
        "today_detail.f_why_now": "Why now",
        "today_detail.f_what_changed": "무엇이 바뀌었나",
        "today_detail.f_unproven": "아직 증명되지 않은 것",
        "today_detail.f_watch": "다음 감시",
        "today_detail.f_confidence": "신뢰 밴드",
        "today_detail.f_action": "행동 프레이밍",
        "today_detail.f_evidence": "연결 증거 요약",
        "today_detail.deeper_rationale": "심층 서술",
        "home.spectrum.card_title": "Today 스펙트럼 — 상위 메시지",
        "home.spectrum.card_meta": "단기 렌즈 기준 상위 2건. 전체 보드는 아래 데모 표에서 시간축을 바꿔 확인하세요.",
    },
    "en": {
        "shell.title": "Investment operating cockpit",
        "shell.lang_switch": "Language",
        "shell.subtitle": "Today’s priorities, watchlist, live research, decisions, and bounded AI — not an internal research viewer.",
        "shell.lang_ko": "Korean",
        "shell.lang_en": "English",
        "nav.home": "Home",
        "nav.watchlist": "Watchlist",
        "nav.research": "Research",
        "nav.replay": "Replay",
        "nav.journal": "Journal",
        "nav.ask_ai": "Ask AI",
        "nav.advanced": "Advanced",
        "nav.reload": "Reload bundle",
        "panel.home.title": "Home — today",
        "panel.home.meta": "Summaries only; raw JSON lives under Advanced.",
        "panel.home.today_hero_meta": "MVP Sprint 3: Today spectrum is the home hero. Cards below are context, watchlist, research, and journal.",
        "panel.watchlist.title": "Watchlist",
        "panel.watchlist.meta": "Names and cohorts you track, in plain language — and why they are not yet an opportunity.",
        "panel.research.title": "Research",
        "panel.research.meta": "Cohort detail, evidence, and archive context — not the Home hero.",
        "panel.journal.title": "Journal — decision log",
        "panel.journal.meta": "What you decided and why, as readable cards.",
        "panel.journal.record": "Record a decision",
        "panel.journal.empty": "No decisions yet. Log hold, watch, defer, or reopen below — entries stack as cards with replay context.",
        "panel.replay.title": "Replay — time-ordered trace",
        "panel.replay.meta": "Only what was knowable at each timestamp. **Decision quality** (then) is separate from **outcome quality** (after).",
        "panel.replay.tab_timeline": "Replay",
        "panel.replay.tab_cf": "Counterfactual Lab",
        "panel.replay.micro": "Micro-brief",
        "panel.replay.micro_empty": "Pick an event for stance, evidence, and “known then” framing.",
        "panel.replay.chart_note": "Dashed line is illustrative rhythm (not live prices). Markers derive from stance codes.",
        "panel.replay.cf_intro": "Hypothetical branches — not drawn on the replay axis. No numeric engine in this build.",
        "panel.ask_ai.title": "Ask AI — decision copilot",
        "panel.ask_ai.meta": "Bounded prompts grounded in the bundle — not a generic chat surface.",
        "panel.ask_ai.brief_label": "Copilot brief (now)",
        "panel.ask_ai.shortcuts": "Shortcuts",
        "panel.ask_ai.placeholder": "Or type a governed prompt (e.g. decision summary, information layer)…",
        "panel.ask_ai.submit": "Submit",
        "panel.advanced.title": "Advanced — alerts & machine detail",
        "panel.advanced.meta": "Full alert workflow and filters. Home shows a short preview only.",
        "panel.advanced.empty": "No alerts match this filter. They appear when the runtime records a change, reopen signal, or operator note.",
        "six_q.title": "This surface should answer",
        "six_q.1": "What matters right now?",
        "six_q.2": "What changed?",
        "six_q.3": "What am I tracking?",
        "six_q.4": "What research is in motion?",
        "six_q.5": "What did I decide?",
        "six_q.6": "What should I review next?",
        "footer.tagline": "Phase 47e bilingual · DESIGN_V3",
        "journal.label_type": "Type",
        "journal.label_asset": "Asset ID",
        "journal.label_note": "Note",
        "journal.btn_log": "Log decision",
        "advanced.filter_status": "Status",
        "advanced.filter_asset": "Asset",
        "advanced.btn_refresh": "Refresh",
        "home.card.today": "Today",
        "home.card.watchlist": "Watchlist",
        "home.card.research": "Research in progress",
        "home.card.alerts": "Alerts",
        "home.card.journal": "Decision journal",
        "home.card.ask_ai": "Ask AI brief",
        "home.card.replay": "Replay preview",
        "home.card.portfolio": "Portfolio snapshot",
        "home.section.what_changed": "What changed",
        "home.jump.manage_alerts": "Manage alerts in Advanced",
        "home.jump.open_journal": "Open full Journal",
        "home.jump.open_ask_ai": "Open Ask AI",
        "home.jump.open_replay": "Open full Replay",
        "home.research.no_threads": "No recent thread rows in the job registry.",
        "spectrum.demo_title": "Today spectrum (demo seed)",
        "spectrum.demo_meta": "MVP Sprint 1 stub — different model families per horizon (not investment advice).",
        "spectrum.as_of": "As of",
        "spectrum.model_family": "Active model family",
        "spectrum.col_asset": "Asset",
        "spectrum.col_position": "Position (0–1)",
        "spectrum.col_tension": "Valuation tension",
        "spectrum.col_rationale": "One line",
        "spectrum.col_changed": "What changed",
        "spectrum.col_band": "Band",
        "spectrum.col_message": "Message",
        "spectrum.band_left": "Low",
        "spectrum.band_center": "Mid",
        "spectrum.band_right": "High",
        "spectrum.h_short": "Short-term",
        "spectrum.h_medium": "Medium-term",
        "spectrum.h_medium_long": "Medium-long",
        "spectrum.h_long": "Long-term",
        "spectrum.horizon_picker": "Horizon",
        "spectrum.mock_tick_note": "Demo: price shock simulated by inverting the 0–1 spectrum axis (not live quotes).",
        "spectrum.mock_mode": "Price overlay (mock)",
        "spectrum.mock_base": "Base seed",
        "spectrum.mock_shock": "Mock shock (axis invert)",
        "spectrum.open_detail": "Open detail",
        "spectrum.row_click_hint": "Click an asset id to open Message → Information → Research.",
        "spectrum.hero_title": "Today board",
        "spectrum.sort_by": "Sort",
        "spectrum.sort_position_desc": "Spectrum position (high first)",
        "spectrum.sort_position_asc": "Spectrum position (low first)",
        "spectrum.sort_asset_az": "Asset id (A–Z)",
        "spectrum.watch_only": "Watchlist only",
        "spectrum.watch_filter_empty": "No seed rows match your watchlist ids. Turn the filter off or check bundle-tracked assets.",
        "spectrum.expand_rationale": "Show rationale line",
        "spectrum.label_bundle": "Bundle watch id count",
        "spectrum.label_filter_tokens": "Filter tokens (incl. aliases)",
        "spectrum.label_seed_board": "Seed asset count",
        "spectrum.label_match_on_seed": "Matches on seed board",
        "spectrum.hint_alias_active": "Optional alias file maps bundle ids/symbols to Today seed (DEMO_*). Watch-only filter uses this mapping.",
        "spectrum.hint_no_overlap": "No bundle↔seed overlap and no aliases. Add data/mvp/today_spectrum_watch_aliases_v1.json or view the full board.",
        "panel.today_detail.title": "Today — object detail",
        "panel.today_detail.meta": "MVP Sprint 4: Message → Information → Research (seed demo).",
        "today_detail.back": "← Back to Home",
        "today_detail.section_message": "1. Message",
        "today_detail.section_information": "2. Information",
        "today_detail.section_research": "3. Research",
        "today_detail.supporting": "Supporting signals",
        "today_detail.opposing": "Opposing / caution signals",
        "today_detail.evidence": "Evidence summary",
        "today_detail.data_note": "Data layer",
        "today_detail.spectrum_ctx": "Spectrum context",
        "today_detail.link_replay": "Open Replay panel",
        "today_detail.link_ask": "Paste into Ask AI",
        "today_detail.tension_prefix": "Valuation tension",
        "today_detail.fallback_opposing": "Short-horizon noise and liquidity events always remain.",
        "today_detail.fallback_evidence": "When the seed has no information_layer: showing spectrum row summary only.",
        "today_detail.fallback_data_note": "This build uses snapshot / demo data.",
        "today_detail.fallback_deeper": "Extend seed research_layer for richer narrative.",
        "today_detail.model_stub_prefix": "Model context (stub):",
        "today_detail.prefill_ranked_here": "Why is this asset placed here on this horizon?",
        "today_detail.f_headline": "Headline",
        "today_detail.f_one_line": "One-line take",
        "today_detail.f_why_now": "Why now",
        "today_detail.f_what_changed": "What changed",
        "today_detail.f_unproven": "What remains unproven",
        "today_detail.f_watch": "What to watch",
        "today_detail.f_confidence": "Confidence band",
        "today_detail.f_action": "Action frame",
        "today_detail.f_evidence": "Linked evidence summary",
        "today_detail.deeper_rationale": "Deeper rationale",
        "home.spectrum.card_title": "Today spectrum — top messages",
        "home.spectrum.card_meta": "Short lens, top two rows. Use the demo table below to change horizon.",
    },
}

SECTION_LABELS: dict[str, dict[str, list[dict[str, str]]]] = {
    "ko": {
        "tabs": [
            {"id": "brief", "label": "브리프", "maps_internal": "decision + message (요약)"},
            {"id": "why_now", "label": "왜 지금", "maps_internal": "메시지·헤드라인 / 변경"},
            {"id": "what_could_change", "label": "무엇이 바뀔 수 있나", "maps_internal": "주시점 + 클로즈아웃 카드"},
            {"id": "evidence", "label": "근거", "maps_internal": "정보 + 연구 레이어"},
            {"id": "history", "label": "기록", "maps_internal": "알림 + 결정(링크)"},
            {"id": "ask_ai", "label": "Ask AI", "maps_internal": "거버넌스 대화"},
            {"id": "advanced", "label": "고급", "maps_internal": "출처 + 클로즈 + 원시 JSON"},
        ]
    },
    "en": {
        "tabs": [
            {"id": "brief", "label": "Brief", "maps_internal": "decision + message (summary)"},
            {"id": "why_now", "label": "Why now", "maps_internal": "message + headline / what changed"},
            {"id": "what_could_change", "label": "What could change", "maps_internal": "watchpoints + closeout card"},
            {"id": "evidence", "label": "Evidence", "maps_internal": "information + research layers"},
            {"id": "history", "label": "History", "maps_internal": "alerts + decisions (links)"},
            {"id": "ask_ai", "label": "Ask AI", "maps_internal": "governed conversation"},
            {"id": "advanced", "label": "Advanced", "maps_internal": "provenance + closeout + raw JSON"},
        ]
    },
}


HOME_FEED: dict[str, dict[str, str]] = {
    "ko": {
        "today.open_body": "열린 알림이 {count}건 있습니다. 가장 최근: {aclass} — {summary}",
        "today.stance_label": "입장",
        "today.evidence_label": "근거",
        "today.evidence_fallback_short": "연구를 참고하세요.",
        "watch.symbols_label": "심볼",
        "closed.research_tab_note": "전체 코호트 카드·근거·아카이브 맥락은 연구 탭에 있습니다.",
        "today.alert_title": "알림에 주목",
        "today.loadout": "현재 로드아웃",
        "today.no_opportunity": "지금은 ‘기회’ 화면이 아닙니다",
        "today.body.fixture": "지금 번들은 **종료된 연구 기록**입니다. 감사·리플레이에는 유용하지만, 매수·매도 제안이 아닙니다. **워치리스트**에서 추적 항목, **연구**에서 진행 상황, **알림**에서 신호를 확인하세요.",
        "watch.why_cohort": "거버넌스된 코호트입니다 — 입장은 근거 한계를 반영할 뿐 과장이 아닙니다.",
        "watch.why_single": "단일 객체 로드아웃입니다. 향후 워치리스트 인제스트로 범위를 넓힐 수 있습니다.",
        "watch.empty_title": "워치리스트가 얇습니다",
        "watch.empty_why": "지금은 하나의 권위 코호트 객체를 불러옵니다.",
        "watch.empty_when": "거버넌스 하에 자산이나 외부 워치 이벤트가 등록되면 채워집니다.",
        "research.empty_title": "최근 작업 행이 없습니다",
        "research.empty_why": "이 머신에 연구 잡 레지스트리가 비어 있거나 아직 기록되지 않았습니다.",
        "research.empty_when": "Phase 48/51 사이클이 돌면 `research_job_registry_v1.json`에 쌓입니다.",
        "research.checkpoint": "다음: 번들 리로드나 외부 트리거가 새로운 경계 사이클을 넣을 수 있습니다.",
        "research.sub_default": "요약이 아직 없습니다.",
        "alerts.empty_title": "알림 없음",
        "alerts.empty_why": "현재 표면과 맞는 알림 원장이 비어 있습니다.",
        "alerts.empty_when": "런타임 신호·재개 조건·Phase 48 출력이 쌓이면 나타납니다.",
        "journal.empty_title": "저널이 비었습니다",
        "journal.empty_why": "결정 추적 원장에 기록이 없습니다.",
        "journal.empty_when": "저널에서 결정을 남기면 채워집니다.",
        "journal.replay_hint": "이 결정 시점의 타임라인은 리플레이에서 엽니다.",
        "replay.preview.head.decision": "다시 보기 좋은 최근 결정",
        "replay.preview.head.default": "리플레이 — 시간 순 추적",
        "replay.preview.no_decision": "아직 기록된 결정이 없어도, 번들 타임라인과 요약 브리프는 리플레이에서 볼 수 있습니다.",
        "replay.preview.axis": "전체 패널: 참고용 기준선과 입장 마커; 이벤트를 고르면 ‘그때까지 알려진 것’이 정리됩니다.",
        "replay.preview.empty_title": "결정 티저가 없습니다",
        "replay.preview.empty_why": "저널이 비어 있어 특정 결정 대신 리플레이 역할을 안내합니다.",
        "replay.preview.empty_when": "저널에 결정이 쌓이면 헤드라인이 채워지고, 타임라인은 항상 리플레이에 있습니다.",
        "portfolio.stub": "포트폴리오 귀속·포지션은 아직 이 화면에 없습니다 — 후속 슬라이스용으로 비워 두었습니다.",
        "copilot.no_alerts": "열린 알림은 없습니다 — 연구 활동을 보거나 아래 숏컷을 쓰세요.",
        "copilot.has_alerts": "열린 항목을 검토해야 할 수 있습니다.",
        "action.review": "위 내용을 검토하거나 조치가 필요할 수 있습니다.",
        "action.calm": "긴급 콕핏 조치는 이 로드아웃에서 필수는 아닙니다 — 아래 블록을 살펴보세요.",
    },
    "en": {
        "today.open_body": "You have {count} open alert(s). The most recent: {aclass} — {summary}",
        "today.stance_label": "Stance",
        "today.evidence_label": "Evidence",
        "today.evidence_fallback_short": "See Research.",
        "watch.symbols_label": "Symbols",
        "closed.research_tab_note": "Full cohort cards, evidence, and archive-style context live under Research.",
        "today.alert_title": "Attention on alerts",
        "today.loadout": "Current loadout",
        "today.no_opportunity": "No live opportunity headline",
        "today.body.fixture": "This bundle is a **closed research record** — useful for audit and replay, not a buy/sell call. Use **Watchlist** for tracking, **Research in progress** for activity, and **Alerts** for signals.",
        "watch.why_cohort": "Governed cohort in this bundle — stance reflects evidence limits, not hype.",
        "watch.why_single": "Single-object loadout; breadth can grow with future watchlist ingest.",
        "watch.empty_title": "Watchlist is thin",
        "watch.empty_why": "This build loads one authoritative cohort object.",
        "watch.empty_when": "More assets or governed watch events will populate this block.",
        "research.empty_title": "No recent job rows",
        "research.empty_why": "The research job registry is empty or not populated on this machine.",
        "research.empty_when": "Phase 48/51 cycles write to `research_job_registry_v1.json`.",
        "research.checkpoint": "Next: bundle reload or an external trigger may enqueue a new bounded cycle.",
        "research.sub_default": "No summary yet.",
        "alerts.empty_title": "No alerts",
        "alerts.empty_why": "Nothing in the alert ledger matches this surface.",
        "alerts.empty_when": "Runtime signals, reopen rules, or Phase 48 outputs will append here.",
        "journal.empty_title": "Journal is empty",
        "journal.empty_why": "No decisions logged in the trace ledger.",
        "journal.empty_when": "Record a decision under Journal to populate this section.",
        "journal.replay_hint": "Open Replay for the timeline around this decision.",
        "replay.preview.head.decision": "Last decision worth revisiting",
        "replay.preview.head.default": "Replay — time-ordered trace",
        "replay.preview.no_decision": "No logged decisions yet — Replay still shows the bundle timeline and micro-briefs.",
        "replay.preview.axis": "Full panel: illustrative reference plus stance markers; pick events for “known then”.",
        "replay.preview.empty_title": "No journal row for a decision teaser",
        "replay.preview.empty_why": "Journal is empty, so we highlight Replay instead of a specific decision.",
        "replay.preview.empty_when": "Logging decisions fills the headline; the timeline always lives in Replay.",
        "portfolio.stub": "Portfolio attribution and positions are not shown here yet — reserved for a later slice.",
        "copilot.no_alerts": "No open alerts — scan Research activity or use a shortcut below.",
        "copilot.has_alerts": "Open items may need your review.",
        "action.review": "Review or action may be warranted from the context above.",
        "action.calm": "No urgent cockpit action implied — scan the blocks below.",
    },
}


GOVERNED_SHORTCUTS: dict[str, list[dict[str, str]]] = {
    "ko": [
        {"label": "짧게 설명해 주세요", "text": "decision summary"},
        {"label": "핵심 근거를 보여 주세요", "text": "information layer"},
        {"label": "왜 종료 상태인가요?", "text": "why is this closed"},
        {"label": "무엇이 바뀌었나요?", "text": "what changed"},
        {"label": "무엇이 바뀔 수 있나요?", "text": "what could change"},
        {"label": "연구 이력을 보여 주세요", "text": "research layer"},
        {"label": "출처 맥락(프로비넌스)", "text": "show provenance"},
    ],
    "en": [
        {"label": "Explain this briefly", "text": "decision summary"},
        {"label": "Show key evidence", "text": "information layer"},
        {"label": "Why is this closed?", "text": "why is this closed"},
        {"label": "What changed?", "text": "what changed"},
        {"label": "What could change?", "text": "what could change"},
        {"label": "Show research history", "text": "research layer"},
        {"label": "Log context (provenance)", "text": "show provenance"},
    ],
}


ACTION_FRAMING: dict[str, dict[str, str]] = {
    "ko": {
        "closed_reopen": "재개 요청 검토 — 새로 명명된 출처 경로가 있을 때만",
        "closed_hold": "연구 종료 — 새 근거나 명명된 출처가 있을 때까지 유지",
        "keep_watching": "계속 관찰",
        "defer": "조치 없음 — 보류",
        "review": "새 근거 검토",
    },
    "en": {
        "closed_reopen": "Consider reopen request — only with a new named source path",
        "closed_hold": "Research closed — hold until new evidence or named source",
        "keep_watching": "Keep watching",
        "defer": "No action — deferred",
        "review": "Review new evidence",
    },
}


SECTION_PAYLOAD: dict[str, dict[str, str]] = {
    "ko": {
        "why_now.intro": "이 객체는 거버넌스된 콕핏 로드아웃의 일부이며 정의된 연구 입장을 갖고 있습니다. 아래 최근 변경은 최신 권위 번들에서 온 것입니다.",
        "history.intro": "알림과 기록된 결정은 상단 고급 탭과 저널(Phase 47d 셸)에 있습니다.",
        "history.link_advanced": "알림 열기(고급)",
        "history.link_journal": "저널 열기",
        "ask_ai.intro": "아래 빠른 프롬프트를 사용하세요 — 응답은 번들에 근거한 거버넌스 대화이며 일반 채팅이 아닙니다.",
        "brief.label_stance": "현재 입장(일러서)",
        "brief.label_saying": "시스템이 말하는 것",
        "brief.label_action": "지금 할 일",
        "brief.label_evidence": "근거 상태",
        "brief.evidence_fallback": "근거 탭 참고",
    },
    "en": {
        "why_now.intro": "This object is on screen because it is part of your governed cockpit loadout and has a defined research stance. Recent changes below are from the latest authoritative bundle.",
        "history.intro": "Alerts and recorded decisions live under top-level Advanced and Journal (Phase 47d shell).",
        "history.link_advanced": "Open Alerts (Advanced)",
        "history.link_journal": "Open Journal",
        "ask_ai.intro": "Use quick prompts below — responses are governed and grounded in the bundle (not generic chat).",
        "brief.label_stance": "Current stance (plain)",
        "brief.label_saying": "What the system is saying",
        "brief.label_action": "What to do now",
        "brief.label_evidence": "Evidence state",
        "brief.evidence_fallback": "See Evidence tab",
    },
}


ASK_AI_CONTRACT: dict[str, list[dict[str, str]]] = {
    "ko": [
        {"id": "matters_now", "label": "지금 가장 중요한 건 무엇인가요?", "prompt_text": "decision summary"},
        {"id": "what_changed", "label": "무엇이 바뀌었나요?", "prompt_text": "what changed"},
        {"id": "active_research", "label": "진행 중 연구를 보여 주세요", "prompt_text": "research layer"},
        {"id": "review_next", "label": "다음에 무엇을 검토하면 좋을까요?", "prompt_text": "what remains unproven"},
        {"id": "last_decisions", "label": "최근 결정을 보여 주세요", "prompt_text": "decision summary"},
        {"id": "open_replay", "label": "이 항목을 리플레이로 열기", "prompt_text": "what changed", "opens_panel": "replay"},
    ],
    "en": [
        {"id": "matters_now", "label": "What matters now?", "prompt_text": "decision summary"},
        {"id": "what_changed", "label": "What changed?", "prompt_text": "what changed"},
        {"id": "active_research", "label": "Show my active research", "prompt_text": "research layer"},
        {"id": "review_next", "label": "What should I review next?", "prompt_text": "what remains unproven"},
        {"id": "last_decisions", "label": "Show my last decisions", "prompt_text": "decision summary"},
        {"id": "open_replay", "label": "Open Replay for this item", "prompt_text": "what changed", "opens_panel": "replay"},
    ],
}


def normalize_lang(lang: str | None) -> str:
    if not lang:
        return "ko"
    lg = str(lang).strip().lower()[:8]
    return lg if lg in SUPPORTED_LANGS else "ko"


def t(lang: str | None, key: str) -> str:
    lg = normalize_lang(lang)
    return (
        SHELL.get(lg, {}).get(key)
        or HOME_FEED.get(lg, {}).get(key)
        or SECTION_PAYLOAD.get(lg, {}).get(key)
        or SHELL["en"].get(key)
        or HOME_FEED["en"].get(key)
        or SECTION_PAYLOAD["en"].get(key)
        or SHELL["ko"].get(key)
        or HOME_FEED["ko"].get(key)
        or SECTION_PAYLOAD["ko"].get(key)
        or key
    )


def governed_prompt_shortcuts_localized(lang: str | None) -> list[dict[str, str]]:
    lg = normalize_lang(lang)
    return [dict(x) for x in GOVERNED_SHORTCUTS.get(lg, GOVERNED_SHORTCUTS["en"])]


def ask_ai_brief_contract_localized(lang: str | None) -> list[dict[str, str]]:
    lg = normalize_lang(lang)
    return [dict(x) for x in ASK_AI_CONTRACT.get(lg, ASK_AI_CONTRACT["en"])]


def translate_status_token(lang: str | None, token: str | None) -> str:
    if not token:
        return ""
    lg = normalize_lang(lang)
    table = STATUS_TRANSLATIONS_KO if lg == "ko" else STATUS_TRANSLATIONS_EN
    s = str(token).strip()
    if s in table:
        return table[s]
    low = s.lower()
    for k, v in table.items():
        if k.lower() in low:
            return v
    return s


def object_kind_label_localized(lang: str | None, kind: str) -> str:
    lg = normalize_lang(lang)
    return OBJECT_KIND_LABELS.get(lg, {}).get(kind) or OBJECT_KIND_LABELS["en"].get(kind) or kind


def object_kind_hint_localized(lang: str | None, kind: str) -> str:
    lg = normalize_lang(lang)
    return OBJECT_KIND_HINTS.get(lg, {}).get(kind) or OBJECT_KIND_HINTS["en"].get(kind, "")


def shell_nav_rows(lang: str | None) -> list[dict[str, str]]:
    """Same ids as SHELL_NAVIGATION_47D; labels localized."""
    lg = normalize_lang(lang)
    ids = ["home", "watchlist", "research", "replay", "journal", "ask_ai", "advanced"]
    questions_ko = [
        "지금 화면 전체에서 무엇이 핵심인가요?",
        "무엇을 추적 중이며 어떻게 움직이나요?",
        "무엇이 진행 중이고 아카이브 맥락은 무엇인가요?",
        "그때 알 수 있었던 것은 무엇인가요?",
        "무엇을 결정했고 왜 그랬나요?",
        "범위가 정해진 보조 — 무엇을 물을 수 있나요?",
        "알림·원시 참고는 여기서 다룹니다.",
    ]
    questions_en = [
        "What matters now across my surface?",
        "What am I tracking and how is it moving?",
        "What is being worked on and archived context?",
        "What happened, knowable then?",
        "What did I decide and why?",
        "Copilot — bounded, bundle-grounded",
        "Alerts manager, raw references",
    ]
    qs = questions_ko if lg == "ko" else questions_en
    out = []
    for i, pid in enumerate(ids):
        out.append(
            {
                "id": pid,
                "label": t(lg, f"nav.{pid}"),
                "user_question": qs[i] if i < len(qs) else "",
            }
        )
    return out


def export_shell_locale_dict(lang: str | None) -> dict[str, str]:
    """Flat map for GET /api/locale — shell + home-feed + section helper strings for the client."""
    lg = normalize_lang(lang)
    out: dict[str, str] = {}
    out.update(SHELL.get(lg, {}))
    out.update(HOME_FEED.get(lg, {}))
    out.update(SECTION_PAYLOAD.get(lg, {}))
    return out


def cockpit_health_public_text(lang: str | None, raw: dict[str, Any]) -> tuple[str, str, list[str]]:
    """Headline, subtext, plain_lines for runtime health card."""
    lg = normalize_lang(lang)
    st = raw.get("health_status") or "unknown"
    cp = raw.get("control_plane_excerpt") or {}
    enabled = cp.get("enabled")
    maint = cp.get("maintenance_mode")

    if lg == "ko":
        if not enabled:
            headline, sub = "연구 런타임이 꺼져 있습니다.", "새 사이클은 시작되지 않습니다. 제어 평면에서 켤 수 있습니다."
        elif maint:
            headline, sub = "점검 모드입니다.", "트리거는 기록되나 실행은 제한될 수 있습니다."
        elif st == "degraded":
            headline, sub = "동작 중이나 일부 사이클이 건너뛰어졌습니다.", "타이밍·리스·윈도 한도를 확인하세요."
        else:
            headline, sub = "상태가 양호해 보입니다.", "감사 요약과 외부 적재는 아래 한눈에 보입니다."
    else:
        if not enabled:
            headline, sub = "Research runtime is off.", "New cycles will not start. Enable from the control plane."
        elif maint:
            headline, sub = "Maintenance mode.", "Triggers may log while runs are constrained."
        elif st == "degraded":
            headline, sub = "Running, but some cycles were skipped.", "Check timing, lease, and window limits."
        else:
            headline, sub = "Runtime looks healthy.", "Audit tail and external ingest are summarized below."

    last_c = raw.get("last_cycle_audit_excerpt") or {}
    ext = raw.get("external_ingest_counts") or {}
    if lg == "ko":
        lines = [
            f"마지막 감사: {last_c.get('timestamp') or '—'}",
            f"사이클 건너뜀: {'예' if last_c.get('skipped') else '아니오'}",
            f"외부 적재: 총 {ext.get('total_entries', 0)} · 대기 {ext.get('accepted_pending', 0)} · 소비 {ext.get('consumed', 0)} · 거절 {ext.get('rejected', 0)} · 중복 {ext.get('deduped', 0)}",
        ]
    else:
        lines = [
            f"Last audit: {last_c.get('timestamp') or '—'}",
            f"Last cycle skipped: {'yes' if last_c.get('skipped') else 'no'}",
            f"External ingest: total {ext.get('total_entries', 0)} · pending {ext.get('accepted_pending', 0)} · consumed {ext.get('consumed', 0)} · rejected {ext.get('rejected', 0)} · deduped {ext.get('deduped', 0)}",
        ]

    la = raw.get("last_accepted_trigger")
    if la:
        if lg == "ko":
            lines.append(f"최근 승인: {la.get('normalized_trigger_type')} @ {str(la.get('received_at') or '')[:19]}")
        else:
            lines.append(f"Last accepted: {la.get('normalized_trigger_type')} @ {str(la.get('received_at') or '')[:19]}")
    lr = raw.get("last_rejected_trigger")
    if lr:
        if lg == "ko":
            lines.append(f"최근 거절: {lr.get('reason')} ({lr.get('raw_event_type')})")
        else:
            lines.append(f"Last rejected: {lr.get('reason')} ({lr.get('raw_event_type')})")

    ext52 = raw.get("external_source_activity_v52")
    if ext52:
        rp = ext52.get("registry_path") or ""
        if lg == "ko":
            lines.append(f"외부 소스: 대기 큐 {ext52.get('queue_depth_pending', 0)}건" + (f" · {rp}" if rp else ""))
        else:
            lines.append(f"External sources: queue pending {ext52.get('queue_depth_pending', 0)}" + (f" · {rp}" if rp else ""))
        for ps in (ext52.get("sources") or [])[:8]:
            oc = ps.get("outcome_counts") or {}
            if oc:
                lines.append(f"  · {ps.get('source_id')}: {oc}")
            kid = ps.get("active_signing_key_id")
            if kid:
                lines.append(f"  · signing key: {kid}")

    p53 = raw.get("external_ingress_phase53") or {}
    if p53:
        if lg == "ko":
            lines.append(
                f"서명 인제스트: 구성됨={p53.get('signed_ingress_configured')} · 데드레터 {p53.get('dead_letter_total_entries', 0)} · 가드 {p53.get('replay_guard_active_entries', 0)}"
            )
        else:
            lines.append(
                f"Signed ingress: configured={p53.get('signed_ingress_configured')} · dead-letter {p53.get('dead_letter_total_entries', 0)} · guard {p53.get('replay_guard_active_entries', 0)}"
            )

    leg = raw.get("legacy_ingest_status") or {}
    if leg:
        if lg == "ko":
            lines.append("무인증 적재: " + ("허용(내부 전용)" if leg.get("allowed") else "비활성 — authenticated 사용"))
        else:
            lines.append("Legacy unauthenticated ingest: " + ("on (internal only)" if leg.get("allowed") else "off — use authenticated"))

    return headline, sub, lines


def phase47f_recommend() -> dict[str, Any]:
    return {
        "phase47f_recommendation": "per_asset_narrative_strip_and_digest_reading_modes_v1",
        "focus": "Per-asset story strip on Home, optional “plain / standard / deep” reading depth for long research objects — still governed, no substrate expansion.",
    }
