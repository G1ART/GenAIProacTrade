# Phase 46 patch report — founder-facing decision cockpit

## 목적

Phase 45 canonical closeout를 **파운더/운영자가 읽기 쉬운 단일 창**으로 올린다. 권위 번들(Phase 44·45)만으로 **read model**, **cockpit 카드**, **결정론적 대표 메시지(스포크스퍼슨)**, **drill-down 계층**, **UI 소비 계약**, **알림·결정 trace 레저(파일)** 를 제공한다. **기판·DB 캠페인·광역 수리 없음.**

## 코드 변경 요약

| 경로 | 역할 |
|------|------|
| `src/phase46/read_model.py` | Phase 45+44 → founder read model |
| `src/phase46/cockpit_state.py` | decision / message / information / research / closeout 카드 |
| `src/phase46/representative_agent.py` | 템플릿 피치; 레거시 Phase 43 권고 문자열 누출 방지 |
| `src/phase46/drilldown.py` | `decision` … `closeout` 계층 |
| `src/phase46/alert_ledger.py` | `data/product_surface/alert_ledger_v1.json` |
| `src/phase46/decision_trace_ledger.py` | `data/product_surface/decision_trace_ledger_v1.json` |
| `src/phase46/ui_contract.py` | 웹/노코드용 JSON 계약 |
| `src/phase46/phase47_recommend.py` | 다음 단계 권고 |
| `src/phase46/orchestrator.py`, `review.py` | 번들·리뷰·피치 MD |
| `src/main.py` | `run-phase46-founder-decision-cockpit`, `write-phase46-founder-decision-cockpit-review` |

## CLI

```bash
export PYTHONPATH=src
python3 src/main.py run-phase46-founder-decision-cockpit \
  --phase45-bundle-in docs/operator_closeout/phase45_canonical_closeout_bundle.json \
  --phase44-bundle-in docs/operator_closeout/phase44_claim_narrowing_truthfulness_bundle.json \
  --bundle-out docs/operator_closeout/phase46_founder_decision_cockpit_bundle.json \
  --out-md docs/operator_closeout/phase46_founder_decision_cockpit_review.md \
  --pitch-out docs/operator_closeout/phase46_founder_pitch_surface.md
```

## 테스트

```bash
pytest src/tests/test_phase46_founder_decision_cockpit.py -q
```

## 실측 산출 (저장소 기록)

- **번들**: `docs/operator_closeout/phase46_founder_decision_cockpit_bundle.json`
- **`generated_utc` (저장소 기록 번들)**: `2026-04-12T20:40:43.768261+00:00`
- **Phase 47 권고** (번들·코드 문자열만; 본 레포에 Phase 47 전용 CLI 없음): `wire_alert_and_decision_ledgers_to_ui_and_notification_hooks_v1`

상세: **`docs/phase46_evidence.md`**.

## Related

`docs/phase46_evidence.md`, `docs/phase45_evidence.md`, `docs/phase44_evidence.md`, **`docs/phase47_evidence.md`** (브라우저 런타임), `HANDOFF.md` — Phase 46·47 절
