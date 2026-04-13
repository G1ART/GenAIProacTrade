# Phase 44 evidence — claim narrowing & audit truthfulness

## 확인 체크리스트

- `phase44_bundle_written` / `phase44_review_written` (stdout 태그, `run-phase44-claim-narrowing-truthfulness` 성공 시)
- `docs/operator_closeout/phase44_claim_narrowing_truthfulness_bundle.json` 유효 JSON, `"ok": true`
- 단위 테스트: `pytest src/tests/test_phase44_claim_narrowing_truthfulness.py -q`

## 설계 앵커

- **입력**: Phase 43 타깃 번들 + Phase 42 Supabase 번들 — **DB 없음**.
- **Provenance**: 행별 `input_bundle_before` vs `runtime_snapshot_before_repair` / `after_repair` (Phase 43 `before_after_row_audit` 메트릭 기반).
- **Truthfulness**: `no_market_metadata_row_for_symbol` → `sector_field_blank_on_metadata_row` **단독**은 material 개선으로 처리하지 않음 (`phase44_truthfulness_assessment`).

## 산출물

| 산출물 | 경로 |
|--------|------|
| 번들 | `docs/operator_closeout/phase44_claim_narrowing_truthfulness_bundle.json` |
| 리뷰 MD | `docs/operator_closeout/phase44_claim_narrowing_truthfulness_review.md` |
| Provenance 감사 | `docs/operator_closeout/phase44_provenance_audit.md` |
| 설명 v7 | `docs/operator_closeout/phase44_explanation_surface_v7.md` |

## 실측 클로즈아웃 (저장소 기록)

| 필드 | 값 |
|------|-----|
| **번들** | `docs/operator_closeout/phase44_claim_narrowing_truthfulness_bundle.json` |
| `generated_utc` | `2026-04-12T06:44:44.839337+00:00` |
| `ok` | `true` |
| 입력 Phase 43 | `phase43_targeted_substrate_backfill_bundle.json` |
| 입력 Phase 42 | `phase42_evidence_accumulation_bundle_supabase.json` |

### Truthfulness (요지)

| 필드 | 값 (실측 기록) |
|------|----------------|
| `material_falsifier_improvement` | `false` |
| `optimistic_sector_relabel_only` | `true` |
| `gate_materially_improved` | `false` |
| `discrimination_rollups_improved` | `false` |

### Phase 44 번들 내 `phase45` (다음 조치 문자열)

| 필드 | 값 |
|------|-----|
| `phase45_recommendation` | `narrow_claims_document_proxy_limits_operator_closeout_v1` |

**운영 권위·레거시 supersede·재진입 규칙**은 **Phase 45** `phase45_canonical_closeout_bundle.json` — **`docs/phase45_evidence.md`**. **파운더 대면 cockpit**은 **Phase 46** — **`docs/phase46_evidence.md`**.

## Related

`docs/phase44_patch_report.md`, `docs/phase45_evidence.md`, **`docs/phase46_evidence.md`**, `docs/phase43_evidence.md`, `HANDOFF.md` — Phase 44 절
