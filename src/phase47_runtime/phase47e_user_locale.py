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
        "panel.research.sandbox_title": "맞춤형 리서치 샌드박스 v1",
        "panel.research.sandbox_meta": "가설·자산·지평·모드를 정해 번들·Today 시드와 결정적으로 교차합니다. 범용 채팅이 아닙니다.",
        "panel.research.deferred_empty": "Today 상세에서 종목을 연 뒤(또는 샌드박스에 자산 ID를 넣은 뒤) 다시 이 탭으로 오면, 메시지→Registry→정보→연구 계약이 읽기 전용으로 채워집니다.",
        "panel.research.deferred_title": "지연 연구 컨텍스트 (Today 상세와 동일 계약)",
        "panel.research.deferred_meta": "추가 텔레메트리 없이 Stage 3 최소 표면입니다.",
        "research.ask_chips_hint": "거버닝 Ask AI",
        "research.ask_chip_why_now": "Why now",
        "research.ask_chip_what_changed": "What changed",
        "research.ask_chip_what_to_watch": "What to watch",
        "sandbox.strip_from_today": "Today 상세에서 가져온 컨텍스트",
        "sandbox.label_hypothesis": "가설 또는 질문",
        "sandbox.label_asset": "자산 ID (선택)",
        "sandbox.label_horizon": "지평",
        "sandbox.label_pit_mode": "시점 모드",
        "sandbox.pit_snapshot": "현재 스냅샷",
        "sandbox.pit_stub": "PIT 스텁 (정직한 자리표시자)",
        "sandbox.label_mock_tick": "데모 가격 오버레이",
        "sandbox.btn_run": "경계 분석 실행",
        "sandbox.result_title": "구조화 결과",
        "sandbox.scan_title": "지평별 스캔 (동일 자산)",
        "sandbox.col_horizon": "지평",
        "sandbox.col_band": "밴드",
        "sandbox.col_pos": "위치",
        "sandbox.col_headline": "헤드라인",
        "sandbox.bullet_hypothesis_prefix": "가설/질문:",
        "sandbox.bullet_selected_lens": "선택 지평 ({hz_label}): 스펙트럼 밴드 {band}.",
        "sandbox.bullet_headline_prefix": "메시지 헤드라인:",
        "sandbox.bullet_asset_not_on_board": "자산 {asset_id}는 이 지평의 시드 보드에 없습니다. 다른 지평만 스캔합니다.",
        "sandbox.bullet_cohort_scope": "범위: 번들 기준 코호트(개별 자산 ID 없음).",
        "sandbox.bullet_decision_card_prefix": "결정 카드 요지:",
        "sandbox.bullet_pitch_prefix": "대표 피치 스니펫:",
        "sandbox.pit_stub_note": "PIT 스텁: MVP에서는 동일 스냅샷·시드와만 교차합니다. 과거 시점 재생은 리플레이·후속 PIT 연동 예정입니다.",
        "sandbox.disclaimer": "출력은 LLM이 아니라 번들·Today 시드에서 결정적으로 조합한 요약입니다. 투자 권유가 아닙니다.",
        "sandbox.action_open_today_detail": "Today 상세로",
        "sandbox.action_open_replay": "리플레이",
        "sandbox.action_open_ask_ai": "Ask AI",
        "sandbox.save_label": "이 실행을 ledger에 저장",
        "sandbox.recent_title": "최근 저장된 실행",
        "sandbox.empty_runs": "아직 저장된 샌드박스 실행이 없습니다.",
        "sandbox.prefill_stub": "이 객체의 단기 전제를 어떻게 반증·좁힐 수 있는가?",
        "sandbox.persisted_ok": "ledger에 저장됨",
        "sandbox.persisted_fail": "ledger 저장 실패(권한·경로 등)",
        "sandbox.ledger_readonly": "ledger에서 연 연구 객체(읽기 전용)",
        "sandbox.apply_to_form": "폼에 반영",
        "sandbox.close_ledger_detail": "닫기",
        "sandbox.open_replay": "리플레이",
        "replay.sandbox_context_hint": "샌드박스 실행 맥락:",
        "replay_aging.title": "어떻게 숙성됐나 (요약)",
        "replay_aging.line_decisions": "저널 결정 기록 {n}건.",
        "replay_aging.no_decisions": "이 자산 ID의 저널 기록은 없습니다.",
        "replay_aging.line_sandbox": "저장된 샌드박스 실행 {n}건.",
        "replay_aging.no_sandbox": "이 자산의 샌드박스 ledger 기록은 없습니다.",
        "replay_aging.line_horizons": "Today 시드에서 지평 {n}개 스냅.",
        "replay_aging.not_on_seed": "Today 시드 보드에 이 자산이 없습니다.",
        "replay_aging.disclaimer": "가격 경로·수치 숙성 엔진은 MVP 범위 밖입니다. 표시는 결정 로그·샌드박스·스펙트럼 시드 결합입니다.",
        "replay.snapshot.title": "Today 메시지 스냅샷",
        "replay.snapshot.family": "당시 활성 모델군",
        "replay.snapshot.headline": "헤드라인 스냅",
        "replay.registry_surface_block": "Registry 표면(읽기 전용)",
        "replay.timeline.join_title": "Today 스펙트럼과 조인된 lineage",
        "replay.timeline.join_intro": "선택한 자산의 Today 스펙트럼 행과 동일한 registry·메시지 스냅샷 포인터입니다.",
        "replay.timeline.pointer": "Replay lineage pointer",
        "replay.timeline.snapshot_id": "Message snapshot id",
        "replay.timeline.registry": "Registry 항목",
        "replay.timeline.artifact": "Artifact",
        "replay.cf.intro_templates": "아래는 반사실 검토용 템플릿입니다. 수치는 시연용 스텁이며 실제 가격 경로가 아닙니다.",
        "replay.cf.preview": "스텁 미리보기",
        "replay.cf.disclaimer": "가설 분기 — 리플레이 타임라인에 그려지지 않습니다. 확정적 수익·손실을 암시하지 않습니다.",
        "replay.cf.label_watch_only": "워치만 분기",
        "replay.cf.sum_watch_only": "배분 변경 없이 관찰만 했다면 스펙트럼 위치는 동일하게 둡니다.",
        "replay.cf.narr_watch_only": "의사결정은 ‘기록’에 남고, 스펙트럼 축은 동일합니다. 이후 결과는 별도 프레임에서 봅니다.",
        "replay.cf.label_evidence_softens": "핵심 근거가 약해진 경우",
        "replay.cf.sum_evidence_softens": "대표 근거 한 줄이 약해졌다고 가정하고 축을 약간 하방으로 이동합니다.",
        "replay.cf.narr_evidence_softens": "근거 강도가 낮아지면 같은 가격대라도 상대 스펙트럼 위치는 방어적으로 읽힐 수 있습니다.",
        "replay.cf.label_horizon_stretch": "더 긴 지평으로 읽힌 경우",
        "replay.cf.sum_horizon_stretch": "동일 데이터를 더 긴 렌즈로 본다고 가정해 축을 상방으로 이동합니다.",
        "replay.cf.narr_horizon_stretch": "시간축이 길어지면 성장·주기 서사가 스펙트럼에 더 실립니다(시연용 이동).",
        "replay.cf.label_allocation_smaller": "체크 규모만 줄인 경우",
        "replay.cf.sum_allocation_smaller": "체감 리스크만 줄였다고 가정하고 축을 소폭 하방으로 이동합니다.",
        "replay.cf.narr_allocation_smaller": "집행이 아니라 관찰 규모만 줄이면 심리적 압박이 달라져 같은 뉴스도 다르게 읽힐 수 있습니다.",
        "replay_aging.horizons": "지평별 스펙트럼 (현재 스냅샷)",
        "replay_aging.decisions": "저널 (최근)",
        "replay_aging.sandbox": "샌드박스 (최근)",
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
        "replay.no_events_for_asset": "이 종목 ID와 일치하는 asset_id를 가진 타임라인 이벤트가 없습니다. 저널·알림 또는 번들 primary asset과 비교해 보세요.",
        "replay.asset_badge": "자산",
        "panel.replay.chart_note": "점선은 참고용 리듬(실시간 시세 아님). 마커는 입장 코드에서 만든 지표입니다.",
        "panel.replay.cf_intro": "가설 분기 — 리플레이 축에 그리지 않습니다. 이 빌드에는 수치 엔진이 없습니다.",
        "panel.ask_ai.title": "Ask AI — 결정 보조",
        "panel.ask_ai.meta": "번들에 근거한 제한된 질문만 다룹니다. 일반 채팅 앱이 아닙니다.",
        "panel.ask_ai.brief_label": "지금 한 줄 브리프",
        "panel.ask_ai.shortcuts": "바로가기",
        "panel.ask_ai.placeholder": "또는 허용된 프롬프트를 직접 입력하세요(예: 결정 요약, 근거 레이어)…",
        "panel.ask_ai.submit": "보내기",
        "panel.ask_ai.context_label": "Today / 상세 컨텍스트",
        "panel.ask_ai.context_clear": "컨텍스트 지우기",
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
        "journal.lineage_bind_hint": "Today 상세에서 연 컨텍스트가 있습니다. 자산 ID가 같으면 message snapshot·registry lineage가 결정 기록에 함께 저장되어 Replay 타임라인과 맞습니다.",
        "journal.card_lineage": "Replay lineage (저널에 저장됨)",
        "journal.card_snapshot": "Message snapshot id",
        "journal.card_lineage_ptr": "Lineage pointer",
        "journal.card_message_line": "연결된 메시지 한 줄",
        "journal.open_replay": "이 결정으로 Replay 열기",
        "journal.btn_log": "결정 기록",
        "replay.now_then.title": "그때(Today 조인) vs 지금(권위 번들)",
        "replay.now_then.body_then": "그때: 스펙트럼에 묶인 활성 모델군「{family}」. 메시지 스냅샷 id「{snapshot_id}」는 저널·타임라인이 같은 키로 조인합니다.",
        "replay.now_then.body_now": "지금: 권위 번들 복기 프레임 — 입장 코드「{stance}」. 헤드라인 발췌: {headline}",
        "replay.now_then.disclaimer": "미래 수익·최적 타이밍을 보장하지 않습니다. outcome은 별도 평가 프레임입니다.",
        "home.demo.pack_title": "투자자 데모 — 동결 스냅샷 팩",
        "home.demo.pack_intro": "같은 시드·번들·스냅샷 저장소를 가리키는 매니페스트입니다. 번들 리로드와 mock_price_tick 0/1로 재현합니다.",
        "home.demo.investor_route": "권장 데모 순서",
        "home.demo.price_overlay": "가격 오버레이(데모)",
        "demo.route.home_today": "홈에서 Today 스펙트럼·시간축 확인",
        "demo.route.object_detail": "종목 상세 — 메시지 → 정보 → 연구",
        "demo.route.journal_log": "저널에서 결정 기록(가능하면 Today 상세 직후)",
        "demo.route.replay_timeline": "Replay 타임라인·그때/지금 프레임",
        "demo.route.counterfactual": "반사실 검토실 — 템플릿 스텁 미리보기",
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
        "spectrum.quintile_extreme_underpriced": "극단 저평가",
        "spectrum.quintile_underpriced": "저평가",
        "spectrum.quintile_neutral": "중립",
        "spectrum.quintile_overpriced": "고평가",
        "spectrum.quintile_extreme_overpriced": "극단 고평가",
        "spectrum.rank_movement_up": "순위↑",
        "spectrum.rank_movement_down": "순위↓",
        "spectrum.rank_movement_steady": "순위 유지",
        "spectrum.rank_movement_unchanged": "순위 동일",
        "spectrum.col_quintile": "밴드(5)",
        "spectrum.col_rank": "순위",
        "spectrum.col_move": "순위 변화",
        "spectrum.sort_watchlist_first": "워치 우선·점수순",
        "research.disagreement_stretch_vs_compression": "스펙트럼은 고평가 쪽인데 밸류 텐션은 ‘압축’으로 읽힙니다. 둘 다 맞을 수 있으니 다음 실적·유동성을 함께 봅니다.",
        "research.disagreement_value_vs_momentum": "저평가 밴드인데 모멘텀이 ‘팽창’으로 잡혀 있습니다. 단기 흐름과 중기 밸류의 괴리를 추적합니다.",
        "research.disagreement_anchor_unproven": "검증되지 않은 가정이 남아 있으므로, 아래 ‘미증명’ 블록을 우선 확인합니다.",
        "research.disagreement_balanced": "지표 조합이 크게 엇갈리지 않습니다. 다음 촉발 요인을 스펙트럼·저널에서 함께 봅니다.",
        "spectrum.h_short": "단기",
        "spectrum.h_medium": "중기",
        "spectrum.h_medium_long": "중장기",
        "spectrum.h_long": "장기",
        "spectrum.horizon_picker": "시간축",
        "spectrum.mock_tick_note": "데모: 가격 충격을 0–1 스펙트럼 축 반전으로 모사했습니다(실시간 시세 아님).",
        "spectrum.mock_mode": "가격 오버레이(모형)",
        "spectrum.mock_base": "기본 시드",
        "spectrum.mock_shock": "모의 충격(축 반전)",
        "spectrum.registry_surface_title": "Registry (읽기 전용)",
        "spectrum.registry_entry": "항목 ID",
        "spectrum.registry_status": "상태",
        "spectrum.registry_active_row": "채택(active) 모델군",
        "spectrum.thesis_family": "서사군(thesis_family)",
        "spectrum.challenger_strip": "챌린저 후보(미채택)",
        "spectrum.challenger_none": "등록된 챌린저 아티팩트 없음(이 지평).",
        "spectrum.col_why_now": "Why now",
        "panel.research.registry_strip_intro": "샌드박스·객체 섹션은 아래와 같이 Registry 계약 위에서만 읽습니다.",
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
        "panel.today_detail.meta": "MVP: 메시지 → Registry(읽기 전용) → 정보(스펙트럼·신호) → 연구 순서.",
        "today_detail.back": "← 홈으로",
        "today_detail.section_message": "1. 메시지",
        "today_detail.section_registry": "Registry (읽기 전용)",
        "today_detail.horizon_lens_title": "다른 시간축 렌즈(동일 종목)",
        "today_detail.horizon_lens_col": "시간축",
        "today_detail.disagreement_note": "신호 보존(불일치 메모)",
        "today_detail.section_information": "2. 정보",
        "today_detail.section_research": "3. 연구",
        "today_detail.supporting": "찬성 신호",
        "today_detail.opposing": "반대·주의 신호",
        "today_detail.evidence": "증거 요약",
        "today_detail.data_note": "데이터 레이어",
        "today_detail.spectrum_ctx": "스펙트럼 맥락",
        "today_detail.link_replay": "리플레이 패널 열기",
        "today_detail.link_journal": "저널에 기록",
        "today_detail.link_ask": "Ask AI에 붙여넣기",
        "today_detail.link_sandbox": "Research 샌드박스",
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
        "tsr.rail.today_summary": "오늘 요약",
        "tsr.rail.no_recent": "최근 거버넌스 이벤트 없음",
        "tsr.rail.change_chip_prefix": "오늘 거버넌스 적용",
        "tsr.primary.meta_sep": "·",
        "tsr.primary.why_now_empty": "현재 해석 준비되지 않음",
        "tsr.decision.one_line_empty": "한 줄 요약 준비되지 않음",
        "tsr.decision.deeper": "해석 근거 자세히",
        "tsr.decision.signals": "뒷받침 · 반증 신호",
        "tsr.decision.supporting": "뒷받침",
        "tsr.decision.opposing": "반증",
        "tsr.decision.unproven": "아직 미증명",
        "tsr.decision.watch": "계속 볼 것",
        "tsr.evidence.head": "증거 · 출처",
        "tsr.evidence.active_artifact": "활성 아티팩트",
        "tsr.evidence.no_artifact": "활성 아티팩트 미연결",
        "tsr.evidence.raw_ids": "원본 식별자 (감사용)",
        "tsr.recent.head": "최근 거버넌스 활동",
        "tsr.recent.empty": "최근 거버넌스 활동 없음",
        "tsr.recent.apply": "적용",
        "tsr.audit.head": "감사 · 원본 식별자",
        "tsr.audit.note": "아래 값은 개발/감사용 원본 식별자입니다.",
        "research_section.head": "연구 해석 · Research read",
        "research_section.current_read": "현재 해석 · Current read",
        "research_section.why_plausible": "해석 근거 · Why plausible",
        "research_section.unproven": "아직 미증명 · What remains unproven",
        "research_section.watch": "계속 볼 것 · What to watch",
        "research_section.bounded_next": "Bounded 다음 액션 · Bounded next step",
        "research_section.empty_head": "해당 종목 · 수평선에 연결된 질의 없음",
        "research_section.empty_body": "Ask AI에서 질의하면 이 영역에 구조화된 해석이 표시됩니다.",
        "research_section.no_bullets": "요약 없음",
        "research_section.no_evidence": "인용 증거 없음",
        "research_section.no_unproven": "미증명 항목 없음",
        "research_section.no_watch": "관찰 항목 없음",
        "research_section.no_sandbox_action": "제안된 샌드박스 액션 없음",
        "research_section.locale_dual": "한·영 모두",
        "research_section.locale_ko_only": "한국어만",
        "research_section.locale_en_only": "영어만",
        "research_section.locale_degraded": "부분 응답",
        "research_section.invoke_copy_hint": "터미널에서 아래 명령을 복붙해서 실행하세요 (UI 실행은 기본 비활성).",
        "research_section.invoke_ui_hint": "대기열 추가 후 터미널에서 harness-tick --queue sandbox_queue 를 실행하세요.",
        "research_section.invoke_copy_btn": "복사",
        "research_section.invoke_copy_done": "복사됨.",
        "research_section.invoke_enqueue_btn": "UI로 대기열 추가 (운영자 게이트)",
        "research_section.invoke_queue_poll": "큐 상태 새로고침",
        "research_section.invoke_state_queued": "큐에 적재됨 — 운영자가 harness-tick 실행 대기",
        "research_section.invoke_state_completed": "샌드박스 실행 완료",
        "research_section.invoke_state_blocked": "차단됨",
        "research_section.invoke_state_unknown": "상태 확인 불가",
        "research_section.invoke_state_loading": "상태 확인 중…",
        "research_section.invoke_error_disabled": "UI 대기열 추가가 비활성화되어 있습니다. 운영자가 터미널에서 복사한 명령을 실행해야 합니다.",
        "research_section.invoke_error_validation": "요청 내용이 검증을 통과하지 못했습니다.",
        "research_section.invoke_error_server": "서버에서 요청을 처리하지 못했습니다.",
        "research_section.invoke_error_raw": "원본 오류 세부",
        "research_section.locale_degraded_label_ko": "부분 응답",
        "research_section.locale_degraded_label_en": "Partial response",
        "tsr.invoke.contract.head": "이 액션의 범위",
        "tsr.invoke.contract.will_do": "수행: 샌드박스 큐에 bounded validation_rerun 요청 1건을 적재합니다.",
        "tsr.invoke.contract.will_not_do": "수행하지 않음: 활성 레지스트리 변경·아티팩트 승격·Today 화면 갱신은 하지 않습니다.",
        "tsr.invoke.contract.after_enqueue": "적재 후: 운영자가 터미널에서 `harness-tick --queue sandbox_queue` 를 실행해야 샌드박스 워커가 돌아갑니다.",
        "tsr.nav.primary.aria": "주요 작업",
        "tsr.nav.utility.aria": "보조 작업",
        "tsr.nav.utility.note": "감사·원본 데이터·번들 재로드",
        "lineage.head": "거버넌스 계보 · Governance lineage",
        "lineage.chip_applies": "적용 {n}건",
        "lineage.chip_sandbox_completed": "샌드박스 완료 {n}건",
        "lineage.chip_needs_rebuild": "DB 재빌드 필요",
        "lineage.step.proposal": "제안",
        "lineage.step.apply": "적용",
        "lineage.step.spectrum_refresh": "스펙트럼 리프레시",
        "lineage.step.validation_eval": "검증 평가",
        "lineage.followups": "샌드박스 팔로업",
        "lineage.no_followups": "샌드박스 팔로업 없음",
        "lineage.loading": "로드 중…",
        "lineage.unavailable": "계보 정보를 읽지 못했습니다.",
        "lineage.load_failed": "계보 로드 실패.",
        "plot.no_events": "타임라인에 표시할 이벤트 없음",
        "plot.apply_label": "적용",
        "plot.governed_apply": "거버넌스 적용",
        "plot.spectrum_refresh": "스펙트럼 리프레시",
        "plot.sandbox_followup": "샌드박스 팔로업",
        "plot.lane_apply": "거버넌스 적용",
        "plot.lane_spectrum": "스펙트럼 리프레시",
        "plot.lane_sandbox": "샌드박스 팔로업",
        "plot.lane_legend_note": "가로축 = 시간, 레인 = 이벤트 종류",
        "lineage.step_count": "4단계 중 {done}단계 완료",
        "lineage.step_after": "이전 대비 +{delta}",
        "lineage.step_pending": "대기",
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
        "panel.research.sandbox_title": "Custom Research Sandbox v1",
        "panel.research.sandbox_meta": "Set hypothesis, optional asset, horizon, and mode — deterministic cross-check vs bundle + Today seed (not generic chat).",
        "panel.research.deferred_empty": "Open Today detail for a symbol (or set Asset ID in the sandbox), then return here — the same message → registry → information → research contract loads read-only.",
        "panel.research.deferred_title": "Deferred research context (same contract as Today detail)",
        "panel.research.deferred_meta": "Stage 3 minimum surface — no extra telemetry.",
        "research.ask_chips_hint": "Governed Ask AI",
        "research.ask_chip_why_now": "Why now",
        "research.ask_chip_what_changed": "What changed",
        "research.ask_chip_what_to_watch": "What to watch",
        "sandbox.strip_from_today": "Context from Today detail",
        "sandbox.label_hypothesis": "Hypothesis or question",
        "sandbox.label_asset": "Asset ID (optional)",
        "sandbox.label_horizon": "Horizon",
        "sandbox.label_pit_mode": "Time mode",
        "sandbox.pit_snapshot": "Current snapshot",
        "sandbox.pit_stub": "PIT stub (honest placeholder)",
        "sandbox.label_mock_tick": "Demo price overlay",
        "sandbox.btn_run": "Run bounded analysis",
        "sandbox.result_title": "Structured result",
        "sandbox.scan_title": "Per-horizon scan (same asset)",
        "sandbox.col_horizon": "Horizon",
        "sandbox.col_band": "Band",
        "sandbox.col_pos": "Position",
        "sandbox.col_headline": "Headline",
        "sandbox.bullet_hypothesis_prefix": "Hypothesis / question:",
        "sandbox.bullet_selected_lens": "Selected lens ({hz_label}): spectrum band {band}.",
        "sandbox.bullet_headline_prefix": "Message headline:",
        "sandbox.bullet_asset_not_on_board": "Asset {asset_id} is not on the seed board for this horizon; scanning other horizons only.",
        "sandbox.bullet_cohort_scope": "Scope: cohort read from bundle (no single asset id).",
        "sandbox.bullet_decision_card_prefix": "Decision card gist:",
        "sandbox.bullet_pitch_prefix": "Representative pitch snippet:",
        "sandbox.pit_stub_note": "PIT stub: this MVP still crosses the same frozen snapshot/seed. Historical PIT replay will wire through Replay later.",
        "sandbox.disclaimer": "Output is deterministically composed from the bundle and Today seed — not an LLM. Not investment advice.",
        "sandbox.action_open_today_detail": "Open Today detail",
        "sandbox.action_open_replay": "Replay",
        "sandbox.action_open_ask_ai": "Ask AI",
        "sandbox.save_label": "Save this run to the ledger",
        "sandbox.recent_title": "Recent saved runs",
        "sandbox.empty_runs": "No saved sandbox runs yet.",
        "sandbox.prefill_stub": "How could we falsify or narrow the short-term premise for this object?",
        "sandbox.persisted_ok": "Saved to ledger",
        "sandbox.persisted_fail": "Ledger save failed (permissions/path)",
        "sandbox.ledger_readonly": "Research object from ledger (read-only)",
        "sandbox.apply_to_form": "Apply to form",
        "sandbox.close_ledger_detail": "Close",
        "sandbox.open_replay": "Replay",
        "replay.sandbox_context_hint": "Sandbox run context:",
        "replay_aging.title": "How it aged (summary)",
        "replay_aging.line_decisions": "{n} journal decision row(s).",
        "replay_aging.no_decisions": "No journal rows for this asset id.",
        "replay_aging.line_sandbox": "{n} saved sandbox run(s).",
        "replay_aging.no_sandbox": "No sandbox ledger rows for this asset.",
        "replay_aging.line_horizons": "{n} horizon snapshot(s) on Today seed.",
        "replay_aging.not_on_seed": "This asset is not on the Today seed board.",
        "replay_aging.disclaimer": "No numeric price-aging engine in MVP — this joins decision log, sandbox ledger, and spectrum seed.",
        "replay.snapshot.title": "Today message snapshot",
        "replay.snapshot.family": "Active model family (then)",
        "replay.snapshot.headline": "Headline snap",
        "replay.registry_surface_block": "Registry surface (read-only)",
        "replay.timeline.join_title": "Lineage joined from Today spectrum",
        "replay.timeline.join_intro": "Same registry / message snapshot pointers as the Today spectrum row for this asset.",
        "replay.timeline.pointer": "Replay lineage pointer",
        "replay.timeline.snapshot_id": "Message snapshot id",
        "replay.timeline.registry": "Registry entry",
        "replay.timeline.artifact": "Artifact",
        "replay.cf.intro_templates": "Counterfactual templates below are review stubs — numbers are illustrative, not live prices.",
        "replay.cf.preview": "Stub preview",
        "replay.cf.disclaimer": "Hypothetical branch — not drawn on the replay timeline; no implied profit or loss.",
        "replay.cf.label_watch_only": "Watch-only branch",
        "replay.cf.sum_watch_only": "Hold spectrum position fixed while changing only the decision posture to watch.",
        "replay.cf.narr_watch_only": "Decisions still land in the journal; the spectrum axis is unchanged. Outcomes are viewed in a separate frame.",
        "replay.cf.label_evidence_softens": "If key evidence softens",
        "replay.cf.sum_evidence_softens": "Assume the headline evidence line weakens and nudge the axis slightly lower.",
        "replay.cf.narr_evidence_softens": "When evidence strength drops, the same price band can read more defensively on the spectrum.",
        "replay.cf.label_horizon_stretch": "If read on a longer horizon",
        "replay.cf.sum_horizon_stretch": "Assume the same facts are viewed through a longer lens and nudge the axis upward.",
        "replay.cf.narr_horizon_stretch": "Longer horizons let growth/cycle narratives weigh more on the spectrum (illustrative shift).",
        "replay.cf.label_allocation_smaller": "If check size only shrinks",
        "replay.cf.sum_allocation_smaller": "Assume only the monitoring stake shrinks and nudge the axis slightly lower.",
        "replay.cf.narr_allocation_smaller": "Smaller checks change how pressure feels — the same headlines can read differently without execution.",
        "replay_aging.horizons": "Spectrum by horizon (current snapshot)",
        "replay_aging.decisions": "Journal (recent)",
        "replay_aging.sandbox": "Sandbox (recent)",
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
        "replay.no_events_for_asset": "No timeline events carry this asset_id. Compare with journal decisions, alerts, or the bundle primary asset.",
        "replay.asset_badge": "Asset",
        "panel.replay.chart_note": "Dashed line is illustrative rhythm (not live prices). Markers derive from stance codes.",
        "panel.replay.cf_intro": "Hypothetical branches — not drawn on the replay axis. No numeric engine in this build.",
        "panel.ask_ai.title": "Ask AI — decision copilot",
        "panel.ask_ai.meta": "Bounded prompts grounded in the bundle — not a generic chat surface.",
        "panel.ask_ai.brief_label": "Copilot brief (now)",
        "panel.ask_ai.shortcuts": "Shortcuts",
        "panel.ask_ai.placeholder": "Or type a governed prompt (e.g. decision summary, information layer)…",
        "panel.ask_ai.submit": "Submit",
        "panel.ask_ai.context_label": "Today / detail context",
        "panel.ask_ai.context_clear": "Clear context",
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
        "journal.lineage_bind_hint": "You have Today detail context open. If the asset ID matches, message snapshot and registry lineage are stored with the decision so Replay stays aligned.",
        "journal.card_lineage": "Replay lineage (stored on decision)",
        "journal.card_snapshot": "Message snapshot id",
        "journal.card_lineage_ptr": "Lineage pointer",
        "journal.card_message_line": "Linked message line",
        "journal.open_replay": "Open Replay from this decision",
        "journal.btn_log": "Log decision",
        "replay.now_then.title": "Then (Today join) vs now (authoritative bundle)",
        "replay.now_then.body_then": "Then: active model family on the spectrum row is “{family}”. Message snapshot id “{snapshot_id}” is the same key joined from Journal and timeline.",
        "replay.now_then.body_now": "Now: authoritative bundle review frame — stance code “{stance}”. Headline excerpt: {headline}",
        "replay.now_then.disclaimer": "Does not guarantee future returns or optimal timing; outcome is a separate evaluation frame.",
        "home.demo.pack_title": "Investor demo — frozen snapshot pack",
        "home.demo.pack_intro": "Manifest pointing at the same seed, bundle, and snapshot store. Reload bundle and use mock_price_tick 0/1 to reproduce.",
        "home.demo.investor_route": "Suggested demo order",
        "home.demo.price_overlay": "Price overlay (demo)",
        "demo.route.home_today": "Home — confirm Today spectrum and horizon",
        "demo.route.object_detail": "Object detail — message → information → research",
        "demo.route.journal_log": "Journal — log a decision (ideally right after Today detail)",
        "demo.route.replay_timeline": "Replay timeline — then / now framing",
        "demo.route.counterfactual": "Counterfactual lab — template stub preview",
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
        "spectrum.quintile_extreme_underpriced": "Extreme under",
        "spectrum.quintile_underpriced": "Underpriced",
        "spectrum.quintile_neutral": "Neutral",
        "spectrum.quintile_overpriced": "Overpriced",
        "spectrum.quintile_extreme_overpriced": "Extreme over",
        "spectrum.rank_movement_up": "Rank↑",
        "spectrum.rank_movement_down": "Rank↓",
        "spectrum.rank_movement_steady": "Steady",
        "spectrum.rank_movement_unchanged": "Same rank",
        "spectrum.col_quintile": "5-band",
        "spectrum.col_rank": "Rank",
        "spectrum.col_move": "Move",
        "spectrum.sort_watchlist_first": "Watch first · score",
        "research.disagreement_stretch_vs_compression": "Spectrum leans overpriced while tension reads compressed — both can be true; next prints and liquidity matter.",
        "research.disagreement_value_vs_momentum": "Underpriced band with stretched momentum — track the gap between short flow and medium value.",
        "research.disagreement_anchor_unproven": "Key claims remain unproven — prioritize the unproven block below.",
        "research.disagreement_balanced": "Signals are not sharply contradictory — watch the next catalysts across spectrum and journal.",
        "spectrum.h_short": "Short-term",
        "spectrum.h_medium": "Medium-term",
        "spectrum.h_medium_long": "Medium-long",
        "spectrum.h_long": "Long-term",
        "spectrum.horizon_picker": "Horizon",
        "spectrum.mock_tick_note": "Demo: price shock simulated by inverting the 0–1 spectrum axis (not live quotes).",
        "spectrum.mock_mode": "Price overlay (mock)",
        "spectrum.mock_base": "Base seed",
        "spectrum.mock_shock": "Mock shock (axis invert)",
        "spectrum.registry_surface_title": "Registry (read-only)",
        "spectrum.registry_entry": "Entry id",
        "spectrum.registry_status": "Status",
        "spectrum.registry_active_row": "Adopted (active) model family",
        "spectrum.thesis_family": "Thesis family",
        "spectrum.challenger_strip": "Challenger candidates (not on-surface)",
        "spectrum.challenger_none": "No challenger artifacts registered for this horizon.",
        "spectrum.col_why_now": "Why now",
        "panel.research.registry_strip_intro": "Sandbox and object sections read only through the registry contract below.",
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
        "panel.today_detail.meta": "MVP: Message → Registry (read-only) → Information (spectrum & signals) → Research.",
        "today_detail.back": "← Back to Home",
        "today_detail.section_message": "1. Message",
        "today_detail.section_registry": "Registry (read-only)",
        "today_detail.horizon_lens_title": "Other horizons (same asset)",
        "today_detail.horizon_lens_col": "Horizon",
        "today_detail.disagreement_note": "Disagreement-preserving note",
        "today_detail.section_information": "2. Information",
        "today_detail.section_research": "3. Research",
        "today_detail.supporting": "Supporting signals",
        "today_detail.opposing": "Opposing / caution signals",
        "today_detail.evidence": "Evidence summary",
        "today_detail.data_note": "Data layer",
        "today_detail.spectrum_ctx": "Spectrum context",
        "today_detail.link_replay": "Open Replay panel",
        "today_detail.link_journal": "Log to journal",
        "today_detail.link_ask": "Paste into Ask AI",
        "today_detail.link_sandbox": "Research sandbox",
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
        "tsr.rail.today_summary": "Today summary",
        "tsr.rail.no_recent": "No recent governance events",
        "tsr.rail.change_chip_prefix": "Governance apply today",
        "tsr.primary.meta_sep": "·",
        "tsr.primary.why_now_empty": "No current read prepared",
        "tsr.decision.one_line_empty": "One-line take not prepared",
        "tsr.decision.deeper": "Why this read · deeper rationale",
        "tsr.decision.signals": "Supporting · opposing signals",
        "tsr.decision.supporting": "Supporting",
        "tsr.decision.opposing": "Opposing",
        "tsr.decision.unproven": "Still unproven",
        "tsr.decision.watch": "What to keep watching",
        "tsr.evidence.head": "Evidence · sources",
        "tsr.evidence.active_artifact": "Active artifact",
        "tsr.evidence.no_artifact": "No active artifact linked",
        "tsr.evidence.raw_ids": "Raw identifiers (audit)",
        "tsr.recent.head": "Recent governance activity",
        "tsr.recent.empty": "No recent governance activity",
        "tsr.recent.apply": "apply",
        "tsr.audit.head": "Audit · raw identifiers",
        "tsr.audit.note": "Values below are raw engineering identifiers for audit.",
        "research_section.head": "Research read",
        "research_section.current_read": "Current read",
        "research_section.why_plausible": "Why plausible",
        "research_section.unproven": "What remains unproven",
        "research_section.watch": "What to watch",
        "research_section.bounded_next": "Bounded next step",
        "research_section.empty_head": "No structured research attached to this asset & horizon",
        "research_section.empty_body": "Ask a question in Ask AI; a structured read will land here.",
        "research_section.no_bullets": "No summary available",
        "research_section.no_evidence": "No cited evidence",
        "research_section.no_unproven": "Nothing flagged unproven",
        "research_section.no_watch": "Nothing flagged to watch",
        "research_section.no_sandbox_action": "No bounded next step proposed",
        "research_section.locale_dual": "KO + EN",
        "research_section.locale_ko_only": "KO only",
        "research_section.locale_en_only": "EN only",
        "research_section.locale_degraded": "Degraded response",
        "research_section.invoke_copy_hint": "Copy-paste the command below in a terminal (UI invoke disabled by default).",
        "research_section.invoke_ui_hint": "Enqueue then run harness-tick --queue sandbox_queue in the terminal.",
        "research_section.invoke_copy_btn": "Copy",
        "research_section.invoke_copy_done": "Copied.",
        "research_section.invoke_enqueue_btn": "Enqueue via UI (operator-gated)",
        "research_section.invoke_queue_poll": "Refresh queue state",
        "research_section.invoke_state_queued": "Queued — waiting for operator to run harness-tick",
        "research_section.invoke_state_completed": "Sandbox run completed",
        "research_section.invoke_state_blocked": "Blocked",
        "research_section.invoke_state_unknown": "State unavailable",
        "research_section.invoke_state_loading": "Checking state…",
        "research_section.invoke_error_disabled": "UI enqueue is disabled; the operator must run the copied terminal command instead.",
        "research_section.invoke_error_validation": "Request did not pass validation.",
        "research_section.invoke_error_server": "The server could not process this request.",
        "research_section.invoke_error_raw": "Raw error detail",
        "research_section.locale_degraded_label_ko": "Partial response (KO)",
        "research_section.locale_degraded_label_en": "Partial response",
        "tsr.invoke.contract.head": "What this action does",
        "tsr.invoke.contract.will_do": "Will do: Enqueue one bounded validation_rerun request onto the sandbox queue.",
        "tsr.invoke.contract.will_not_do": "Will NOT do: Does not modify the active registry, promote artifacts, or refresh Today.",
        "tsr.invoke.contract.after_enqueue": "After enqueue: Operator must run `harness-tick --queue sandbox_queue` for the worker to execute.",
        "tsr.nav.primary.aria": "Primary actions",
        "tsr.nav.utility.aria": "Utility actions",
        "tsr.nav.utility.note": "Audit, raw data, bundle reload",
        "lineage.head": "Governance lineage",
        "lineage.chip_applies": "applies {n}",
        "lineage.chip_sandbox_completed": "sandbox completed {n}",
        "lineage.chip_needs_rebuild": "DB rebuild needed",
        "lineage.step.proposal": "Proposal",
        "lineage.step.apply": "Apply",
        "lineage.step.spectrum_refresh": "Spectrum refresh",
        "lineage.step.validation_eval": "Validation eval",
        "lineage.followups": "Sandbox followups",
        "lineage.no_followups": "No sandbox followups",
        "lineage.loading": "Loading…",
        "lineage.unavailable": "Lineage information unavailable.",
        "lineage.load_failed": "Failed to load lineage.",
        "plot.no_events": "No timeline events to plot",
        "plot.apply_label": "Apply",
        "plot.governed_apply": "Governed apply",
        "plot.spectrum_refresh": "Spectrum refresh",
        "plot.sandbox_followup": "Sandbox followup",
        "plot.lane_apply": "Governed apply",
        "plot.lane_spectrum": "Spectrum refresh",
        "plot.lane_sandbox": "Sandbox followup",
        "plot.lane_legend_note": "x = time, rows = event kind",
        "lineage.step_count": "{done} of 4 steps complete",
        "lineage.step_after": "+{delta} after previous",
        "lineage.step_pending": "pending",
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
        "watch.reorder_title": "추적 종목 순서",
        "watch.reorder_explain": "스펙트럼 점수 순서는 모델이 정합니다. 여기서는 워치리스트에 보이는 식별자 순서만 바꿉니다.",
        "watch.move_up": "위로",
        "watch.move_down": "아래로",
        "watch.save_order": "순서 저장",
        "watch.save_failed": "저장에 실패했습니다.",
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
        "watch.reorder_title": "Tracked symbol order",
        "watch.reorder_explain": "Spectrum score ordering stays model-driven. Here you only change how watchlist ids are listed.",
        "watch.move_up": "Move up",
        "watch.move_down": "Move down",
        "watch.save_order": "Save order",
        "watch.save_failed": "Could not save order.",
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
        # Bounded Non-Quant Cash-Out v1 — overlay short labels (Today compact).
        # Fixed copy, no recommendation/buy/sell/guarantee wording.
        "overlay.short.regime_shift": "레짐 변화 관찰 중",
        "overlay.short.confidence_adjustment": "트랜스크립트 톤 반영",
        "overlay.short.invalidation_warning": "무효화 신호 감시",
        "overlay.short.catalyst_window": "이벤트 창 열림",
        "overlay.short.hazard_modifier": "하방 비대칭 확대",
        "horizon.state.template_fallback_note": "장기 지평은 아직 샘플 템플릿입니다 — 실-파생 전환 전까지 참고용입니다.",
        "horizon.state.insufficient_evidence_note": "아직 충분한 근거가 쌓이지 않은 지평입니다 — 과장된 확신을 만들지 않습니다.",
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
        "overlay.short.regime_shift": "Regime shift watch",
        "overlay.short.confidence_adjustment": "Confidence adjusted by transcript",
        "overlay.short.invalidation_warning": "Potential invalidation risk",
        "overlay.short.catalyst_window": "Catalyst window active",
        "overlay.short.hazard_modifier": "Downside asymmetry widened",
        "horizon.state.template_fallback_note": "Long horizons are still on a sample template — reference use only until real-derived lands.",
        "horizon.state.insufficient_evidence_note": "This horizon has not accumulated enough evidence yet — we refuse to manufacture confidence.",
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
