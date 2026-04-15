# Message Layer v1 — API contract (stub)

`GET /api/today/spectrum` 응답의 각 `rows[]` 항목에 **`message`** 객체가 포함됩니다.  
시드 `data/mvp/today_spectrum_seed_v1.json`에 `message` 블록이 있으면 그대로 병합하고, 없으면 `rationale_summary`·`what_changed`로 최소 메시지를 생성합니다.

## 필드 (`message`)

| 필드 | 설명 |
|------|------|
| `message_id` | 안정적인 데모 ID |
| `asset_id` | 종목/객체 ID |
| `horizon` | `short` \| `medium` \| `medium_long` \| `long` |
| `headline` | 카드 상단 한 줄 (제품 메시지) |
| `one_line_take` | 한 줄 해석 |
| `why_now` | 왜 지금인지 |
| `what_changed` | 무엇이 바뀌었는지 |
| `what_remains_unproven` | 아직 열린 질문 |
| `what_to_watch` | 다음 관찰 포인트 |
| `action_frame` | buy/sell 대신 관심/경계/검토 프레이밍 |
| `confidence_band` | 해석 강도 |
| `linked_model_family` | 해당 시간축 활성 모델군 |
| `linked_evidence_summary` | 근거 한 줄 (시드) |

## 행 레벨 스펙트럼

- `spectrum_band`: `left` \| `center` \| `right` — `spectrum_position` 0~1 구간의 UI 색 밴드.

## 가격 오버레이 mock

`GET /api/today/spectrum?...&mock_price_tick=0|1`

- `0`(기본): 시드 스펙트럼 위치 그대로.
- `1`: **0–1 축 반전**으로 순위·밴드가 바뀌는 것을 시연(실시간 시세 아님). 응답에 `mock_price_tick_note` 포함.

`GET /api/home/feed` 는 **`today_spectrum_summary`**(단기 상위 2건 메시지)를 첨부할 수 있음 — 시드가 있을 때만.

`today_spectrum_ui` (Sprint 3): **`watchlist_asset_ids`**(번들 그대로), **`watchlist_spectrum_filter_ids`**(선택 별칭 확장), **`spectrum_seed_asset_ids`**, **`watchlist_on_spectrum`** / **`watchlist_on_spectrum_aliased`**. 별칭 파일: `data/mvp/today_spectrum_watch_aliases_v1.json` (`aliases`: 번들 id/심볼 → 시드 `asset_id`).

## 종목 상세 (Sprint 4 — Message → Information → Research)

`GET /api/today/object?asset_id=DEMO_KR_A&horizon=short|…&mock_price_tick=0|1&lang=`

- `message`: 스펙트럼 행과 동일한 메시지 객체.
- `information`: `supporting_signals`·`opposing_signals`(문자열 배열), `evidence_summary`, `data_layer_note` — 시드 `information_layer`가 있으면 사용, 없으면 스펙트럼 행으로 최소 생성.
- `research`: `deeper_rationale`, `model_family_context`, `links.prefill_ask_ai` 등 — 시드 `research_layer` 또는 폴백.

구현: `src/phase47_runtime/message_layer_v1.py`, `today_spectrum.py`.
