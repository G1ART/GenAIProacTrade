# Phase 52 patch report — governed webhook auth, budgets, routing, optional queue

## 목적

Phase 51 외부 적재 위에 **소스 등록·인증(SHA-256 비밀 해시)·소스별 예산·라우팅 화이트리스트·선택 큐**를 얹고, **감사 가능한 거절 사유**와 **런타임 헬스의 소스/큐 가시성**을 확보한다. **광역 기판·무인증 공개 웹훅·자율 매매 없음.**

## 코드·데이터

| 경로 | 역할 |
|------|------|
| `src/phase52_runtime/source_registry.py` | 소스 레지스트리 로드/저장 |
| `src/phase52_runtime/webhook_auth.py` | 비밀 해시·`verify_source_auth` |
| `src/phase52_runtime/source_budgets.py` | 분당·윈도 예산, 인증/라우팅/레이트·결과 카운터 |
| `src/phase52_runtime/routing_rules.py` | raw / normalized allowlist |
| `src/phase52_runtime/event_queue.py` | 경계 큐, dedupe, pop/상태 |
| `src/phase52_runtime/governed_ingress.py` | 인증 게이트 → 정규화 → 라우팅 → 예산 → direct 또는 enqueue, flush |
| `src/phase52_runtime/health_merge.py` | `runtime_health_summary`에 `external_source_activity_v52` 병합 |
| `src/phase52_runtime/orchestrator.py` | `run_phase52_governed_webhook_auth_routing_smoke` |
| `src/phase52_runtime/review.py`, `phase53_recommend.py` | 번들·리뷰 MD, Phase 53 토큰 |
| `src/phase51_runtime/runtime_health.py` | Phase 52 병합 훅 |
| `src/phase51_runtime/cockpit_health_surface.py` | 한글 헬스에 소스/큐 한 줄 |
| `src/phase47_runtime/routes.py`, `app.py` | `/api/runtime/external-ingest/authenticated`, 헤더 전달 |
| `src/main.py` | `run-phase52-governed-webhook-auth-routing-smoke` |
| `src/tests/test_phase52_webhook_auth_routing.py` | 단위·스모크·dispatch 검증 |

## CLI

```bash
cd /Users/hyunminkim/GenAIProacTrade
PYTHONPATH=src python3 -m main run-phase52-governed-webhook-auth-routing-smoke --repo-root .
# 선택: 런타임 헬스 JSON 갱신
PYTHONPATH=src python3 -m main run-phase52-governed-webhook-auth-routing-smoke --repo-root . --persist-runtime-health
```

## 테스트

```bash
PYTHONPATH=src python3 -m pytest src/tests/test_phase52_webhook_auth_routing.py \
  src/tests/test_phase51_external_trigger_ingest_and_runtime_health.py \
  src/tests/test_phase50_registry_controls_and_operator_timing.py -q
```

## 클로즈

- **Phase 52**: **종료** — 증거 `docs/phase52_evidence.md`, 요약 `docs/operator_closeout/phase52_closeout.md`.

## Related

`docs/phase52_evidence.md`, `docs/operator_closeout/phase52_closeout.md`, `docs/phase51_patch_report.md`, `HANDOFF.md`
