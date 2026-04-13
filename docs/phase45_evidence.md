# Phase 45 evidence — canonical closeout & reopen protocol

## 확인 체크리스트

- `phase45_bundle_written` / `phase45_review_written` (stdout 태그, `run-phase45-operator-closeout-and-reopen-protocol` 성공 시)
- `docs/operator_closeout/phase45_canonical_closeout_bundle.json` 유효 JSON, `"ok": true`
- 단위 테스트: `pytest src/tests/test_phase45_operator_closeout_and_reopen_protocol.py -q`

## 설계 앵커

- **입력**: Phase 44 `phase44_claim_narrowing_truthfulness_bundle.json` + Phase 43 `phase43_targeted_substrate_backfill_bundle.json` — **DB 없음**, **기판 수리 없음**.
- **권위**: Phase 44가 Phase 43 번들 내 `phase44.phase44_recommendation` 등 **레거시 낙관 권고**를 현재 가이드에서 **supersede** (`authoritative_resolution.superseded_recommendations`).
- **단일 클로즈아웃**: 운영자는 **`canonical_closeout`** + **`phase45_canonical_closeout_review.md`** 를 8행 코호트 종결의 한 벌로 본다.

## 산출물

| 산출물 | 경로 |
|--------|------|
| 번들 | `docs/operator_closeout/phase45_canonical_closeout_bundle.json` |
| 리뷰 MD | `docs/operator_closeout/phase45_canonical_closeout_review.md` |

## 실측 클로즈아웃 (저장소 기록)

| 필드 | 값 |
|------|-----|
| **번들** | `docs/operator_closeout/phase45_canonical_closeout_bundle.json` |
| `generated_utc` | `2026-04-12T19:18:33.685667+00:00` |
| `ok` | `true` |
| 입력 Phase 44 | `phase44_claim_narrowing_truthfulness_bundle.json` |
| 입력 Phase 43 | `phase43_targeted_substrate_backfill_bundle.json` |

### Authoritative resolution (요지)

| 필드 | 값 |
|------|-----|
| `authoritative_phase` | `phase44_claim_narrowing_truthfulness` |
| `authoritative_recommendation` | `narrow_claims_document_proxy_limits_operator_closeout_v1` |
| Superseded (예시) | `phase43` … `phase44.phase44_recommendation` → `continue_bounded_falsifier_retest_or_narrow_claims_v1` (**비권위**) |

### Canonical closeout (요지)

- **코호트**: 8행 — BBY, ADSK, CRM, CRWD, DELL, DUK, NVDA, WMT (번들 `canonical_closeout.cohort.rows`)
- **시도**: filing `bounded_run_sample_ingest_per_cik`; sector `yahoo_chart` (Phase 43와 동일 참조)
- **변경**: sector 진단 no_row → blank-field; digest 전후 변화 (실행 기록)
- **비변경**: filing 스코어카드 집계, `sector_available`, 게이트, 판별 롤업 개선 없음
- **명시적 unsupported**: 번들 `canonical_closeout.explicit_unsupported_interpretations`
- **재개 조건**: `future_reopen_protocol` — 명명 소스·Phase 43 경로와의 차이·8행 상한·원샷 bounded

### Phase 46 (기본)

| 필드 | 값 |
|------|-----|
| `phase46_recommendation` | `hold_closeout_until_named_new_source_or_new_evidence_v1` |

## Related

`docs/phase45_patch_report.md`, `docs/phase44_evidence.md`, `docs/phase43_evidence.md`, **`docs/phase46_evidence.md`**, `HANDOFF.md` — Phase 45 절
