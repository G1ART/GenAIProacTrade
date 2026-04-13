# Phase 51 patch report — external trigger ingest & runtime health surface

## 목적

Phase 50 제어 평면·감사 위에 **거버넌스된 외부 트리거 적재**(정규화·중복 제거·별도 감사)와 **런타임 헬스 요약·파운더 표면**을 추가한다. 외부 이벤트는 Phase 48 **`supplemental_triggers`** 로만 합류하며, **운영자 `manual_triggers_v1` 시드 없이** 권위 스모크로 비영 사이클을 증명한다. **광역 기판·프리미엄 구매 실행·무제한 웹훅·자율 매매 없음.**

## 코드·데이터

| 경로 | 역할 |
|------|------|
| `src/phase51_runtime/external_trigger_ingest.py` | 적재 레지스트리, 제어 평면 게이트, supplemental 변환, 소비 시 `linked_cycle_id` |
| `src/phase51_runtime/trigger_normalizer.py` | raw → 허용 트리거 타입, `dedupe_key` |
| `src/phase51_runtime/external_trigger_audit.py` | 외부 전용 감사 로그 |
| `src/phase51_runtime/external_ingest_adapters.py` | 파일 드롭·`process_external_payload` |
| `src/phase51_runtime/runtime_health.py` | `runtime_health_summary_v1.json` |
| `src/phase51_runtime/cockpit_health_surface.py` | 한글 헬스 카드 payload |
| `src/phase51_runtime/orchestrator.py` | `run_phase51_external_positive_path_smoke` |
| `src/phase51_runtime/review.py`, `phase52_recommend.py` | 번들·리뷰·다음 페이즈 토큰 |
| `src/phase48_runtime/trigger_engine.py` | `supplemental_triggers` 병합 |
| `src/phase48_runtime/orchestrator.py` | `supplemental_triggers` 전달 |
| `src/phase47_runtime/routes.py`, `static/app.js` | `/api/runtime/*`, Brief 헬스 |
| `src/main.py` | `run-phase51-external-positive-path-smoke`, `submit-external-trigger-json`, `refresh-runtime-health-summary` |
| `data/research_runtime/phase51_*` | 스모크 격리 산출(레지스트리·적재·감사·드롭 등) |

## CLI

**권위 외부 스모크 + 번들·리뷰 + (선택) 헬스 파일 갱신**

```bash
cd /Users/hyunminkim/GenAIProacTrade
PYTHONPATH=src python3 src/main.py run-phase51-external-positive-path-smoke --persist-runtime-health
```

**단건 JSON 적재**

```bash
PYTHONPATH=src python3 src/main.py submit-external-trigger-json --json-file /path/to/event.json
```

**헬스 요약만 재생성**

```bash
PYTHONPATH=src python3 src/main.py refresh-runtime-health-summary
```

## 테스트

```bash
PYTHONPATH=src python3 -m pytest src/tests/test_phase51_external_trigger_ingest_and_runtime_health.py -q
```

## 클로즈

- **Phase 51**: **종료** — 증거 `docs/phase51_evidence.md`, 요약 `docs/operator_closeout/phase51_closeout.md`.

## Related

`docs/phase51_evidence.md`, `docs/operator_closeout/phase51_closeout.md`, `docs/phase50_patch_report.md`, `HANDOFF.md`
