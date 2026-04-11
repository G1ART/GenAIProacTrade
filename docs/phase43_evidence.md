# Phase 43 evidence — bounded targeted substrate backfill (8-row cohort)

## 확인 체크리스트

- `phase43_bundle_written` / `phase43_review_written` (stdout 태그, `run-phase43-targeted-substrate-backfill` 성공 시)
- `docs/operator_closeout/phase43_targeted_substrate_backfill_bundle.json` 유효 JSON, `"ok": true` (실 run 후)
- 단위 테스트: `pytest src/tests/test_phase43_targeted_substrate_backfill.py -q` → **13 passed** (코호트 8행 잠금·분류·before/after MD·Phase 44 분기·Phase 42 `use_supabase=True` 와이어링; DB 없음)

## 설계 앵커

- **입력**: `docs/operator_closeout/phase42_evidence_accumulation_bundle_supabase.json` 의 `row_level_blockers` **정확히 8행**만 타깃 (유니버스 확장 없음).
- **권위 재실행**: 오케스트레이터는 Phase 42 재호출 시 **`use_supabase=True`** (`phase42_rerun_used_supabase_fresh`); 클로즈아웃에 `--bundle-substrate-only` **사용 안 함**.
- **코호트 (작업지시서)**: `BBY, ADSK, CRM, CRWD, DELL, DUK, NVDA, WMT` — Supabase-fresh 관측 filing은 ADSK만 `only_post_signal_filings_available`, 나머지 `no_10k_10q_rows_for_cik`; sector는 전 행 `no_market_metadata_row_for_symbol` (실 run 후 before/after 번들로 갱신).

## 산출물 (명령이 쓰는 기본 경로)

| 산출물 | 경로 |
|--------|------|
| 번들 | `docs/operator_closeout/phase43_targeted_substrate_backfill_bundle.json` |
| 리뷰 MD | `docs/operator_closeout/phase43_targeted_substrate_backfill_review.md` |
| Before/after 감사 | `docs/operator_closeout/phase43_targeted_substrate_before_after_audit.md` |
| 설명 v6 | `docs/operator_closeout/phase43_explanation_surface_v6.md` |

## 실측 클로즈아웃

**이 문서의 실측 표는 운영자가 Supabase 환경에서 Phase 43을 1회 완주한 뒤 번들·MD로 채운다.** 패치 단계에서는 코드·테스트·HANDOFF만 반영한다.
