# Residual Score Semantics v1 (Pragmatic Brain Absorption v1 — Milestone B)

## 범위

- 이 문서는 **Residual Score / Band / Invalidation / Recheck** 필드를 `spectrum_rows_by_horizon[*]` 항목과 `MessageObjectV1`에서 같은 의미로 쓰기 위한 **단일 계약**이다.
- 완벽한 통계 모형을 정의하지 않는다 (작업지시서 §6 — "완벽한 수학" 금지). 대신 **현재 브레인 산출물에서 결정적으로 계산되는 최소 항**만 고정한다.
- 기존 MVP 스펙 Q1–Q10 (`print-mvp-spec-survey`)과 **충돌하지 않는다**: 모든 신규 필드는 optional이며, 없을 때 default는 빈 문자열이다.

## 필드 정의

| 필드 | 위치 | 의미 | 결정 규칙 |
|------|------|------|-----------|
| `spectrum_position` (`[0,1]`) | spectrum row (기존) | 스펙트럼 상의 위치. 0 = compressed, 1 = stretched. | 기존 `build_spectrum_rows_from_validation`의 `position` 규칙 유지. |
| `confidence_band` (`low\|medium\|high`) | spectrum row + MessageObject | 팩터-검증 슬라이스의 valid 표본 수 근거 confidence. | `_confidence_band_from_sample`의 임계(24, 96) 유지. |
| `residual_score_semantics_version` | spectrum row (optional) | 이 계약의 버전 태그. | 고정 문자열 `"residual_semantics_v1"`. |
| `invalidation_hint` | spectrum row (optional) + MessageObject (optional) | "이 신호가 무효화될 조건"을 **결정적 스트링**으로. Replay / memory에 동일 key로 남길 수 있어야 함. | 아래 § Invalidation Rule 참조. |
| `recheck_cadence` | spectrum row (optional) + MessageObject (optional) | 이 신호를 다시 확인할 기본 주기. | 아래 § Recheck Rule 참조. |
| `what_remains_unproven` (기존) | MessageObject | residual이 **아직 설명하지 못한 부분**을 한 문장으로. | 기존 Product Spec §6.4 유지. |

## Invalidation Rule

결정적 문자열. 자유 서술 금지(작업지시서 §6). 아래 규칙 중 **가장 구체적인 하나**를 선택해 `invalidation_hint`에 담는다.

1. `horizon_returns_reverse_sign`: 해당 bundle horizon의 forward-return이 **부호 반전**으로 관측되면 무효.
2. `spectrum_position_crosses_midline`: 다음 재계산에서 `spectrum_position`이 0.5 기준 **반대 방향**으로 가로지르면 무효.
3. `confidence_band_drops_to_low`: 동일 (factor, horizon, universe) 조합의 `confidence_band`가 `low`로 떨어지면 무효.
4. `factor_validation_pit_fail`: PIT 인증이 떨어지면 (`pit_pass=False`) 즉시 무효.

기본값(다른 모든 규칙 미충족): `horizon_returns_reverse_sign`.

## Recheck Rule

결정적 문자열. `bundle_horizon`에 따라 아래 매핑.

| bundle_horizon | recheck_cadence |
|----------------|-----------------|
| `short` | `"monthly_after_new_filing_or_21_trading_days"` |
| `medium` | `"quarterly_after_new_filing_or_63_trading_days"` |
| `medium_long` | `"semi_annually_after_new_filing_or_126_trading_days"` |
| `long` | `"annually_after_new_filing_or_252_trading_days"` |

## 스키마 합류

- `spectrum_rows_from_validation_v1`: 위 optional 필드를 결정적으로 채운다.
- `MessageObjectV1`: `invalidation_hint` / `recheck_cadence` / `residual_score_semantics_version` 를 optional string 필드로 추가 (기본 `""`). Product Spec §6.4의 기존 필수 필드는 그대로.
- Bundle integrity (`validate_active_registry_integrity`) 는 영향받지 않는다 (필수 필드 변경 없음).
- `print-mvp-spec-survey`는 영향받지 않는다 (Q1–Q10 판단 조건에 신규 필드 없음).

## 비목표

- 잔차의 통계적 분포 추정, 모델 불확실성, 베이지안 업데이트 — 범위 밖.
- AI-generated 자유 서술 narrative을 Replay 의사결정 요약에 직접 삽입 — 금지 (§6).

---

## Product Shell Connection (Patch 11, 2026-04-23)

위 계약은 Brain 내부 semantics 다. Patch 11 이 이 계약을 **Product Shell 의 네 고객 표면** (Today / Research / Replay / Ask AI) 으로 흘려보낸다. 원칙: **raw slug 은 제품 DTO 에 한 글자도 유출되지 않는다.** 대신 `shared_focus.residual_freshness` 블록이 KO/EN 라벨을 문자 단위 동일하게 반복한다.

### Pipeline

1. **Message layer** — `src/phase47_runtime/message_layer_v1.py` 의 `MESSAGE_LAYER_V1_KEYS` 가 `residual_score_semantics_version / invalidation_hint / recheck_cadence` 3 키를 포함. `build_message_layer_v1_for_row` 가 spectrum row 에서 이 값을 읽어 message dict 에 pass-through.
2. **View-model 공통 계약** — `src/phase47_runtime/product_shell/view_models_common.py`:
   - `normalize_recheck_cadence(raw)` — 위 Recheck Rule 의 4 개 raw 값을 controlled key (`short|medium|medium_long|long`) 로 매핑.
   - `normalize_invalidation_hint(raw)` — 위 Invalidation Rule 의 4 개 raw 값을 controlled kind (`returns_reverse_sign|position_crosses_midline|confidence_drops|pit_fails`) 로 매핑.
   - `RESIDUAL_WORDING[lang]["recheck"|"invalidation"][kind]` — KO/EN parity 11 버킷.
   - `residual_freshness_block(row, lang)` — 위 두 normalize 로 얻은 controlled key 를 `{recheck_cadence_key, invalidation_hint_kind, recheck_label, invalidation_label}` 으로 묶어 반환. `residual_score_semantics_version` 이 빈 문자열이면 **블록 자체를 생략**.
3. **Shared focus block** — `build_shared_focus_block` 이 `block["residual_freshness"] = residual_freshness_block(...)` 를 embed. 네 표면 모두가 같은 라벨을 consume.
4. **Coherence signature** — `compute_coherence_signature` 가 `recheck_cadence_key, invalidation_hint_kind` 를 12-hex 지문 입력에 추가. residual semantics 가 바뀌면 네 표면 모두 지문이 바뀌며, 언어만 바꾸면 지문이 유지된다.
5. **No-leak 방어선** — `strip_engineering_ids` 에 raw slug (`monthly_after_new_filing_or_21_trading_days`, `spectrum_position_crosses_midline`, `confidence_band_drops_to_low`, `pit_validation_fails`, `residual_semantics_v1`) regex 를 pin. `test_agh_v1_patch_11_copy_no_leak.py` 가 DTO 표면에서 0 건 노출을 강제.

### Split runbook (Brain ↔ Product Shell)

| 계층 | 책임 | 대표 파일 | 실행 |
|------|------|-----------|------|
| Brain (residual semantics 결정) | spectrum row 와 message object 에 3 optional 필드를 **결정적으로** 채운다. | `src/metis_brain/spectrum_rows_from_validation_v1.py`, `src/metis_brain/message_object_v1.py` | `python3 -m metis_brain.spectrum_rows_from_validation_v1` |
| Product Shell (residual semantics 번역) | raw 3 필드를 controlled key 로 normalize 한 뒤 KO/EN 라벨 2 줄로 번역. | `src/phase47_runtime/product_shell/view_models_common.py` | 자동 (네 view-model DTO 생성 시 호출) |
| Evidence + Runbook | raw slug 누수 0 + KO/EN parity + coherence 지문 반영 을 봉인. | `scripts/agh_v1_patch_11_brain_truth_freeze.py`, `scripts/agh_v1_patch_11_brain_truth_runbook.py` | `PYTHONPATH=src python3 scripts/agh_v1_patch_11_brain_truth_runbook.py` |
| Spec survey | `residual_score_semantics_version` 커버리지를 Q11 으로, long-horizon tier honesty 를 Q12 로 자동 판정. | `src/metis_brain/mvp_spec_survey_v0.py` | `PYTHONPATH=src python3 -m src.main print-mvp-spec-survey` |

### 변경 요약

- Residual 계약 자체 (§Invalidation Rule / §Recheck Rule / §필드 정의) 는 **변경 없음**.
- 신규 추가: Product Shell 에 번역 파이프라인 + `normalize_*` 2 개 + `RESIDUAL_WORDING` + `residual_freshness_block` + coherence signature 입력 확장 + no-leak regex pin.
- 유지: Message 계약의 optional 속성, Q1..Q10 판정 불변, bundle integrity 필수 필드 불변.
