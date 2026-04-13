# Phase 45 patch report — canonical operator closeout & reopen protocol

## 목적

Phase 44를 **현재 8행 코호트에 대한 단일 권위 해석**으로 고정하고, Phase 43 번들에 남은 **낙관적 레거시 권고 문자열**을 현재 가이드에서 분리한다. **canonical closeout** 번들·리뷰 한 벌과 **전향적 재진입(reopen) 프로토콜**, **Phase 46** 기본 권고를 산출한다. **신규 기판·DB 캠페인·데이터 백필 없음** (거버넌스·클로즈아웃 전용).

## 코드 변경 요약

| 경로 | 역할 |
|------|------|
| `src/phase45/authoritative_resolver.py` | Phase 44 번들이 Phase 43 중첩 권고를 supersede |
| `src/phase45/closeout_package.py` | 시도·변경/비변경·명시적 unsupported·종결 요약 |
| `src/phase45/reopen_protocol.py` | `observed_material_improvement` vs `reopen_eligibility_on_new_named_source` 구분 |
| `src/phase45/phase46_recommend.py` | 기본 hold-closeout; 선택 플래그 시 bounded reopen 등록 권고 |
| `src/phase45/orchestrator.py`, `review.py` | 번들 조립·리뷰 MD |
| `src/main.py` | `run-phase45-operator-closeout-and-reopen-protocol`, `write-phase45-operator-closeout-and-reopen-protocol-review` |

## CLI

```bash
export PYTHONPATH=src
python3 src/main.py run-phase45-operator-closeout-and-reopen-protocol \
  --phase44-bundle-in docs/operator_closeout/phase44_claim_narrowing_truthfulness_bundle.json \
  --phase43-bundle-in docs/operator_closeout/phase43_targeted_substrate_backfill_bundle.json \
  --bundle-out docs/operator_closeout/phase45_canonical_closeout_bundle.json \
  --out-md docs/operator_closeout/phase45_canonical_closeout_review.md
```

선택: `--operator-registered-new-named-source` — Phase 46에 `register_new_source_then_authorize_one_bounded_reopen_v1` 노출.

리뷰만:

```bash
python3 src/main.py write-phase45-operator-closeout-and-reopen-protocol-review \
  --bundle-in docs/operator_closeout/phase45_canonical_closeout_bundle.json \
  --out-md docs/operator_closeout/phase45_canonical_closeout_review.md
```

## 테스트

```bash
pytest src/tests/test_phase45_operator_closeout_and_reopen_protocol.py -q
```

## 실측 산출 (저장소 기록)

- **번들**: `docs/operator_closeout/phase45_canonical_closeout_bundle.json`
- **`generated_utc` (기록본)**: `2026-04-12T19:18:33.685667+00:00`
- **`ok`**: `true`
- **권위**: `authoritative_resolution.authoritative_phase` = `phase44_claim_narrowing_truthfulness`
- **종결**: `current_closeout_status.current_closeout_status` = `closed_pending_new_evidence`
- **Phase 46 (기본)**: `hold_closeout_until_named_new_source_or_new_evidence_v1`

상세 체크리스트·표: **`docs/phase45_evidence.md`**.

## Related

`docs/phase45_evidence.md`, `docs/phase44_patch_report.md`, `docs/phase44_evidence.md`, `docs/phase43_patch_report.md`, `HANDOFF.md` (Phase 45 절)
