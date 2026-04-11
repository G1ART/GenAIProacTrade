# Phase 42 — Supabase 리뷰어 감사 패키지

**체크리스트 대응**: (1) 아래 §1 + `phase42_evidence_accumulation_bundle_supabase.json` · (2) §2 표 · (3) §3 filing 샘플 · (4) §4 메타 진단.

_생성 UTC: `2026-04-11T05:54:32.711655+00:00`_
_입력 Phase 41 번들: `docs/operator_closeout/phase41_falsifier_substrate_bundle.json`_

## 1. Phase 42 (Supabase fresh, `blocker_replay_source: supabase_fresh`)

- **번들 JSON**: `docs/operator_closeout/phase42_evidence_accumulation_bundle_supabase.json` (게이트·히스토리 쓰기는 임시 디렉터리에만 수행 후 폐기)
- **리뷰 MD**: `docs/operator_closeout/phase42_evidence_accumulation_review_supabase.md`
- **설명 v5 (이 실행)**: `docs/operator_closeout/phase42_explanation_surface_v5_supabase.md`

```json
{
  "ok": true,
  "generated_utc": "2026-04-11T05:54:33.329066+00:00",
  "stable_run_digest": "edfd0b7d36ecb2de",
  "family_evidence_scorecard": {
    "cohort_label": "phase41_fixture_row_results",
    "cohort_row_count": 8,
    "filing_blocker_distribution": {
      "no_10k_10q_rows_for_cik": 7,
      "only_post_signal_filings_available": 1
    },
    "sector_blocker_distribution": {
      "no_market_metadata_row_for_symbol": 8
    },
    "phase41_families": [
      "signal_filing_boundary_v1",
      "issuer_sector_reporting_cadence_v1"
    ],
    "outcome_discriminating_family_count": 2,
    "identical_rollup_groups": []
  },
  "promotion_gate_primary_block_category": "deferred_due_to_proxy_limited_falsifier_substrate"
}
```

## 2. Row-level blockers (Supabase 분류, 동일 로직 as orchestrator)

| symbol | cik | signal_available_date | filing_blocker_cause | sector_blocker_cause | blocker_replay_source |
| --- | --- | --- | --- | --- | --- |
| BBY | 0000764478 | 2025-12-08 | no_10k_10q_rows_for_cik | no_market_metadata_row_for_symbol | supabase_fresh |
| ADSK | 0000769397 | 2025-11-27 | only_post_signal_filings_available | no_market_metadata_row_for_symbol | supabase_fresh |
| CRM | 0001108524 | 2025-12-04 | no_10k_10q_rows_for_cik | no_market_metadata_row_for_symbol | supabase_fresh |
| CRWD | 0001535527 | 2025-12-03 | no_10k_10q_rows_for_cik | no_market_metadata_row_for_symbol | supabase_fresh |
| DELL | 0001571996 | 2025-12-10 | no_10k_10q_rows_for_cik | no_market_metadata_row_for_symbol | supabase_fresh |
| DUK | 0001326160 | 2025-11-10 | no_10k_10q_rows_for_cik | no_market_metadata_row_for_symbol | supabase_fresh |
| NVDA | 0001045810 | 2025-11-20 | no_10k_10q_rows_for_cik | no_market_metadata_row_for_symbol | supabase_fresh |
| WMT | 0000104169 | 2025-12-04 | no_10k_10q_rows_for_cik | no_market_metadata_row_for_symbol | supabase_fresh |

## 3. `filing_index` — 10-K/10-Q 신호일 전·후 샘플

### BBY (CIK `0000764478`, signal `2025-12-08`)

- `filing_index` 행 수 (limit 200, 전 form): **10**

**on_or_before_signal** (10-K/10-Q, 최대 0행)

_해당 없음_

**after_signal** (10-K/10-Q, 최대 0행)

_해당 없음_

### ADSK (CIK `0000769397`, signal `2025-11-27`)

- `filing_index` 행 수 (limit 200, 전 form): **10**

**on_or_before_signal** (10-K/10-Q, 최대 0행)

_해당 없음_

**after_signal** (10-K/10-Q, 최대 1행)

| form | filed_at | accepted_at | accession_no |
| --- | --- | --- | --- |
| 10-K | 2026-03-03T00:00:00+00:00 | 2026-03-03T16:06:39+00:00 | 0000769397-26-000015 |

### CRM (CIK `0001108524`, signal `2025-12-04`)

- `filing_index` 행 수 (limit 200, 전 form): **10**

**on_or_before_signal** (10-K/10-Q, 최대 0행)

_해당 없음_

**after_signal** (10-K/10-Q, 최대 0행)

_해당 없음_

### CRWD (CIK `0001535527`, signal `2025-12-03`)

- `filing_index` 행 수 (limit 200, 전 form): **10**

**on_or_before_signal** (10-K/10-Q, 최대 0행)

_해당 없음_

**after_signal** (10-K/10-Q, 최대 0행)

_해당 없음_

### DELL (CIK `0001571996`, signal `2025-12-10`)

- `filing_index` 행 수 (limit 200, 전 form): **10**

**on_or_before_signal** (10-K/10-Q, 최대 0행)

_해당 없음_

**after_signal** (10-K/10-Q, 최대 0행)

_해당 없음_

### DUK (CIK `0001326160`, signal `2025-11-10`)

- `filing_index` 행 수 (limit 200, 전 form): **10**

**on_or_before_signal** (10-K/10-Q, 최대 0행)

_해당 없음_

**after_signal** (10-K/10-Q, 최대 0행)

_해당 없음_

### NVDA (CIK `0001045810`, signal `2025-11-20`)

- `filing_index` 행 수 (limit 200, 전 form): **6**

**on_or_before_signal** (10-K/10-Q, 최대 0행)

_해당 없음_

**after_signal** (10-K/10-Q, 최대 0행)

_해당 없음_

### WMT (CIK `0000104169`, signal `2025-12-04`)

- `filing_index` 행 수 (limit 200, 전 form): **12**

**on_or_before_signal** (10-K/10-Q, 최대 0행)

_해당 없음_

**after_signal** (10-K/10-Q, 최대 0행)

_해당 없음_

## 4. `market_metadata_latest` — 행 존재·sector·industry

### BBY (CIK `0000764478`)

- **raw_row_count**: 0
- **diagnostic**: `no_rows_in_table`
- **taxonomy** (`classify_sector_blocker_cause` on picked row): `no_market_metadata_row_for_symbol`
- **picked**: _없음_

### ADSK (CIK `0000769397`)

- **raw_row_count**: 0
- **diagnostic**: `no_rows_in_table`
- **taxonomy** (`classify_sector_blocker_cause` on picked row): `no_market_metadata_row_for_symbol`
- **picked**: _없음_

### CRM (CIK `0001108524`)

- **raw_row_count**: 0
- **diagnostic**: `no_rows_in_table`
- **taxonomy** (`classify_sector_blocker_cause` on picked row): `no_market_metadata_row_for_symbol`
- **picked**: _없음_

### CRWD (CIK `0001535527`)

- **raw_row_count**: 0
- **diagnostic**: `no_rows_in_table`
- **taxonomy** (`classify_sector_blocker_cause` on picked row): `no_market_metadata_row_for_symbol`
- **picked**: _없음_

### DELL (CIK `0001571996`)

- **raw_row_count**: 0
- **diagnostic**: `no_rows_in_table`
- **taxonomy** (`classify_sector_blocker_cause` on picked row): `no_market_metadata_row_for_symbol`
- **picked**: _없음_

### DUK (CIK `0001326160`)

- **raw_row_count**: 0
- **diagnostic**: `no_rows_in_table`
- **taxonomy** (`classify_sector_blocker_cause` on picked row): `no_market_metadata_row_for_symbol`
- **picked**: _없음_

### NVDA (CIK `0001045810`)

- **raw_row_count**: 0
- **diagnostic**: `no_rows_in_table`
- **taxonomy** (`classify_sector_blocker_cause` on picked row): `no_market_metadata_row_for_symbol`
- **picked**: _없음_

### WMT (CIK `0000104169`)

- **raw_row_count**: 0
- **diagnostic**: `no_rows_in_table`
- **taxonomy** (`classify_sector_blocker_cause` on picked row): `no_market_metadata_row_for_symbol`
- **picked**: _없음_
