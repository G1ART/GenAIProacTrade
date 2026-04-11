# Phase 41 evidence — falsifier substrate (filing + sector)

## 확인 체크리스트

- `phase41_bundle_written` / `phase41_review_written` (stdout 태그)
- `docs/operator_closeout/phase41_falsifier_substrate_bundle.json` 유효 JSON, `"ok": true`
- 단위 테스트: `pytest src/tests/test_phase41_substrate.py -q` → **9 passed** (기판 분류·게이트 v4·Phase 42 권고 문자열; DB 없음)

## 실측 클로즈아웃

**명령**: `run-phase41-falsifier-substrate --universe sp500_current` (번들·리뷰·설명 v4 경로는 `docs/phase41_patch_report.md` CLI 절 참고)

**근거 번들**: `docs/operator_closeout/phase41_falsifier_substrate_bundle.json`  
**리뷰 MD**: `docs/operator_closeout/phase41_falsifier_substrate_review.md`  
**설명 v4**: `docs/operator_closeout/phase41_explanation_surface_v4.md`

| 필드 | 값 |
|------|-----|
| `generated_utc` | `2026-04-11T02:45:40.253079+00:00` |
| `pit_execution.experiment_id` | `f85f3524-73eb-4403-bf0e-c347c06d011f` |
| `pit_execution.generated_utc` | `2026-04-11T02:45:40.250605+00:00` |
| `universe_name` | `sp500_current` |
| `pit_execution.fixture_row_count` | **8** |
| `pit_execution.baseline_run_id` | `223e2aa5-3879-4dee-b28f-3d579cbf4cbd` |
| `pit_execution.scores_loaded.baseline` | **353** |
| 재실행 패밀리 | **2** (`signal_filing_boundary_v1`, `issuer_sector_reporting_cadence_v1`) |
| `all_families_leakage_passed` | **true** |
| **Filing 기판** (`filing_substrate.summary`) | 8행 전부 `filing_public_ts_unavailable` · `rows_with_explicit_signal_proxy` **8** (`filing_index` 조회 후에도 신호일 이전 적격 10-K/10-Q 미선택 → 명시적 signal 프록시) |
| **Sector 기판** (`sector_substrate.summary`) | 8행 전부 `sector_metadata_missing` · `distinct_sector_labels` **[]** (`market_metadata_latest`에 픽스처 심볼 `sector` 없음) |
| Outcome 롤업 (양 패밀리) | 각 spec **`still_join_key_mismatch` 8**; 그 외 버킷 0 |
| 섹터 스트라텀 (`sector_stratum_outcome_counts`) | **`unknown`만** 8행 |
| **Phase 40 대비** (`family_rerun_before_after`) | Filing: 롤업 동일·`unchanged_rollups` **true**. Issuer sector: spec `stratified_fixture_only_replay` → `sector_stratified_signal_pick_v1`, 숫자는 동일(8 mismatch), `unchanged_rollups` **false** (스펙 키 변경) |
| `lifecycle_status_distribution` | `challenged` **1**, `conditionally_supported` **4** (상태 필드 자체는 Phase 40과 동일; 가설에 `substrate_audit_log` append) |
| `promotion_gate_phase41.gate_status` | `deferred` |
| `promotion_gate_phase41.primary_block_category` | `deferred_due_to_proxy_limited_falsifier_substrate` |
| `promotion_gate_phase41.schema_version` | **4** |
| `phase42_recommendation` | `accumulate_evidence_and_narrow_hypotheses_under_stronger_falsifiers_v1` |

### 해석 (운영)

- **코드 경로는 정상**: filing·메타 조회·누수 감사·번들·게이트 v4·설명 v4·영속 JSON 갱신이 한 사이클로 완결됨.
- **이번 DB 스냅샷**에서는 반증 강도가 아직 **프록시/결손**에 머물러 게이트가 `deferred_due_to_proxy_limited_falsifier_substrate`로 분류됨. filing 쪽은 인덱스에 행이 있어도 **규칙(10-K/10-Q, `filed_at` ≤ signal)** 을 만족하는 후보가 없으면 unavailable로 남김.
- **다음**: Phase 42 권고대로 증거 축적·가설 축소·설명/거버넌스 정교화(광역 기판 스프린트 비목표).

## 산출·영속

- `docs/operator_closeout/phase41_falsifier_substrate_bundle.json`
- `docs/operator_closeout/phase41_falsifier_substrate_review.md`
- `docs/operator_closeout/phase41_explanation_surface_v4.md`
- `data/research_engine/hypotheses_v1.json` (`substrate_audit_log`)
- `data/research_engine/adversarial_reviews_v1.json` (Phase 41 배치 append)
- `data/research_engine/promotion_gate_v1.json`, `promotion_gate_history_v1.json`

## Related

`docs/phase41_patch_report.md`, `docs/phase40_evidence.md`, **`docs/phase42_evidence.md`** (증거 적층·게이트 phase42), `HANDOFF.md`
