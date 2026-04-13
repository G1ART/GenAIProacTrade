# Research engine constitution (v1)

Public-core joined substrate is **frozen for MVP** (`freeze_public_core_and_shift_to_research_engine`). Upper-layer work is **research-governed investment intelligence**: hypotheses, PIT experiments, adversarial review, explicit promotion gates, a residual casebook, and judgment-oriented explanations — **not** a generic stock-picker.

## Pillars → code → artifacts

| Pillar | Role | Python module | Persistent JSON / output |
|--------|------|---------------|---------------------------|
| Hypothesis forge | Testable claims + falsifiers | `phase37.hypothesis_registry` · **`phase39`/`phase40` lifecycle** | `data/research_engine/hypotheses_v1.json` |
| PIT validation lab | Family-specific replay + contract | **`phase40.family_execution`** · **`phase41.pit_rerun`** (기판) · **`phase42.evidence_accumulation`** (증거 적층) · `phase38.pit_runner` · `phase39.pit_family_contract` | Phase 40/41/42 번들 · `governance_join_policy_registry_v1.json` |
| Adversarial peer review | Queryable challenges | `phase37.adversarial_review` · **`phase40.adversarial_family`** · **`phase41.adversarial_phase41`** | `adversarial_reviews_v1.json` |
| Promotion gate | No auto-promotion | **`phase42.promotion_gate_phase42`** · **`phase41.promotion_gate_phase41`** (v4) · **`phase40.promotion_gate_phase40`** (v3) · `phase39.promotion_gate_phase39` | `promotion_gate_v1.json` · `promotion_gate_history_v1.json` |
| Residual memory / casebook | Deferred tails with reopen rules | `phase37.casebook` | `casebook_v1.json` |
| User-facing explanation layer | Evidence-linked narrative | **`phase42.explanation_v5`** · **`phase41.explanation_v4`** · **`phase40.explanation_v3`** · `phase39.explanation_v2` · `phase38.explanation_phase38` | **`phase42_explanation_surface_v5.md`** · **`phase41_explanation_surface_v4.md`** 등 |

Machine-readable mirror: `phase37.constitution.RESEARCH_ENGINE_ARTIFACTS` and bundle field `research_engine_constitution`.

## Work units (queueable)

Each pillar defines `work_unit_types` in the constitution payload (e.g. `hypothesis.create`, `pit.execute_scaffold`). These are stable IDs for future queues, DB tables, or CI steps.

## Non-goals

- Broad filing / raw / forward / state_change repair as headline work  
- Auto-promoting hypotheses  
- Production scoring rewrites without governance  
- Black-box buy/sell UX  

## Evidence & patch

- `docs/phase37_evidence.md` — Sprint 1 CLI·산출
- `docs/phase37_patch_report.md`
- `docs/phase38_evidence.md` — DB-bound PIT·누수 감사·스펙 정의·**실측 클로즈아웃** (`sp500_current`, 번들 `docs/operator_closeout/phase38_db_bound_pit_runner_bundle.json`, `ok: true`)
- `docs/phase38_patch_report.md`
- `docs/phase39_evidence.md` — 가설 패밀리·라이프사이클·다중 stance·게이트 v2·**실측** (`phase39_hypothesis_family_expansion_bundle.json`)
- `docs/phase39_patch_report.md`
- `docs/phase40_evidence.md` — 패밀리 PIT 실행·누수·라이프사이클·게이트 v3·**실측 클로즈아웃** (`phase40_family_spec_bindings_bundle.json`, `generated_utc` `2026-04-11T00:09:06Z`, `ok: true`)
- `docs/phase40_patch_report.md`
- `docs/phase41_evidence.md` — 반증 기판·2패밀리 재실행·게이트 v4·**실측** (`phase41_falsifier_substrate_bundle.json`, `generated_utc` `2026-04-11T02:45:40Z`, `ok: true`)
- `docs/phase41_patch_report.md`
- `docs/phase42_evidence.md` — 증거 적층·판별·게이트 phase42·**실측** (`phase42_evidence_accumulation_bundle.json`, `generated_utc` `2026-04-11T04:52:28Z`, `ok: true`; `--bundle-substrate-only`)
- `docs/phase42_patch_report.md`
- `docs/phase43_evidence.md` — 8행 bounded backfill + Phase 42 Supabase-fresh 재실행·**실측** (`phase43_targeted_substrate_backfill_bundle.json`, `2026-04-11T19:03:56Z`, `ok: true`)
- `docs/phase43_patch_report.md`
- `docs/phase44_evidence.md` — claim narrowing·provenance·truthfulness (번들만, DB 없음; `phase44_claim_narrowing_truthfulness_bundle.json`)
- `docs/phase44_patch_report.md`
- `docs/phase45_evidence.md` — canonical closeout·reopen protocol·Phase 46 (번들만; `phase45_canonical_closeout_bundle.json`)
- `docs/phase45_patch_report.md`
- `docs/phase46_evidence.md` — founder cockpit·governed pitch·UI contract·레저 스냅샷 (`phase46_founder_decision_cockpit_bundle.json`, `generated_utc` `2026-04-12T20:40:43Z`, `ok: true`)
- `docs/phase46_patch_report.md`
- `docs/phase47_evidence.md` — browser runtime·governed conversation·ledger writes (`phase47_founder_cockpit_runtime_bundle.json`, `generated_utc` `2026-04-12T22:02:36Z`, `ok: true`)
- `docs/phase47_patch_report.md`
- `docs/phase48_evidence.md` — proactive single-cycle runtime·job registry·bounded debate (`phase48_proactive_research_runtime_bundle.json`, `generated_utc` `2026-04-13T00:50:42Z`, `ok: true`; **클로즈** `docs/operator_closeout/phase48_closeout.md`)
- `docs/phase48_patch_report.md`
- `docs/operator_closeout/phase49_daemon_scheduler_multi_cycle_review.md` — Phase 49 multi-cycle scheduler·metrics (`phase49_daemon_scheduler_multi_cycle_bundle.json`, `generated_utc` `2026-04-13T01:10:08Z`, `ok: true`)

## Commands

### Phase 37 (scaffold)

```bash
export PYTHONPATH=src
python3 src/main.py run-phase37-research-engine-backlog-sprint \
  --phase36-1-bundle-in docs/operator_closeout/phase36_1_complete_narrow_integrity_round_bundle.json \
  --bundle-out docs/operator_closeout/phase37_research_engine_backlog_sprint_bundle.json \
  --out-md docs/operator_closeout/phase37_research_engine_backlog_sprint_review.md
```

### Phase 38 (DB-bound PIT; Supabase 필요)

```bash
export PYTHONPATH=src
python3 src/main.py run-phase38-db-bound-pit-runner \
  --universe sp500_current \
  --bundle-out docs/operator_closeout/phase38_db_bound_pit_runner_bundle.json \
  --out-md docs/operator_closeout/phase38_db_bound_pit_runner_review.md
```

### Phase 39 (가설 패밀리·게이트 v2·설명 v2; DB 불필요)

```bash
export PYTHONPATH=src
python3 src/main.py run-phase39-hypothesis-family-expansion \
  --phase38-bundle-in docs/operator_closeout/phase38_db_bound_pit_runner_bundle.json \
  --bundle-out docs/operator_closeout/phase39_hypothesis_family_expansion_bundle.json \
  --out-md docs/operator_closeout/phase39_hypothesis_family_expansion_review.md
```

### Phase 40 (패밀리별 PIT 스펙·공통 누수 감사; Supabase 필요)

```bash
export PYTHONPATH=src
python3 src/main.py run-phase40-family-spec-bindings \
  --universe sp500_current \
  --bundle-out docs/operator_closeout/phase40_family_spec_bindings_bundle.json \
  --out-md docs/operator_closeout/phase40_family_spec_bindings_review.md
```

### Phase 41 (filing_index + 섹터 메타 반증 기판; Supabase 필요)

```bash
export PYTHONPATH=src
python3 src/main.py run-phase41-falsifier-substrate \
  --universe sp500_current \
  --bundle-out docs/operator_closeout/phase41_falsifier_substrate_bundle.json \
  --out-md docs/operator_closeout/phase41_falsifier_substrate_review.md
```

리뷰만 재생성: `write-phase41-falsifier-substrate-review --bundle-in …`

### Phase 42 (Phase 41 번들 기반 증거 적층·게이트; Supabase 선택)

번들 기판만 재생 (DB 없음): `--bundle-substrate-only`.

```bash
export PYTHONPATH=src
python3 src/main.py run-phase42-evidence-accumulation \
  --phase41-bundle-in docs/operator_closeout/phase41_falsifier_substrate_bundle.json \
  --bundle-substrate-only \
  --bundle-out docs/operator_closeout/phase42_evidence_accumulation_bundle.json \
  --out-md docs/operator_closeout/phase42_evidence_accumulation_review.md
```

리뷰만 재생성: `write-phase42-evidence-accumulation-review --bundle-in …`

### Phase 43 (8행 코호트 한정 backfill + Supabase-fresh Phase 42 재실행)

```bash
export PYTHONPATH=src
python3 src/main.py run-phase43-targeted-substrate-backfill \
  --phase42-supabase-bundle-in docs/operator_closeout/phase42_evidence_accumulation_bundle_supabase.json \
  --bundle-out docs/operator_closeout/phase43_targeted_substrate_backfill_bundle.json \
  --out-md docs/operator_closeout/phase43_targeted_substrate_backfill_review.md
```

### Phase 44 (truthfulness·provenance — 번들만)

```bash
export PYTHONPATH=src
python3 src/main.py run-phase44-claim-narrowing-truthfulness \
  --phase43-bundle-in docs/operator_closeout/phase43_targeted_substrate_backfill_bundle.json \
  --phase42-supabase-bundle-in docs/operator_closeout/phase42_evidence_accumulation_bundle_supabase.json \
  --bundle-out docs/operator_closeout/phase44_claim_narrowing_truthfulness_bundle.json \
  --out-md docs/operator_closeout/phase44_claim_narrowing_truthfulness_review.md
```

### Phase 45 (canonical closeout — 번들만)

```bash
export PYTHONPATH=src
python3 src/main.py run-phase45-operator-closeout-and-reopen-protocol \
  --phase44-bundle-in docs/operator_closeout/phase44_claim_narrowing_truthfulness_bundle.json \
  --phase43-bundle-in docs/operator_closeout/phase43_targeted_substrate_backfill_bundle.json \
  --bundle-out docs/operator_closeout/phase45_canonical_closeout_bundle.json \
  --out-md docs/operator_closeout/phase45_canonical_closeout_review.md
```

### Phase 46 (founder cockpit — 번들만)

```bash
export PYTHONPATH=src
python3 src/main.py run-phase46-founder-decision-cockpit \
  --phase45-bundle-in docs/operator_closeout/phase45_canonical_closeout_bundle.json \
  --phase44-bundle-in docs/operator_closeout/phase44_claim_narrowing_truthfulness_bundle.json \
  --bundle-out docs/operator_closeout/phase46_founder_decision_cockpit_bundle.json \
  --out-md docs/operator_closeout/phase46_founder_decision_cockpit_review.md \
  --pitch-out docs/operator_closeout/phase46_founder_pitch_surface.md
```

Phase 46 번들의 `phase47.phase47_recommendation` (`wire_alert_and_decision_ledgers_to_ui_and_notification_hooks_v1`) 는 **구현 목표 문구**였고, **실제 런타입**은 아래 Phase 47 명령으로 기동한다.

### Phase 47 (founder cockpit runtime)

메타 번들·리뷰:

```bash
export PYTHONPATH=src
python3 src/main.py run-phase47-founder-cockpit-runtime \
  --phase46-bundle-in docs/operator_closeout/phase46_founder_decision_cockpit_bundle.json \
  --bundle-out docs/operator_closeout/phase47_founder_cockpit_runtime_bundle.json \
  --out-md docs/operator_closeout/phase47_founder_cockpit_runtime_review.md
```

HTTP 서버(UI):

```bash
export PYTHONPATH=src
python3 src/phase47_runtime/app.py
```

배포: `docs/operator_closeout/phase47_runtime_deploy_notes.md`

### Phase 48 (proactive research — 단일 사이클, 기판 없음)

`data/research_runtime/research_job_registry_v1.json` · `discovery_candidates_v1.json` 갱신. 알림 레저는 기본 적재 가능 — 운영 시 `--skip-alerts` 로 억제 가능. **운영 클로즈**: `docs/operator_closeout/phase48_closeout.md`.

```bash
export PYTHONPATH=src
python3 src/main.py run-phase48-proactive-research-runtime \
  --phase46-bundle-in docs/operator_closeout/phase46_founder_decision_cockpit_bundle.json \
  --bundle-out docs/operator_closeout/phase48_proactive_research_runtime_bundle.json \
  --out-md docs/operator_closeout/phase48_proactive_research_runtime_review.md
```

### Phase 49 (daemon — 다중 사이클·트리거·메트릭)

Phase 48 오케스트레이터를 N회 호출하고 집계한다. `--cycles`, `--sleep-seconds` 등은 `python3 src/main.py run-phase49-daemon-scheduler-multi-cycle-triggers-and-metrics-v1 --help` 참고.

```bash
export PYTHONPATH=src
python3 src/main.py run-phase49-daemon-scheduler-multi-cycle-triggers-and-metrics-v1 \
  --phase46-bundle-in docs/operator_closeout/phase46_founder_decision_cockpit_bundle.json \
  --bundle-out docs/operator_closeout/phase49_daemon_scheduler_multi_cycle_bundle.json \
  --out-md docs/operator_closeout/phase49_daemon_scheduler_multi_cycle_review.md
```
