# Phase 44 patch report — claim narrowing & audit truthfulness

## 목적

Phase 43 혼합 출처 before/after 표 문제를 **출처 분리(provenance)** 로 보완하고, sector **blank-field만**의 스코어카드 이동을 **material falsifier 개선으로 보지 않는** 보수적 규칙을 적용한다. **머신 리더블 claim narrowing**, **retry 레지스트리**(신규 명명 경로), Phase 44 번들 내 **`phase45`** 권고 블록을 산출한다. **광역 기판·DB 캠페인 없음** (번들 입력만).

## 코드 변경 요약

| 경로 | 역할 |
|------|------|
| `src/phase44/provenance_audit.py` | `input_bundle_before` vs runtime before/after |
| `src/phase44/audit_render.py` | `phase44_provenance_audit.md` |
| `src/phase44/recommendation_truth.py` | material 판정 (exact_ts·sector_available·게이트·판별) |
| `src/phase44/claim_narrowing.py`, `retry_eligibility.py` | 패밀리/코호트 한계·retry 조건 |
| `src/phase44/phase45_recommend.py` | 번들에 넣을 Phase 45 권고 문자열 (truthfulness 레이어) |
| `src/phase44/orchestrator.py`, `review.py` | 번들·리뷰·설명 v7 |
| `src/main.py` | `run-phase44-claim-narrowing-truthfulness`, `write-phase44-claim-narrowing-truthfulness-review` |

## CLI

```bash
export PYTHONPATH=src
python3 src/main.py run-phase44-claim-narrowing-truthfulness \
  --phase43-bundle-in docs/operator_closeout/phase43_targeted_substrate_backfill_bundle.json \
  --phase42-supabase-bundle-in docs/operator_closeout/phase42_evidence_accumulation_bundle_supabase.json \
  --bundle-out docs/operator_closeout/phase44_claim_narrowing_truthfulness_bundle.json \
  --out-md docs/operator_closeout/phase44_claim_narrowing_truthfulness_review.md \
  --audit-out docs/operator_closeout/phase44_provenance_audit.md \
  --explanation-out docs/operator_closeout/phase44_explanation_surface_v7.md
```

## 테스트

```bash
pytest src/tests/test_phase44_claim_narrowing_truthfulness.py -q
```

## 실측 산출 (저장소 기록)

- **번들**: `docs/operator_closeout/phase44_claim_narrowing_truthfulness_bundle.json`
- **`generated_utc` (기록본)**: `2026-04-12T06:44:44.839337+00:00`
- **`ok`**: `true`
- **요지**: `material_falsifier_improvement: false`, `optimistic_sector_relabel_only: true`, `phase45.phase45_recommendation` = `narrow_claims_document_proxy_limits_operator_closeout_v1`

운영 **단일 클로즈아웃 패키지**는 Phase 45 번들을 추가로 본다: **`docs/phase45_evidence.md`**.

## Related

`docs/phase44_evidence.md`, `docs/phase45_patch_report.md`, `docs/phase43_patch_report.md`, `HANDOFF.md` (Phase 44 절)
