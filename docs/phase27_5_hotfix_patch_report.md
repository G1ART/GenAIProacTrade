# Phase 27.5 hotfix 패치 보고 (corrective)

## 목적

Phase 27 **계측·분기·repair wiring** 오류를 코드로만 바로잡는다. 새 기능 확장이 아니라 **corrective patch**다.

## 수정 요약

| # | 대상 | 내용 |
|---|------|------|
| 1 | `db.records.fetch_cik_map_for_tickers` | `out[ticker]=cik` 대입을 응답 행 루프 **내부**로 이동. 청크당 마지막 행만 남던 버그 제거. |
| 2 | `targeted_backfill.review.build_phase27_evidence_bundle` | `build_revalidation_trigger`의 **평면** 반환과 정합. `_extract_rerun_readiness`, 실패 시 `wiring_warnings`. 번들에 `revalidation_trigger_raw`, `registry_gap_rollup` 추가. |
| 3 | `targeted_backfill.phase28_recommend` | `registry_blocker_total_count` — Phase28 버킷 전부 합산(issuer/factor/norm 등 과소계상 방지). |
| 4 | `targeted_backfill.validation_registry` | `registry_gap_rollup_for_bundle`, `run_validation_registry_repair` 확장: symbol_to_cik_miss·issuer orphan·factor miss·norm/omission 처리, `blocked_actions`/`deferred_actions` 필수. |
| 5 | 오케스트레이터 | `targeted_backfill.repair_closeout` + CLI `run-targeted-backfill-repair-and-review`. 리뷰 MD에 review-only vs repair+review 시맨틱·rollup·wiring 섹션. |
| 6 | 테스트 | `src/tests/test_phase27_5_hotfix.py` (청크 회귀, rerun wiring, rollup, Phase28, repair blocked, 경계). |

## 비목표

워크오더와 동일: 프리미엄·프로덕션 스코어·임계 완화·제네릭 스프린트·UI/백테스트.

## 관련 문서

- 실측 기록: `docs/phase27_5_hotfix_evidence.md`
- Phase 27 본패치 보고: `docs/phase27_patch_report.md` (27.5 절 교차 참조)
