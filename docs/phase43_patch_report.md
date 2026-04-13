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
  --out-md docs/operator_closeout/phase43_targeted_substrate_backfill_review.md \
  --before-after-audit-out docs/operator_closeout/phase43_targeted_substrate_before_after_audit.md \
  --explanation-out docs/operator_closeout/phase43_explanation_surface_v6.md
```

**주의**: `--out-md …review.md` 와 다음 옵션 사이에 **반드시 공백**(또는 `\` 줄 연속). `…md--before-after…` 처럼 붙이면 `unrecognized arguments` 로 실패한다.

리뷰만 재생성:

```bash
python3 src/main.py write-phase43-targeted-substrate-backfill-review \
  --bundle-in docs/operator_closeout/phase43_targeted_substrate_backfill_bundle.json \
  --out-md docs/operator_closeout/phase43_targeted_substrate_backfill_review.md
```

## 테스트

- `pytest src/tests/test_phase43_targeted_substrate_backfill.py -q` → **13 passed**

## 실측 결과 요약 (2026-04-11)

- **번들**: `phase43_targeted_substrate_backfill_bundle.json`, `generated_utc` `2026-04-11T19:03:56.022392+00:00`, `ok: true`.
- **수리**: filing 8 CIK `run_sample_ingest` (인덱스 업데이트 위주; 번들상 raw/silver 삽입 없음). sector Yahoo 8심볼, 이미 current 8.
- **행 감사**: filing 블로커 **8행 변경 없음**. sector **8행** `no_market_metadata_row_for_symbol` → `sector_field_blank_on_metadata_row`.
- **스코어카드**: filing 7+1 유지; sector 버킷 **no_row 8 → blank 8**.
- **게이트**: `deferred` / `deferred_due_to_proxy_limited_falsifier_substrate` **유지**.
- **digest**: `edfd0b7d36ecb2de` → `285b046cc5bcb307`.
- **번들 내 `phase44` (레거시)**: `continue_bounded_falsifier_retest_or_narrow_claims_v1` — **현재 코호트 운영 가이드가 아님**. 권위 해석·클로즈아웃은 **`docs/phase44_evidence.md`**, **`docs/phase45_evidence.md`** 및 Phase 45 canonical 번들.

상세 표·해석: **`docs/phase43_evidence.md`**.

## 증거 문서

- `docs/phase43_evidence.md`

## Related

`docs/phase42_patch_report.md`, `docs/phase42_evidence.md`, **`docs/phase44_patch_report.md`**, **`docs/phase44_evidence.md`**, **`docs/phase45_patch_report.md`**, **`docs/phase45_evidence.md`**, `HANDOFF.md` (Phase 43 절)
