# Phase 42 패치 보고 — evidence accumulation (Phase 41 bundle)

## 목적

Phase 41 권고 **`accumulate_evidence_and_narrow_hypotheses_under_stronger_falsifiers_v1`** 에 맞춰, Phase 41 번들의 pit·기판 요약을 입력으로 **블로커 분류·증거 스코어카드·가설 간 outcome 시그니처 비교·축소 라벨·프로모션 게이트(phase 필드 phase42)·설명 v5·Phase 43 권고**를 산출한다. 자동 승격 없음.

## 모듈 (`src/phase42/`)

| 모듈 | 역할 |
|------|------|
| `blocker_taxonomy` | filing/sector 원인 코드 (`classify_filing_blocker_cause`, `classify_sector_blocker_cause`) |
| `evidence_accumulation` | 코호트 추출, 판별 요약, 스코어카드, 번들 재생 행 블로커, `stable_run_digest` |
| `hypothesis_narrowing` | 패밀리별 `narrowing_status`·`narrow_claim_required` 힌트 |
| `promotion_gate_phase42` | schema v4 유지, `phase42_context`, 히스토리 append |
| `explanation_v5` | 스코어카드·판별·게이트·Phase 43 MD |
| `phase43_recommend` | 게이트 카테고리 기반 다음 권고 문자열 |
| `orchestrator`, `review` | 실행·번들·리뷰 MD |

## CLI

```bash
export PYTHONPATH=src
python3 src/main.py run-phase42-evidence-accumulation \
  --phase41-bundle-in docs/operator_closeout/phase41_falsifier_substrate_bundle.json \
  --bundle-substrate-only \
  --research-data-dir data/research_engine \
  --bundle-out docs/operator_closeout/phase42_evidence_accumulation_bundle.json \
  --out-md docs/operator_closeout/phase42_evidence_accumulation_review.md
```

- **Supabase 재조회**: `--bundle-substrate-only` 생략 (fixture 행은 Phase 41 번들 filing 패밀리 `row_results`에서 추출).
- 리뷰만: `write-phase42-evidence-accumulation-review --bundle-in … --out-md …`

### 리뷰어용 감사 (행 표·filing_index 샘플·메타 raw)

운영 `promotion_gate_v1.json` 을 건드리지 않고 Supabase 번들 + 단일 MD를 내려받으려면:

```bash
export PYTHONPATH=src
python3 scripts/export_phase42_supabase_reviewer_audit.py
```

산출: `docs/operator_closeout/phase42_supabase_reviewer_audit.md`, `phase42_evidence_accumulation_bundle_supabase.json`, `phase42_explanation_surface_v5_supabase.md` — 이후 `write-phase42-evidence-accumulation-review --bundle-in …/phase42_evidence_accumulation_bundle_supabase.json --out-md …/phase42_evidence_accumulation_review_supabase.md`.

## 테스트 (DB 없음)

```bash
pytest src/tests/test_phase42_evidence_accumulation.py -q
```

## 실측 (2026-04-11 UTC)

**번들** `docs/operator_closeout/phase42_evidence_accumulation_bundle.json` (`ok: true`, `generated_utc` `2026-04-11T04:52:28.074748+00:00`), **`--bundle-substrate-only`**.

- **스코어카드**: 코호트 8행, filing `only_post_signal_filings_available` 8, sector `no_market_metadata_row_for_symbol` 8
- **게이트**: `deferred` / `deferred_due_to_proxy_limited_falsifier_substrate` (`promotion_gate_v1.json` 갱신)
- **stable_run_digest**: `1cc5113aeff11483`
- **Phase 43**: `substrate_backfill_or_narrow_claims_then_retest_v1`

상세 표·판별 해석: **`docs/phase42_evidence.md`**.

**Supabase fresh** (동일 일 별도 실행): `phase42_evidence_accumulation_bundle_supabase.json` + **`phase42_supabase_reviewer_audit.md`** — `docs/phase42_evidence.md` §「Supabase fresh」표 참고.

## Related

`docs/phase41_patch_report.md`, `docs/research_engine_constitution.md`
