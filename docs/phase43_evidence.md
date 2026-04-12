# Phase 43 evidence — bounded targeted substrate backfill (8-row cohort)

## 확인 체크리스트

- `phase43_bundle_written` / `phase43_review_written` (stdout 태그, `run-phase43-targeted-substrate-backfill` 성공 시)
- `docs/operator_closeout/phase43_targeted_substrate_backfill_bundle.json` 유효 JSON, `"ok": true` — **실측 완료** (`2026-04-11T19:03:56Z`)
- 단위 테스트: `pytest src/tests/test_phase43_targeted_substrate_backfill.py -q` → **13 passed** (코호트 8행 잠금·분류·before/after MD·Phase 44 분기·Phase 42 `use_supabase=True` 와이어링; DB 없음)

## 설계 앵커

- **입력**: `docs/operator_closeout/phase42_evidence_accumulation_bundle_supabase.json` 의 `row_level_blockers` **정확히 8행**만 타깃 (유니버스 확장 없음).
- **권위 재실행**: 오케스트레이터는 Phase 42 재호출 시 **`use_supabase=True`** (`phase42_rerun_used_supabase_fresh`); 클로즈아웃에 `--bundle-substrate-only` **사용 안 함**.
- **Phase 41 번들**: `phase41_bundle_path` 또는 `--phase41-bundle-in` — 픽스처 `residual_join_bucket` 병합용 (`docs/operator_closeout/phase41_falsifier_substrate_bundle.json`).

## 산출물

| 산출물 | 경로 |
|--------|------|
| 번들 | `docs/operator_closeout/phase43_targeted_substrate_backfill_bundle.json` |
| 리뷰 MD | `docs/operator_closeout/phase43_targeted_substrate_backfill_review.md` |
| Before/after 감사 | `docs/operator_closeout/phase43_targeted_substrate_before_after_audit.md` |
| 설명 v6 | `docs/operator_closeout/phase43_explanation_surface_v6.md` |

## 실측 클로즈아웃 (2026-04-11 UTC)

| 필드 | 값 |
|------|-----|
| **번들** | `docs/operator_closeout/phase43_targeted_substrate_backfill_bundle.json` |
| `generated_utc` | `2026-04-11T19:03:56.022392+00:00` |
| `ok` | `true` |
| `universe_name` | `sp500_current` |
| 입력 Phase 42 | `phase42_evidence_accumulation_bundle_supabase.json` |
| Phase 41 사용 | `phase41_falsifier_substrate_bundle.json` |
| `phase42_rerun_used_supabase_fresh` | **`true`** |
| **Phase 41 pit (재실행)** | `experiment_id` **`5ae2780b-5978-4522-b1f5-0ece15844e0f`**, `fixture_row_count` **8**, `ok` **true** |

### 코호트 8행 (Phase 42 입력 블로커 요약)

| symbol | filing (before, Phase 42) | sector (before) |
|--------|---------------------------|-----------------|
| BBY | `no_10k_10q_rows_for_cik` | `no_market_metadata_row_for_symbol` |
| ADSK | `only_post_signal_filings_available` | `no_market_metadata_row_for_symbol` |
| CRM, CRWD, DELL, DUK, NVDA, WMT | `no_10k_10q_rows_for_cik` | `no_market_metadata_row_for_symbol` |

### 한정 수리 (번들 `backfill_actions`)

- **Filing**: `bounded_run_sample_ingest_per_cik` — **8**고유 CIK, CIK당 1회 시도. 샘플 요약: `filing_index_updated` **true** 다수, `filing_index_inserted` / `raw_inserted` / `silver_inserted` **false** (이번 런에서 **좁은 샘플 ingest**가 raw/silver까지 확장하지는 않음).
- **Sector**: `yahoo_chart` — `symbols_requested` **8**, `provider_rows_returned` **8**, `rows_already_current` **8**, `rows_upserted` **0**, `rows_missing_after_requery` **0**.

### 행 단위 before/after (요지, `before_after_row_audit`)

- **Filing 블로커**: 8행 모두 **before = after** (ADSK post-signal 유지, 나머지 `no_10k_10q_rows_for_cik`).
- **Sector 블로커**: 8행 모두 **`no_market_metadata_row_for_symbol` → `sector_field_blank_on_metadata_row`**. 감사 필드상 `raw_row_count`는 전 행 **1**로 before/after 동일 → **“메타 행 부재”에서 “행은 있으나 sector 필드 공백”**으로 **분류만 정밀화**된 것으로 해석.

### Phase 42 스코어카드 (번들 `scorecard_before` → `scorecard_after`)

| 구분 | Before (Phase 42 Supabase 입력 기준) | After (Phase 43 직후 재실행) |
|------|----------------------------------------|------------------------------|
| **filing** | `no_10k_10q_rows_for_cik` **7**, `only_post_signal_filings_available` **1** | **동일** |
| **sector** | `no_market_metadata_row_for_symbol` **8** | **`sector_field_blank_on_metadata_row` 8** |
| `cohort_row_count` | 8 | 8 |

### 게이트·다이제스트

| 필드 | Before | After |
|------|--------|-------|
| `gate_status` | `deferred` | `deferred` |
| `primary_block_category` | `deferred_due_to_proxy_limited_falsifier_substrate` | **동일** |
| `stable_run_digest` | `edfd0b7d36ecb2de` | `285b046cc5bcb307` |

**리뷰어 주의**: `phase42_context.sector_missing_row_count` 등 게이트 집계는 **스코어카드의 세분 sector 코드**와 항상 1:1로 맞지 않을 수 있다. 이번 런에서는 **스코어카드·`before_after_row_audit`** 를 sector 진단의 1차 근거로 본다.

### Phase 44

| 필드 | 값 |
|------|-----|
| `phase44_recommendation` | `continue_bounded_falsifier_retest_or_narrow_claims_v1` |
| 요지 | 스코어카드/행 단위에 **변화**가 있어(특히 sector 버킷·digest) **추가 bounded 재시도 또는 주장 축소** 분기 |

### Phase 42 번들 내 `phase43` (코드 권고, 재실행 산출)

- `substrate_backfill_or_narrow_claims_then_retest_v1` — 문자열 권고는 유지. **운영 의사결정**은 위 **Phase 44**와 **본 문서 표**를 함께 본다.

## 해석 (운영)

1. **Bounded backfill만으로 filing falsifier 품질은 이 코호트에서 개선되지 않음** — ingest가 인덱스 터치에 그쳤고, 10-K/10-Q 관점·시그널 대비 여전히 동일 블로커 코드.
2. **Sector는 “없음”에서 “있으나 비어 있음”으로 관측이 정밀해짐** — 여전히 **usable sector 라벨 없음**; 게이트 카테고리는 동일 유지.
3. **다음**: 광역 기판 금지 전제에서 **추가 bounded 실험**(다른 ingest 깊이·데이터 소스는 별도 설계) vs **주장 축소·한계 문서화** — Phase 44 권고와 정합.

## Related

`docs/phase43_patch_report.md`, `docs/phase42_evidence.md` (§ Supabase fresh), `docs/operator_closeout/phase42_supabase_reviewer_audit.md`, `HANDOFF.md` — Phase 43 절
