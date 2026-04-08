# Phase 31 패치 보고 — Raw-facts bridge after filing-index repair

## 목적

Phase 30 filing-index 수리 후 노출된 **`filing_index_present_no_raw_facts`** seam 을 `raw_xbrl_facts` 경로로 메우고, **GIS**류 silver 미매핑(`raw_rows_unmapped_to_silver`)을 개념명 정규화로 완화하며, **NWSA**류 `issuer_mapping_gap` 에 대해 안전할 때만 `issuer_master` 를 결정적으로 보강한다. 메타·임계·15/16·프리미엄·스코어 비목표.

## 수정 요약

| # | 영역 | 내용 |
|---|------|------|
| 1 | `sec.facts.concept_map` | `normalize_concept_key_for_mapping` — `us-gaap_*` / `dei_*` / `ifrs-full_*` → 콜론 형식; `map_source_concept` 가 정규화 키를 우선 조회. |
| 2 | `phase30.filing_index_gaps` | 수리 성공 행에 `quarter_snapshot_class_after_filing_ingest`·`raw_xbrl_present_after`·`issuer_quarter_snapshot_count_after` 부여; **`filing_index_repaired_now`**·분리 카운트·`repaired_now_semantics` 명시. |
| 3 | `phase30.empty_cik_cleanup` | `issuer_mapping_gap` 진단에 `membership_cik`·`registry_cik` 항상 채움; 맵 불일치 시 `detail=issuer_map_cik_mismatch`. |
| 4 | `phase31.raw_facts_gaps` | `report_raw_facts_gap_targets` / `export_*` / `classify_raw_facts_gap_detail`(sec 파이프만 있음·완전 공백 등). |
| 5 | `phase31.raw_facts_repair` | `run_raw_facts_backfill_repair` — `run_facts_extract_for_ticker`, CIK 정합, 분류 before/after. |
| 6 | `phase31.silver_seam_repair` | GIS 우선 `raw_present_no_silver_facts` 재처리 + 스냅샷 + CIK 단위 하류. |
| 7 | `phase31.issuer_mapping_repair` | `run_deterministic_empty_cik_issuer_repair`. |
| 8 | `phase31.orchestrator` | 전후 스냅샷 + raw·silver·issuer + raw/issuer 터치 CIK에만 추가 하류 retry. |
| 9 | `phase31.phase32_recommend` | 번들 `phase32`. |
| 10 | `main.py` | 위 CLI. |
| 11 | `src/tests/test_phase31_raw_facts_bridge.py` | 분류·수리·concept·리뷰. |

## 산출물

- `docs/operator_closeout/phase31_raw_facts_bridge_review.md`
- `docs/operator_closeout/phase31_raw_facts_bridge_bundle.json`

## 재현 예시

```bash
PYTHONPATH=src python3 -u src/main.py run-phase31-raw-facts-bridge-repair \
  --universe sp500_current \
  --panel-limit 8000 \
  --out-md docs/operator_closeout/phase31_raw_facts_bridge_review.md \
  --bundle-out docs/operator_closeout/phase31_raw_facts_bridge_bundle.json
```
