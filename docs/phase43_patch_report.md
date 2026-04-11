# Phase 43 patch report — bounded falsifier substrate backfill

## 목적

Phase 42 **Supabase-fresh** 번들에 고정된 **8행** falsifier 코호트에 대해 filing_index·`market_metadata_latest` 만 **상한** 보강한 뒤, Phase 41 pit 재실행 → Phase 42를 **Supabase-fresh**로 재실행한다. public-core·광역 기판 스프린트 **비목표**.

## 코드 변경 요약

- **`src/phase43/`**: `target_cohort` (8행 강제), `filing_audit` / `filing_backfill`, `sector_audit` / `sector_backfill`, `before_after_audit`, `orchestrator`, `review`, `explanation_v6`, `phase44_recommend`.
- **`src/main.py`**: `run-phase43-targeted-substrate-backfill`, `write-phase43-targeted-substrate-backfill-review` 및 `argparse` 서브커맨드.

## CLI

```bash
export PYTHONPATH=src
python3 src/main.py run-phase43-targeted-substrate-backfill \
  --phase42-supabase-bundle-in docs/operator_closeout/phase42_evidence_accumulation_bundle_supabase.json \
  --bundle-out docs/operator_closeout/phase43_targeted_substrate_backfill_bundle.json \
  --out-md docs/operator_closeout/phase43_targeted_substrate_backfill_review.md
```

리뷰만 재생성:

```bash
python3 src/main.py write-phase43-targeted-substrate-backfill-review \
  --bundle-in docs/operator_closeout/phase43_targeted_substrate_backfill_bundle.json \
  --out-md docs/operator_closeout/phase43_targeted_substrate_backfill_review.md
```

## 테스트

- `pytest src/tests/test_phase43_targeted_substrate_backfill.py -q`

## 증거 문서

- `docs/phase43_evidence.md`
