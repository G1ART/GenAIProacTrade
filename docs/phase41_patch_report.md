# Phase 41 패치 보고 — falsifier substrate (filing + sector)

## 목적

Phase 40 권고 **`wire_filing_and_sector_substrate_for_hypothesis_falsification_and_explanation_v4`** 에 따라, 광역 수리 없이 **`filing_index`**·**`market_metadata_latest`** 만 연결해 두 패밀리를 재실행한다. 침묵 프록시 금지·행 단위 분류·공통 누수 규칙 유지·게이트 **schema v4**·설명 **v4**·Phase 42 권고.

## 모듈 (`src/phase41/`)

| 모듈 | 역할 |
|------|------|
| `substrate_filing` | 행별 `exact_filing_public_ts_available` / `exact_filing_filed_date_available` / `filing_public_ts_unavailable` |
| `substrate_sector` | `sector_metadata_available` / `sector_metadata_missing` |
| `pit_rerun` | 2패밀리 PIT (`filing_public_ts_strict_pick`, `sector_stratified_signal_pick_v1`) |
| `lifecycle_phase41` | `substrate_audit_log` append |
| `adversarial_phase41` | `phase41_falsifier_substrate_review` 배치 append |
| `promotion_gate_phase41` | v4·`deferred_due_to_proxy_limited_falsifier_substrate` 등 |
| `explanation_v4` | 실기판 vs 프록시 vs before/after |
| `phase42_recommend` | 다음 권고 문자열 |
| `orchestrator`, `review` | 번들·리뷰 MD |

## DB (`src/db/records.py`)

- `fetch_filing_index_rows_for_cik` — Phase 41 filing 기판 조회

## CLI

```bash
export PYTHONPATH=src
python3 src/main.py run-phase41-falsifier-substrate \
  --universe sp500_current \
  --bundle-out docs/operator_closeout/phase41_falsifier_substrate_bundle.json \
  --out-md docs/operator_closeout/phase41_falsifier_substrate_review.md
```

선택: `--phase40-bundle-in docs/operator_closeout/phase40_family_spec_bindings_bundle.json` (before/after 요약)

리뷰만: `write-phase41-falsifier-substrate-review --bundle-in … --out-md …`

(Supabase 필요)

## 테스트 (DB 없음)

```bash
pytest src/tests/test_phase41_substrate.py -q
```

실측 CLI 후 본 저장소에서 **9 passed** 확인.

## 실측 (2026-04-11 UTC)

**번들** `docs/operator_closeout/phase41_falsifier_substrate_bundle.json` (`ok: true`, `generated_utc` `2026-04-11T02:45:40.253079+00:00`).

- **실험** `f85f3524-73eb-4403-bf0e-c347c06d011f`, baseline 런 `223e2aa5…`, 점수 **353**행
- **Filing**: 8행 모두 unavailable·명시적 signal 프록시 8 (롤업은 Phase 40 filing 패밀리와 동일)
- **Sector**: 8행 메타 결손, 스트라텀 전부 `unknown`; 스펙은 `sector_stratified_signal_pick_v1`로 전환(롤업 수치는 동일)
- **누수**: 양 패밀리 통과
- **게이트 v4**: `deferred` / `deferred_due_to_proxy_limited_falsifier_substrate`
- **Phase 42 (코드 권고)**: `accumulate_evidence_and_narrow_hypotheses_under_stronger_falsifiers_v1` — **실측**: `docs/phase42_evidence.md` (`2026-04-11T04:52:28Z`, `--bundle-substrate-only`)

상세 표: **`docs/phase41_evidence.md`**.

## Related

`docs/phase42_patch_report.md`, `docs/phase42_evidence.md` — Phase 41 번들 기반 증거 적층·게이트 phase42.
