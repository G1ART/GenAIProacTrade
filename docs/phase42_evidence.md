# Phase 42 evidence — evidence accumulation (Phase 41 bundle)

## 확인 체크리스트

- `phase42_bundle_written` / `phase42_review_written` (stdout 태그)
- `docs/operator_closeout/phase42_evidence_accumulation_bundle.json` 유효 JSON, `"ok": true`
- 단위 테스트: `pytest src/tests/test_phase42_evidence_accumulation.py -q` → **8 passed** (분류·판별·게이트·다이제스트·설명 스모크; DB 없음)

## 실측 클로즈아웃

**명령**: `run-phase42-evidence-accumulation --bundle-substrate-only` (Phase 41 pit의 `filing_substrate` / `sector_substrate` `per_row`로 블로커 재생; DB 재조회 없음). 상세 CLI: `docs/phase42_patch_report.md`.

**근거 번들**: `docs/operator_closeout/phase42_evidence_accumulation_bundle.json`  
**리뷰 MD**: `docs/operator_closeout/phase42_evidence_accumulation_review.md`  
**설명 v5**: `docs/operator_closeout/phase42_explanation_surface_v5.md`

| 필드 | 값 |
|------|-----|
| `generated_utc` | `2026-04-11T04:52:28.074748+00:00` |
| 입력 Phase 41 번들 | `docs/operator_closeout/phase41_falsifier_substrate_bundle.json` |
| `pit_execution.experiment_id` (참조) | `f85f3524-73eb-4403-bf0e-c347c06d011f` |
| 코호트 행 수 | **8** |
| `blocker_replay_source` | `phase41_bundle_substrate` (전 행 동일) |
| **Scorecard** (`family_evidence_scorecard`) | `filing_blocker_distribution`: **`only_post_signal_filings_available` 8** (번들 재생 시 Phase 41 `filing_public_ts_unavailable` → 거칠게 이 코드로 매핑) · `sector_blocker_distribution`: **`no_market_metadata_row_for_symbol` 8** |
| **Outcome 판별** (`discrimination_summary`) | `any_family_outcome_discriminating` **true** · `live_and_discriminating_family_ids`에 **양 패밀리 모두** 포함 · `families_with_identical_rollups_groups` **[]** |
| 판별 해석 (리뷰어 주의) | 두 패밀리의 **숫자 롤업**(예: `still_join_key_mismatch` 8)은 동일하나, Phase 42 판별은 **spec 키 이름까지 포함한 시그니처**로 비교한다. 따라서 “가설 간 outcome 카운트만으로 구별됨”으로 읽지 말 것. |
| `hypothesis_narrowing.headline` | `at_least_one_family_outcome_discriminating` |
| `hypothesis_narrowing.by_family_id` | 양 패밀리 `narrowing_status`: **`live_and_discriminating`** · `proxy_limited_substrate`: **true** (기판은 여전히 프록시/결손) |
| `stable_run_digest` | `1cc5113aeff11483` |
| `promotion_gate_phase42.phase` | `phase42` |
| `promotion_gate_phase42.gate_status` | `deferred` |
| `promotion_gate_phase42.primary_block_category` | `deferred_due_to_proxy_limited_falsifier_substrate` |
| `promotion_gate_phase42.phase42_context` | `filing_proxy_row_count` **8**, `sector_missing_row_count` **8**, `all_families_leakage_passed_phase41` **true** |
| `prior_gate_digest.prior_phase` | `phase41` |
| **Phase 43** (`phase43`) | `substrate_backfill_or_narrow_claims_then_retest_v1` |

### 해석 (운영)

- Phase 42는 Phase 41 pit을 읽어 **행 단위 블로커·스코어카드·판별·축소 라벨·게이트(phase42)·설명 v5**를 한 번에 남긴다.
- **게이트 우선순위**: 프록시/섹터 결손 행이 남으면 **`deferred_due_to_proxy_limited_falsifier_substrate`** 가 유지된다 (이번 실측: Phase 41과 동일 카테고리, `phase` 필드만 phase42로 갱신).
- **DB 재조회** 없이 돌린 경우: filing 블로커 분포는 `build_row_level_blockers_from_phase41_substrate` 매핑에 따른다; 세분 원인은 Supabase 경로의 `classify_filing_blocker_cause`와 다를 수 있다.

## 실측 — Supabase fresh (리뷰어·다음 패치 설계)

**원스톱 MD** (요청 1~4 정리): **`docs/operator_closeout/phase42_supabase_reviewer_audit.md`**  
생성: `python3 scripts/export_phase42_supabase_reviewer_audit.py` (게이트 쓰기는 **임시 디렉터리**만 사용; 운영 `data/research_engine` 미변경)

| 필드 | 값 (2026-04-11 실측) |
|------|------------------------|
| 번들 | `docs/operator_closeout/phase42_evidence_accumulation_bundle_supabase.json` |
| `generated_utc` | `2026-04-11T05:54:33.329066+00:00` |
| `stable_run_digest` | `edfd0b7d36ecb2de` |
| **filing** (`family_evidence_scorecard`) | `no_10k_10q_rows_for_cik` **7**, `only_post_signal_filings_available` **1** (ADSK) |
| **sector** | 8행 모두 `no_market_metadata_row_for_symbol` — 감사 MD §4 기준 **심볼당 `market_metadata_latest` raw 행 0건** |
| 리뷰 / 설명 | `phase42_evidence_accumulation_review_supabase.md`, `phase42_explanation_surface_v5_supabase.md` |

번들 재생(`--bundle-substrate-only`)만 쓰면 `signal_available_date`·filing 원인이 거칠어지므로, **원인 코드 검증은 본 Supabase 번들 + 감사 MD**를 권위로 본다.

### Phase 43 후속 (bounded backfill + Phase 42 Supabase-fresh 재실행, 2026-04-11)

동일 8행 코호트에 대해 **`run-phase43-targeted-substrate-backfill`** 를 완주한 뒤 Phase 42를 다시 돌린 결과는 **`docs/operator_closeout/phase43_targeted_substrate_backfill_bundle.json`** (`generated_utc` **`2026-04-11T19:03:56.022392+00:00`**, `ok: true`)에 있다.

| 항목 | Phase 42 Supabase (입력) → Phase 43 직후 Phase 42 |
|------|-----------------------------------------------------|
| **filing 스코어카드** | `no_10k_10q_rows_for_cik` 7 + `only_post_signal_filings_available` 1 → **동일** |
| **sector 스코어카드** | `no_market_metadata_row_for_symbol` 8 → **`sector_field_blank_on_metadata_row` 8** |
| **stable_run_digest** | `edfd0b7d36ecb2de` → **`285b046cc5bcb307`** |
| **게이트 primary_block_category** | `deferred_due_to_proxy_limited_falsifier_substrate` → **동일** |

한정 수리만으로 filing 블로커는 코호트에서 바뀌지 않았고, sector는 **행 부재 → 필드 공백**으로 **분류만 정밀화**되었다. 전체 서술·표·운영 해석은 **`docs/phase43_evidence.md`**, **`HANDOFF.md` Phase 43 절**을 본다.

### Phase 44·45 (8행 코호트 클로즈아웃 체인)

- **Phase 44**: `run-phase44-claim-narrowing-truthfulness` — provenance·truthfulness·claim narrowing. 증거 **`docs/phase44_evidence.md`**, 패치 **`docs/phase44_patch_report.md`**.
- **Phase 45**: `run-phase45-operator-closeout-and-reopen-protocol` — Phase 44 권위 확정, Phase 43 레거시 권고 supersede, canonical closeout·reopen 규칙·Phase 46 권고 필드. 증거 **`docs/phase45_evidence.md`**, 패치 **`docs/phase45_patch_report.md`**.
- **Phase 46**: `run-phase46-founder-decision-cockpit` — 파운더 cockpit·피치·레저·UI 계약. 증거 **`docs/phase46_evidence.md`**, 패치 **`docs/phase46_patch_report.md`**.
- **Phase 47**: `run-phase47-founder-cockpit-runtime` + `src/phase47_runtime/app.py` — 브라우저 런타임·거버넌스 대화·레저 쓰기. 증거 **`docs/phase47_evidence.md`**, 패치 **`docs/phase47_patch_report.md`**.
- **Phase 48**: `run-phase48-proactive-research-runtime` — 트리거·잡 레지스트리·경계 토론·디스커버리 후보(추천 아님). **운영 클로즈 완료** — **`docs/operator_closeout/phase48_closeout.md`**. 증거 **`docs/phase48_evidence.md`**, 패치 **`docs/phase48_patch_report.md`**. 후속 다중 사이클: **`docs/operator_closeout/phase49_daemon_scheduler_multi_cycle_review.md`**.

## 산출·영속

- `docs/operator_closeout/phase42_evidence_accumulation_bundle.json`
- `docs/operator_closeout/phase42_evidence_accumulation_review.md`
- `docs/operator_closeout/phase42_explanation_surface_v5.md`
- `data/research_engine/promotion_gate_v1.json` (**Phase 42 페이로드로 덮어씀**)
- `data/research_engine/promotion_gate_history_v1.json` (append)

## Related

`docs/phase42_patch_report.md`, `docs/phase41_evidence.md`, **`docs/operator_closeout/phase42_supabase_reviewer_audit.md`**, **`docs/phase43_evidence.md`**, **`docs/phase44_evidence.md`**, **`docs/phase45_evidence.md`**, **`docs/phase46_evidence.md`**, **`docs/phase47_evidence.md`**, **`docs/phase48_evidence.md`**, **`docs/operator_closeout/phase48_closeout.md`**, `HANDOFF.md`
