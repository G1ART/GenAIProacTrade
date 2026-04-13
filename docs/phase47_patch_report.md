# Phase 47 patch report — deployable founder cockpit runtime

## 목적

Phase 46 계약(JSON·MD)을 **브라우저에서 쓰는 얇은 런타임**으로 전환한다. **DB·기판·광역 수리 없음.** Phase 45/46 권위 번들만 소비하고, **거버넌스 대화(의도 매핑)**·**알림/결정 레저 쓰기**·**내부 알림 훅**·**명시적 번들 리로드**를 제공한다.

## 코드 변경 요약

| 경로 | 역할 |
|------|------|
| `src/phase47_runtime/app.py` | stdlib HTTP 서버, 정적 UI, `/api/*` JSON |
| `src/phase47_runtime/routes.py` | 메타·개요·drilldown·알림·결정·대화·리로드 디스패치 |
| `src/phase47_runtime/runtime_state.py` | Phase 46 번들 로드, 레저 경로, staleness |
| `src/phase47_runtime/governed_conversation.py` | 의도 레지스트리 → drilldown/피치 조각만 반환 |
| `src/phase47_runtime/notification_hooks.py` | 프로세스 내 이벤트 큐(Slack 등 후속 연결점) |
| `src/phase47_runtime/orchestrator.py`, `review.py` | Phase 47 메타 번들·리뷰 MD |
| `src/phase47_runtime/phase48_recommend.py` | 다음 단계 권고 |
| `src/phase47_runtime/static/` | `index.html`, `app.js` |
| `src/phase46/alert_ledger.py` | `alert_id`, `update_alert_status`, `dismissed` 상태 |
| `src/main.py` | `run-phase47-founder-cockpit-runtime` |

## CLI

메타 번들·리뷰 생성:

```bash
export PYTHONPATH=src
python3 src/main.py run-phase47-founder-cockpit-runtime \
  --phase46-bundle-in docs/operator_closeout/phase46_founder_decision_cockpit_bundle.json \
  --bundle-out docs/operator_closeout/phase47_founder_cockpit_runtime_bundle.json \
  --out-md docs/operator_closeout/phase47_founder_cockpit_runtime_review.md
```

## 로컬 서버

```bash
export PYTHONPATH=src
python3 src/phase47_runtime/app.py
```

## 테스트

```bash
pytest src/tests/test_phase47_founder_cockpit_runtime.py -q
pytest src/tests/test_phase46_founder_decision_cockpit.py -q
```

## Related

`docs/phase47_evidence.md`, `docs/operator_closeout/phase47_runtime_deploy_notes.md`, `HANDOFF.md`
