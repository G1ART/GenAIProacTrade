# Phase 46 evidence — founder decision cockpit

## 확인 체크리스트

- `phase46_bundle_written` / `phase46_review_written` / `phase46_pitch_written` (stdout, `run-phase46-founder-decision-cockpit` 성공 시)
- `docs/operator_closeout/phase46_founder_decision_cockpit_bundle.json` 유효 JSON, `"ok": true`
- 레저 파일 존재: `data/product_surface/alert_ledger_v1.json`, `data/product_surface/decision_trace_ledger_v1.json`
- 단위 테스트: `pytest src/tests/test_phase46_founder_decision_cockpit.py -q`
- 피치에 Phase 43 레거시 권고 토큰 **부재** (`continue_bounded_falsifier_retest_or_narrow_claims_v1` 등)

## 산출물

| 산출물 | 경로 |
|--------|------|
| 번들 | `docs/operator_closeout/phase46_founder_decision_cockpit_bundle.json` |
| Cockpit 리뷰 | `docs/operator_closeout/phase46_founder_decision_cockpit_review.md` |
| 대표 피치 | `docs/operator_closeout/phase46_founder_pitch_surface.md` |

## 실측 클로즈아웃 (저장소 기록)

| 필드 | 값 |
|------|-----|
| `generated_utc` | `2026-04-12T20:40:43.768261+00:00` |
| 입력 Phase 45 | `phase45_canonical_closeout_bundle.json` |
| 입력 Phase 44 | `phase44_claim_narrowing_truthfulness_bundle.json` |
| `founder_read_model.decision_status` | `watching_for_new_evidence` |
| `phase47.phase47_recommendation` | `wire_alert_and_decision_ledgers_to_ui_and_notification_hooks_v1` |

번들의 `input_phase45_bundle_path` / `input_phase44_bundle_path` 는 생성 환경에 따라 **절대경로**로 기록될 수 있다. 감사 시 `docs/operator_closeout/` 상대 경로와 함께 본다.

## 번들 필수 필드 (요지)

`ok`, `phase`, `generated_utc`, `input_phase45_bundle_path`, `input_phase44_bundle_path`, `founder_read_model`, `cockpit_state`, `representative_pitch`, `drilldown_examples`, `alert_ledger_schema`, `decision_trace_ledger_schema`, `ui_surface_contract`, `phase47` (+ 레저 스냅샷·경로)

## Related

`docs/phase46_patch_report.md`, `docs/phase45_evidence.md`, `docs/phase44_evidence.md`, `docs/research_engine_constitution.md`, `HANDOFF.md`
