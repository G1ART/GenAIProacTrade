# Phase 12 증거 — 공개 코어 full-cycle

## 목표

프리미엄 계정·실연동 없이 **결정적 state change → harness 입력 → 조사 메모 → 이상치 케이스북 → 일일 워치리스트**까지 한 번에 돌리고, `docs/public_core_cycle/latest/` 에 JSON+Markdown 번들을 남긴다. **스코어링은 공개 결정적 코어만**; 트랜스크립트 등 프리미엄은 요약 메타로만 표시.

## 사전 조건

- Supabase 마이그레이션 적용(Phase 6–11.1).
- 대상 유니버스에 대해 **completed** `state_change_runs` 가 있거나, `--ensure-state-change` 로 패널이 채워진 뒤 엔진이 돌아가야 함.

## 명령

```bash
cd /path/to/GenAIProacTrade
source .venv/bin/activate
export PYTHONPATH=src

python3 src/main.py run-public-core-cycle --universe sp500_current
# 또는 기존 run 지정
python3 src/main.py run-public-core-cycle --universe sp500_current --state-change-run-id '<uuid>'

# 마지막 번들 재출력
python3 src/main.py report-public-core-cycle
```

선택: `--out-dir` 로 번들 경로 변경(기본 `docs/public_core_cycle/latest/`).

## 산출물

| 파일 | 내용 |
|------|------|
| `cycle_summary.json` | 단계별 status, run id, 경고, 오버레이/레지스트리 요약, `operator_plain_language` |
| `operator_packet.md` | 운영자용 짧은 Markdown |

## 관측성

- 상위 `operational_runs`: `run_type=public_core_cycle`, `component=run_public_core_cycle_v1`.
- 단계별 세부는 기존처럼 `ai_harness`, `outlier_casebook`, `daily_scanner` 등 **별도 run**으로 남길 수 있음(동일 DB에서 `started_at`으로 연계).

## DB 연계 확인 (예시)

```sql
select id, run_type, component, status, started_at, metadata_json
from operational_runs
where run_type in ('public_core_cycle', 'daily_scanner', 'ai_harness', 'outlier_casebook')
order by started_at desc
limit 20;
```

## 프리미엄

- `cycle_summary.json` 의 `overlay_and_registry_summary` 에 트랜스크립트 오버레이·레지스트리 헤드라인이 포함되며, **차단/미설정이어도 사이클은 완료될 수 있음**.

## 테스트

```bash
cd src && python -m pytest tests/test_phase111_phase12.py -q
```
