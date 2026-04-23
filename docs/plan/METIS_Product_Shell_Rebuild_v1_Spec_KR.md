# METIS Product Shell Rebuild v1 — 스펙 (Patch 10A 베이스)

> 대상: 사용자용 웹툴 (Product Shell) 의 아키텍처·표면·언어 계약을 처음으로 명문화한 문서.
> 범위: Patch 10A/10B 가 **실제로 구현한 것** + 10C 재설계가 준수해야 할 계약.
> 관련: [METIS_MVP_Unified_Product_Spec_KR_v1](./METIS_MVP_Unified_Product_Spec_KR_v1.md), [METIS_Product_Shell_Rebuild_v1_Patch_10A_Plan_KR](./METIS_Product_Shell_Rebuild_v1_Patch_10A_Plan_KR.md)

---

## 1. 왜 Product Shell 을 따로 만드는가

기존 Ops Cockpit (`/` 에서 서빙되던 Phase 47 UI) 는 **연구자·운영자의 통합 대시보드**로 성장했다. 장점은 많지만 사용자 관점에서는:

- 내부 아이디 (`art_*`, `reg_*`, `factor_*`) 가 직접 노출되고,
- 모델군·서사군 같은 엔지니어링 계층이 가장 먼저 보이며,
- 한 스크린에 들어있는 정보량이 너무 많아 "지금 이 종목에 대해 뭘 해야 하나?" 에 답을 주지 못한다.

Patch 10A 는 이 문제를 **UI 튜닝이 아니라 아키텍처 분리**로 해결한다.

- `/` → 사용자용 Product Shell. 엔지니어링 ID 는 UI 에도 DTO 에도 **절대 등장하지 않는다.**
- `/ops` → 기존 Cockpit. `METIS_OPS_SHELL=1` 이 있어야 뜬다. **운영자만 본다.**

---

## 2. 아키텍처 하드 2-파일 분리

### 2.1 파일 레이아웃

```text
src/phase47_runtime/
├── app.py                              # 루트(/) → Product Shell, /ops → Cockpit (env-gated)
├── routes.py                           # /api/product/* 신규, /api/* 기존 보존
├── static/
│   ├── index.html                      # Product Shell 마운트 포인트 (신규)
│   ├── product_shell.css               # Design tokens + 8 priority components (신규)
│   ├── product_shell.js                # Product Shell IIFE (신규)
│   ├── ops.html                        # 기존 Cockpit HTML (git mv)
│   └── ops.js                          # 기존 Cockpit JS  (git mv)
└── product_shell/
    ├── __init__.py                     # 유출 방지 선언적 주석
    └── view_models.py                  # DTO 매퍼 레이어 (신규)
```

### 2.2 라우팅 계약

| 경로 | 서빙 | 조건 |
|---|---|---|
| `/`, `/index.html` | `static/index.html` | 항상 활성. 존재하지 않으면 500. |
| `/ops`, `/ops/index.html` | `static/ops.html` | `METIS_OPS_SHELL ∈ {1, true, yes}` 일 때만, 아니면 404. |
| `/api/product/today` | `view_models.build_today_product_dto()` | `PRODUCT_TODAY_V1` DTO 반환. |
| `/api/*` | 기존 엔드포인트 그대로 | Cockpit 과의 바인딩 불변. |

### 2.3 API 접두어 계약

- 사용자용 데이터는 **전부** `/api/product/*` 로 나간다.
- `/api/*` (접두어 `product` 없음) 는 **내부용**이며 Cockpit 에서만 호출한다.
- 같은 도메인의 두 트리가 공존하지만, **서로 경계 없이 섞이지 않는다** — 이 경계가 무너지면 Product Shell 의 언어 계약(§5)이 깨진다.

---

## 3. 뷰모델 매퍼 레이어

### 3.1 목적

백엔드 상태(브레인 번들, 스펙트럼 row, provenance enum, registry id)를 **사용자 언어**로 번역한다. 이 레이어는 DTO 를 밖으로 내보내기 전에 **엔지니어링 토큰을 박탈**한다.

### 3.2 핵심 API

```python
# src/phase47_runtime/product_shell/view_models.py

HORIZON_KEYS: tuple[str, ...] = ("short", "medium", "medium_long", "long")

def compose_today_product_dto(
    *, bundle, spectrum_by_horizon, lang="ko",
    watchlist_tickers=None, now_utc: str,
) -> dict: ...   # 순수 함수, 테스트에서 사용

def build_today_product_dto(*, lang="ko", watchlist_tickers=None) -> dict: ...
                                  # 디스크/레지스트리 로더 포함, API 라우트에서 사용

def strip_engineering_ids(obj) -> obj: ...
                                  # 재귀 스크러버. 마지막 방어선.
```

### 3.3 스크러버 패턴 (banned)

- `art_[a-z0-9_]+`, `reg_[a-z0-9_]+`, `factor_[a-z0-9_]+`, `pkt_[a-z0-9_]+`
- `pit:demo:*`, `registry_entry_id`, `horizon_provenance`
- 원시 provenance enum: `real_derived`, `real_derived_with_degraded_challenger`, `template_fallback`, `insufficient_evidence`
- 버전 슬러그: `name_v\d+`

매치된 문자열은 `"[redacted]"` 로 치환된다.

### 3.4 Grade / Stance / Confidence 분리 (사용자 정제 R2)

| 축 | 역할 | 값 |
|---|---|---|
| `grade_chip` | **신호 강도** | A+, A, B, C, D, F |
| `stance_label` | **방향성** | 강한 매수 경향 / 매수 경향 / 중립 / 매도 경향 / 강한 매도 경향 |
| `confidence_badge` | **데이터 품질** | live / live_with_caveat / sample / preparing |

**샘플 데이터일 때 grade 가 A+ 로 찍히면 안 된다** → `_spectrum_position_to_grade(..., source_key=...)` 가 source 품질로 grade 의 상한을 제한한다.

---

## 4. Today 표면 계약

### 4.1 레이아웃 (위 → 아래)

```text
┌─────────────────────────────────────────────────────────┐
│ trust strip         (정직한 신뢰 티어 헤더)              │
├─────────────────────────────────────────────────────────┤
│ today at a glance   (오늘 한 눈에 보기: 문장 요약 3줄)   │
├─────────────────────────────────────────────────────────┤
│ hero horizon cards × 4   ← 시각 1순위                   │
│   - grade chip + stance label + confidence badge        │
│   - 한 줄 스토리                                        │
│   - 포지션 바 (매도-중립-매수)                          │
│   - mini SVG 스파크라인                                 │
│   - CTA 주: "근거 보기" → inline evidence drawer (R1)   │
├─────────────────────────────────────────────────────────┤
│ selected movers     (변화가 큰 종목 3-5 개)             │
├─────────────────────────────────────────────────────────┤
│ watchlist strip     ← 시각 우선순위 낮음 (R3, subdued)  │
├─────────────────────────────────────────────────────────┤
│ advanced disclosure (접혀 있음. /ops 안내)              │
└─────────────────────────────────────────────────────────┘
```

### 4.2 사용자 정제 3 지점 (10A 에 반영됨)

- **R1.** Hero 카드의 1순위 CTA 는 **Today 내부 evidence drawer** 를 연다. Research 페이지로의 하드 네비게이션은 10A 에서는 disabled.
- **R2.** `grade chip` 과 `stance label` 은 분리 병치한다 (§3.4).
- **R3.** `watchlist strip` 은 유지하되 hero 카드보다 **시각 우선순위가 낮다** (캡션 사이즈, subdued 서피스).

### 4.3 Stub 패널 (10B 에서 정식 재설계)

Research / Replay / Ask AI 는 10A 에서는 "곧 도착" 안내 카드로 둔다. 각 스텁은:

- 제목 + 한 문장 약속 + "지금은 Today 근거 보기로도 충분히 답을 드립니다" 안내.
- 매수/매도 권유 문구 없음, 과장된 예측 확신 없음 (Product Spec §4.3, §5.1 준수).

---

## 5. 언어 계약

### 5.1 금지 목록 (No-leak)

사용자가 도달하는 표면 — `static/index.html` · `product_shell.js` · `product_shell.css` · `/api/product/*` JSON — 어디에도 다음이 나타나서는 안 된다:

- 엔지니어링 ID 프리픽스: `art_`, `reg_`, `factor_`, `pkt_`, `pit:demo:`
- 내부 enum: `real_derived`, `real_derived_with_degraded_challenger`, `template_fallback`, `insufficient_evidence`, `horizon_provenance`, `registry_entry_id`
- 버전 슬러그: `..._v\d+`
- 권유 명령 (`buy`, `sell`, `매수하세요`, `매도하세요`)

이 계약은 `src/tests/test_agh_v1_patch_10a_copy_no_leak.py` 가 HTML · JS · CSS · 실제 DTO 출력 4 면 모두를 스캔해서 강제한다.

### 5.2 Degraded 언어 (Honest not hype)

| 내부 provenance | 제품 `source_key` | KO 라벨 | 의미 |
|---|---|---|---|
| `real_derived` | `live` | 실시간 데이터 | 정상 운영 |
| `real_derived_with_degraded_challenger` | `live_with_caveat` | 실시간 데이터 (일부 제한) | 일부 근거 원천이 약함 |
| `template_fallback` | `sample` | 샘플 데이터 | 실데이터 대체 중 |
| `insufficient_evidence` | `preparing` | 준비 중 | 아직 못 보여드림 |

**샘플일 때 샘플이라고 말한다.** 그래야 사용자 신뢰의 바닥이 만들어진다.

### 5.3 로케일 키

- 접두어 `product_shell.*` 로 46 개 KO/EN 쌍을 `src/phase47_runtime/phase47e_user_locale.py` 에 추가.
- KO/EN parity 는 테스트가 강제 (누락 시 fail).

---

## 6. 비주얼 시스템

### 6.1 Design tokens (발췌)

```css
:root {
  --ps-color-surface-0: #0b0d11;
  --ps-color-surface-1: #101419;
  --ps-color-text-primary: #e8ecef;
  --ps-color-semantic-success: #6fcf97;
  --ps-color-semantic-warning: #f2c94c;
  --ps-color-semantic-danger:  #eb5757;
  --ps-sp-1: 4px;  --ps-sp-2: 8px;  --ps-sp-3: 12px;
  --ps-sp-4: 16px; --ps-sp-5: 24px; --ps-sp-6: 32px;
  --ps-radius-sm: 6px; --ps-radius-md: 10px; --ps-radius-lg: 14px;
  --ps-fz-body: 14px; --ps-fz-h3: 18px; --ps-fz-h2: 22px;
  --ps-fw-normal: 400; --ps-fw-bold: 700;
}
```

### 6.2 우선 8 컴포넌트

`.ps-hero-card`, `.ps-grade-chip`, `.ps-stance-label`, `.ps-confidence-badge`, `.ps-change-bullet`, `.ps-mini-sparkline`, `.ps-mover-card`, `.ps-watchlist-chip`, `.ps-disclosure-drawer`.

### 6.3 격리 원칙

- 외부 차트 라이브러리 없음 — 스파크라인은 SVG hand-roll.
- 외부 폰트 네트워크 요청 없음 — system UI stack 만.
- Ops Cockpit 의 인라인 스타일은 **그대로 놔둔다** — Product Shell 이 건들지 않는다.

---

## 7. 테스트 계약

| 파일 | 역할 |
|---|---|
| `src/tests/test_agh_v1_patch_10a_hard_split.py` | 라우팅 / env gate / 파일 분리 / HTTP probe |
| `src/tests/test_agh_v1_patch_10a_visual_system.py` | Design tokens + 8 컴포넌트 + JS 마운트 포인트 |
| `src/tests/test_agh_v1_patch_10a_today_product_dto.py` | DTO shape / grade / stance / confidence / scrub |
| `src/tests/test_agh_v1_patch_10a_copy_no_leak.py` | HTML/JS/CSS/DTO regex 스캔 + KO/EN parity |

앞 패치 (6~9) 의 회귀 테스트는 `static/ops.html`, `static/ops.js` 로 경로만 업데이트해서 **그린 유지**.

---

## 8. 10A 가 **의도적으로** 하지 않은 것

- Research / Replay / Ask AI 의 **정식 재설계** — 10B.
- 모바일/태블릿 반응형 튜닝 — 10C.
- 실제 fetch 분기 (production vs sample) 의 사용자용 구분 뷰 — 10B.
- AI chat / conversational Ask UI — 10B.
- 추가 기능 증가보다 **신뢰 가능한 Today 한 장** 을 우선한다는 Build Plan §14 원칙을 준수.

---

## 9. 다음 단계 (10B 진입 계약)

- `/api/product/research`, `/api/product/replay`, `/api/product/ask` 라우트와 DTO 매퍼 도입.
- Today 내부 evidence drawer 에서 "이 종목 전체 근거" 로 점프하는 soft link (페이지 이동 없이 expand) 로 Research 를 확장.
- Ask AI 는 "근거 안에서만 답한다" 계약 (Retrieval-grounded) 을 명문화한 뒤 여는 순서.

---

## 10. Patch 10B 가 **실제로 구현한 것** (2026-04-23)

### 10.1 공통 — `view_models_common.py` 추출

Today 가 사용하던 `src/phase47_runtime/product_shell/view_models.py` 에서 `HORIZON_KEYS`, `strip_engineering_ids`, grade/stance/confidence/peer helper 를 `view_models_common.py` 로 추출. 네 표면 (Today/Research/Replay/Ask) 이 **단일 스크러버/단일 grade/stance/confidence 정의** 를 공유. `strip_engineering_ids` 금지 패턴에 `job_*`, `sandbox_request_id`, `process_governed_prompt`, `counterfactual_preview_v1`, `sandbox_queue` 를 추가.

### 10.2 Research — landing + 3-rail deep-dive

- **DTO contracts** (`view_models_research.py`):
  - `PRODUCT_RESEARCH_LANDING_V1` = `{contract, as_of, horizon_columns[4]}`. 각 column 은 `{horizon_key, horizon_label_ko/en, tiles[{asset_id, asset_display, grade, stance, confidence, one_liner_ko/en, deep_link}]}`.
  - `PRODUCT_RESEARCH_DEEPDIVE_V1` = `{contract, asset_id, asset_display, horizon_key, as_of, claim, evidence[5], actions[3], breadcrumbs, empty_state?}`.
  - Evidence 5 카드 kind: `what_changed` / `strongest_support` / `counter_or_companion` / `missing_or_preparing` / `peer_context`. 카드마다 `title_ko/en`, `body_ko/en`, optional `meta` (peer chips 등). 제품 언어만 — raw artifact id 노출 없음.
  - Actions 3 kind: `open_replay`, `ask_ai`, `back_to_today`. 프런트엔드가 kind 기반으로 network action 매핑.
- **Route**: `GET /api/product/research?presentation=landing|deepdive&asset_id=&horizon_key=`. 누락된 자산·구간은 `empty_state.reason_key` 로 정직 번역.
- **Empty state**: `asset_not_registered`, `horizon_not_available`, `evidence_missing_preparing` 세 가지로 고정. 카피 키 `product_shell.research.empty.*`.

### 10.3 Replay — timeline + gap annotation + 3 시나리오

- **DTO contract** (`view_models_replay.py`): `PRODUCT_REPLAY_V1` = `{contract, asset_id, asset_display, horizon_key, as_of, headline, summary_counts{total_events, gap_count, first_event_ts, last_event_ts}, timeline[{kind, ts, title_ko/en, body_ko/en, meta?}], scenarios[3], advanced_disclosure}`.
- **Timeline kinds**: `proposal`, `decision`, `applied`, `spectrum_refresh`, `validation_evaluation`, `sandbox_request`, `sandbox_result`, `gap` (30+ 일 공백 annotation), `checkpoint` (시작/최근 상태 표시). `kind` 는 UI 색상·아이콘 매핑 전용이며 DTO 는 여전히 제품 언어.
- **Scenarios**: `baseline` / `weakened_evidence` / `stressed` 3 카드. 각 카드 `{label_ko/en, description_ko/en, projected_grade, projected_stance, delta_explanation_ko/en}`. `_build_scenarios` 가 baseline position 에 ±shift 를 적용해 grade/stance 를 재계산 — 환상적 숫자 없이 상대적 민감도만 보여준다.
- **Advanced disclosure**: `{visible:false, hint_ko/en}`. Hint 는 "/ops 에서 원본 payload 확인" 한 줄. payload 자체는 고객 DTO 에 절대 실리지 않음.
- **Route**: `GET /api/product/replay?asset_id=&horizon_key=`. 하네스 스토어가 비어 있으면 `_try_load_lineage` 가 None → empty state.

### 10.4 Ask AI — bounded decision assistant

- **DTO contracts** (`view_models_ask.py`):
  - `PRODUCT_ASK_V1` (landing) = `{contract, context_card, quick_chips[6], free_text{placeholder_ko/en, submit_label_ko/en}, contract_banner, requests{cards[]}}`.
  - `PRODUCT_ASK_QUICK_V1` = `{contract, intent, answer{claim[], evidence[], insufficiency[], grounded:bool}}`.
  - `PRODUCT_ASK_ANSWER_V1` (free-text) = `{contract, answer{claim[], evidence[], insufficiency[], grounded:bool}, degraded?:{reason_key, message_ko/en}}`.
  - `PRODUCT_REQUEST_STATE_V1` = `{contract, cards[{request_id_display, kind_label_ko/en, status_key(running|completed|blocked), hint_ko/en}]}`.
- **Quick intents (6)**: `explain_claim`, `show_support`, `show_counter`, `other_horizons`, `why_confidence`, `whats_missing`. 모두 **노출된 근거 안에서만** 결정론적으로 생성. Brain bundle 범위를 넘어가는 질문이면 `insufficiency` 배열로 정직 답변.
- **Free-text**: `api_conversation` 을 `scrub_free_text_answer` 가 래핑. 호출 실패·빈 응답이면 `_degraded_answer` 로 전환 (`grounded:false`, banner 로 degraded 명시). 성공 응답도 `strip_engineering_ids` 로 한 번 더 스크럽.
- **Routes**: `GET /api/product/ask`, `GET /api/product/ask/quick?intent=&asset_id=&horizon_key=`, `POST /api/product/ask`, `GET /api/product/requests`.

### 10.5 시각 시스템 v2 — 18 신규 컴포넌트

`product_shell.css` 에 Research (`.ps-research-landing`, `.ps-research-column`, `.ps-research-tile`, `.ps-research-empty`, `.ps-research-deepdive`, `.ps-breadcrumbs`, `.ps-rails`, `.ps-claim-card`, `.ps-evidence-rail`, `.ps-evidence-card`, `.ps-missing-badge`, `.ps-peer-chip`, `.ps-action-rail`, `.ps-action-chip`), Replay (`.ps-replay`, `.ps-replay-timeline`, `.ps-timeline-event`, `.ps-timeline-gap`, `.ps-timeline-checkpoint`, `.ps-scenarios`, `.ps-scenario-card`), Ask (`.ps-ask`, `.ps-ask-main`, `.ps-ask-context-card`, `.ps-ask-quick-grid`, `.ps-ask-action-chip`, `.ps-ask-freetext`, `.ps-ask-answer`), 공용 (`.ps-request-state-card`, `.ps-advanced-drawer`, `.ps-tooltip` info/caution/trust 3 variants) 를 추가. 10A 다크 프리미엄 톤 + system UI stack 유지, 외부 차트 라이브러리 없음, 반응형 (1100/820/640 px fallback).

### 10.6 프런트엔드 연결성 — STATE.focus + hash routing

- `STATE.focus = {asset_id, horizon_key}` 를 전역으로 두고, 네 패널이 모두 참조. Today → Research deep-dive → Replay → Ask 가 **같은 포커스** 위에서 한 걸음씩 이어진다.
- URL hash `#panel?asset=AAPL&h=short` 왕복 동기화: `applyHash` (hash → state + fetch) ↔ `updateHashFromState` (state → hash). 브라우저 back/forward + 링크 공유 가능.
- Today hero secondary CTA "리서치 열기" 를 활성화 (10A 에서는 disabled), selected_movers 카드에 "자세히 보기 →" soft-link 추가 → Research deep-dive 로 직결.
- 렌더러 교체: `renderResearchPanel` (landing grid + deep-dive 3-rail + breadcrumbs), `renderReplayPanel` (타임라인 + 3 시나리오 + advanced drawer), `renderAskPanel` (context + quick + free-text + answer + request-state side). 10A 의 `renderStub` 는 "로딩" 변이로만 재활용.

### 10.7 언어 계약 확장 + 10B no-leak

- `phase47e_user_locale.py` 에 `product_shell.research.*` 21 쌍 + `product_shell.replay.*` 17 쌍 + `product_shell.ask.*` 24 쌍 = 62 쌍 추가 (KO/EN parity).
- `test_agh_v1_patch_10b_copy_no_leak.py` 가 Product Shell HTML/JS/CSS + 모든 새 DTO (research landing/deepdive, replay, ask landing/quick/freetext degraded, request state) 를 스캔해 `art_*`, `reg_*`, `factor_*`, `pkt_*`, `job_*`, `sandbox_request_id`, `process_governed_prompt`, `counterfactual_preview_v1`, `sandbox_queue`, raw provenance enum, "buy/sell" 명령형이 **어디에도** 없음을 강제. 118 파라미터 케이스 모두 green.

### 10.8 Evidence + Runbook

- `scripts/agh_v1_patch_10b_product_shell_freeze_snapshots.py` = Product Shell HTML/JS/CSS + DTO 샘플 14 (research landing/deepdive + replay + ask landing/quick + freetext degraded + request state, 각 KO/EN) + SHA256 manifest 를 `data/mvp/evidence/screenshots_patch_10b/` 에 기록.
- `scripts/agh_v1_patch_10b_product_shell_runbook.py` = S1..S7 (research mapper / replay mapper / ask mapper / CSS 컴포넌트 / JS state+hash+renderers / locale+no-leak / routes) 를 코드 수준 플래그로 검증, 결과 7 개 `*_ok` + `all_ok` 전부 green.
- 산출 evidence: `data/mvp/evidence/patch_10b_product_shell_{runbook,bridge}_evidence.json`.

### 10.9 10B 가 **의도적으로** 하지 않은 것

- Ask AI 의 **실 LLM 품질 평가 golden-set** 은 10C 이후. 지금은 `api_conversation` 래퍼가 실패·빈 응답에서 `degraded` 로 내려가는 구조적 보장만 한다.
- Research 의 **tile 스파크라인** — 10A Today 패턴을 재사용하기로 했으나 10B 는 one-liner + grade + stance 로 한 발 먼저 납품. Sparkline 은 10C 후보.
- Replay 의 **실제 이벤트 쓰기** (sandbox result 를 timeline 에 즉시 반영) 는 Patch 9 C·A/C·B 경로 위에서 돌고 있으며 10B 는 **읽기 표현** 만.


## 11. Patch 10C 가 **실제로 추가한 것** (2026-04-23, coherence / trust / language closure)

10C 는 "네 표면이 같은 진실을 같은 제품 언어로 말한다" 를 **코드 수준 불변식**으로 봉인한 seal patch 다. 새 페이지·새 카피·새 sandbox kind 를 **만들지 않았고**, 이미 작동하던 Today / Research / Replay / Ask AI 를 같은 근거 위에 묶었다.

### 11.1 공통 계약 — `view_models_common.py` 에 3 개 새 함수

- **`compute_coherence_signature(...)`** — `(asset_id, horizon_key, quantized_position, grade_key, stance_key, source_key, digest(what_changed), digest(rationale_summary))` 로부터 **언어 독립적** 12-hex SHA-256 지문(`fingerprint`) 을 만든다. 계약 버전은 `COHERENCE_V1` (대문자 V — 스크러버가 소문자 `*_vN` 을 지우기 때문에 의도적으로 대문자).
- **`build_shared_focus_block(...)`** — 네 표면 모두가 **문자 단위로 동일하게** 포함하는 단일 soure-of-truth 블록 `{asset_id, horizon_key, horizon_caption, family_name, grade, stance, confidence, evidence_summary, coherence_signature}`. position 이 없어도 `best_representative_row` 로 최선 대표 row 를 선택한다.
- **`SHARED_WORDING`** — 10 버킷(`sample`, `preparing`, `limited_evidence`, `production`, `freshness`, `bounded_ask`, `next_step`, `what_changed`, `knowable_then`, `out_of_scope`) 의 KO/EN 공통 카피 사전. `shared_wording(kind, lang)` 로 조회하고, 알려지지 않은 kind 는 자동으로 `limited_evidence` 로 안전 fallback.

### 11.2 네 표면 통합 배선

- `compose_today_product_dto` 는 각 hero card 에 `shared_focus + coherence_signature + cta_more` 를 실었고, 가장 강한 live 카드를 `primary_focus` 로 top-level 에 끌어올린다. `shared_wording` 도 top-level 에 동봉.
- `compose_research_deepdive_dto` / `compose_replay_product_dto` / `compose_ask_product_dto` 는 모두 **같은 `shared_focus` 블록**을 top-level 에 embed 하고 `coherence_signature`, `evidence_lineage_summary`, `shared_wording`, `breadcrumbs` 를 통일된 키 이름으로 노출.
- Research landing/Ask quick 은 deep-dive 가 아니지만, 각 tile 이 `shared_focus` 를 embed 해 같은 지문을 공유한다.

### 11.3 Ask AI trust closure — 3중 grounding guard

1. **pre-LLM `classify_question_scope`** — 프롬프트를 lower-casing 후 4 가지로 분류: `in_scope` / `advice_request` / `off_topic` / `foreign_ticker`. advice/off_topic/foreign 은 **LLM 호출 없이** 구조적 `out_of_scope` 답변으로 단락.
2. **LLM-side `surfaced_context_summary`** — 화면에 보이는 focus (grade/stance/confidence + evidence 한 줄 요약) 를 **한 문단**으로 묶어 `copilot_context.surfaced_evidence` + `bounded_contract` 지시어와 함께 `api_conversation` 에 주입.
3. **post-LLM `scan_response_for_hallucinations`** — 반환된 body 를 advice language / foreign ticker / price target 로 스캔. 1 건이라도 걸리면 **body 자체를 폐기** 하고 `partial` 답변으로 downgrade — 고객은 hallucinate 된 문장을 **한 글자도** 보지 못한다.

### 11.4 Focus continuity UI — 리본 + soft-link + 통합 breadcrumb

- **`.ps-focus-ribbon`** — Research (deepdive) / Replay / Ask 공통 포커스 리본. `(asset_id, horizon_key)` + 동일 grade/stance/confidence chips + coherence 지문(muted code), 그리고 네 표면을 가로지르는 soft-link 버튼 그룹 (`today / research / replay / ask_ai`) 과 "초점 해제". data-source 에 따라 좌측 accent bar 가 live(green) / sample(purple) / preparing(amber) 로 변한다.
- **Today hero `cta_more`** — primary/secondary CTA 하단에 소프트 링크 row (chip) 로 "리플레이 열기 / Ask AI 에 질문" 을 추가. 동일 구간의 대표 ticker 가 있으면 그 포커스를 그대로 가지고 넘어간다.
- **Breadcrumb 통일** — Research deepdive / Replay / Ask 모두 `Today / <surface> / <ticker>` 구조로 정렬. 모든 링크는 `setActivePanel` 만 사용.

### 11.5 Language contract — 새 locale 3 패밀리

`phase47e_user_locale.py` 에 `product_shell.continuity.*` (10 키) + `product_shell.trust.*` (5 키) + `product_shell.ask.out_of_scope.*` (3 키) = 18 쌍 KO/EN parity. `test_agh_v1_patch_10c_copy_no_leak.py` 가 세 패밀리 parity + 비어있지 않음을 강제한다.

### 11.6 불변 테스트 — cross-surface coherence 를 코드로 봉인

- `test_agh_v1_patch_10c_coherence.py` — 동일 focus 에 대해 Today/Research/Replay/Ask (landing/quick 포함) 의 `coherence_signature.fingerprint` 가 **KO·EN 모두** 동일함, 언어만 바꾸면 지문 불변, `rationale_summary` 또는 grade-tier 를 건너는 position 변경은 지문을 바꾼다.
- `test_agh_v1_patch_10c_ops_product_parity.py` — Ops raw lineage (`api_governance_lineage_for_registry_entry`) 와 Product Replay DTO timeline 의 event count·sandbox count 가 일치, 원본 packet id (`pkt_*`) 는 DTO 에 단 한 글자도 노출되지 않음, outcome 은 모두 humanized localized 타이틀.
- `test_agh_v1_patch_10c_language_contract.py` — 네 표면 모두 `shared_wording` 블록을 top-level 로 expose, preparing/sample 포커스의 evidence body 는 `SHARED_WORDING` 의 body 와 **문자 단위** 일치, Ask AI 의 out-of-scope banner title 은 `shared_wording('out_of_scope')` 와 동일.
- `test_agh_v1_patch_10c_ask_golden_set.py` — in_scope / advice / off_topic / foreign / low-evidence / degraded / hallucinating-LLM 7 분기 골든셋 전부 pass; hallucinate LLM 의 원본 body 가 결과 DTO 로 새어 들어가지 않음을 추가 단언.
- `test_agh_v1_patch_10c_copy_no_leak.py` — 10A/10B 금지 패턴을 계승 + 10C 내부 헬퍼 이름 (`_quantize_position`, `_short_hash`, `classify_question_scope`, `scan_response_for_hallucinations`) 까지 UI/DTO 어느 쪽에도 노출되지 않음, `coherence_signature.fingerprint` 와 `COHERENCE_V1` 은 `strip_engineering_ids` 를 **보존된 채로** 통과함을 확인.

### 11.7 Evidence + Runbook

- `scripts/agh_v1_patch_10c_product_coherence_freeze.py` — 같은 focus (`AAPL/short`) 에 대해 Today / Research-deepdive / Replay / Ask-landing / Ask-quick / Ask-out-of-scope 6 DTO × 2 언어 = **12 파일 + SHA256 manifest** 를 `data/mvp/evidence/screenshots_patch_10c/` 에 저장. manifest 안의 `invariants.{ko,en}.cross_surface_match` 가 `true` 로 나와야 freeze 성공.
- `scripts/agh_v1_patch_10c_product_coherence_runbook.py` — S1..S6 시나리오 (cross-surface coherence / Ask trust closure / UI continuity / DTO refinement / language contract / no-leak+fingerprint) 를 코드 수준 플래그로 검증, 6 개 `s*_ok` + `all_ok` 전부 green.
- 산출 evidence 6: `patch_10c_product_coherence_{runbook,bridge}_evidence.json`, `patch_10c_coherence_evidence.json`, `patch_10c_ask_trust_golden_set_evidence.json`, `patch_10c_cross_surface_alignment_evidence.json`, `patch_10c_language_contract_evidence.json`.

### 11.8 10C 가 **의도적으로** 하지 않은 것

- LLM-end-to-end 품질(예: free-text grounding 의 reasoning 정확도) 은 여전히 "bounded + hallucination-downgrade" 의 **구조적** 보장이지, 결과 품질의 **의미적** 보장이 아니다 — 계속 real golden-set 누적 필요.
- Replay timeline 의 **선형적 시간축 시각화** (오늘 timeline 은 flat list) 는 10C 범위 밖. 지문·초점은 묶었지만 미감은 향후 polish 에서.
- Research tile sparkline 도 여전히 10B 의 대기 상태다 (하지만 10A Today sparkline 패턴은 재사용 가능).
