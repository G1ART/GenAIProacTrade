# Phase 13 증거 — Public-Core Quality Gate and Residual Triage

**목표**: 실행 성공(`ok: true`)만으로는 부족한 **실질 품질**을 임계값과 DB 증거로 고정하고, 잔차를 **재사용 가능한 버킷**으로 묶어 운영자 패킷과 향후 프리미엄 ROI 훅을 연결한다. 인과 단정과 매매 언어는 사용하지 않는다.

## 1. 산출물

| 산출물 | 설명 |
|--------|------|
| `public_core_cycle_quality_runs` | 사이클마다 1행: `quality_class`, `metrics_json`, `gap_reasons_ranked`, 오버레이 요약, 잔차 트리이지, 미해결 큐(JSON 배열). |
| `cycle_summary.json` | `cycle_quality_class`, `public_core_cycle_quality_run_id`, `cycle_quality_snapshot`. |
| `operator_packet.md` | Phase 13 섹션: 품질 등급, missingness 비율, 오버레이 coarse 상태(absent vs blocked vs partial/available), 잔차 지배 버킷, 갭 이유 상위, explicit unknowns. |
| `outlier_casebook_entries` | `residual_triage_bucket`, `premium_overlay_suggestion` (insert 시 자동 채움). |

## 2. 품질 등급 (`quality_class`)

코드 상수: `src/public_core/quality.py`.

- **failed**: `cycle_ok` 아님 또는 `scanner_watchlist` 단계 `failed`.
- **degraded**: harness / memos / casebook 중 단계 `failed`, 또는 harness 오류율이 0.15 초과.
- **thin_input**: `insufficient_data` 비율이 0.75 이상이거나, 0.5 이상이면서 gating missingness 비율이 0.35 이상.
- **strong**: 낮은 insufficient 비율과 워치리스트·케이스북 건수 조건(코드 참고).
- **usable_with_gaps**: 그 외 성공 사이클.

## 3. 잔차 트리이지 버킷

`src/casebook/residual_triage.py`에서 `outlier_type`과 reaction_gap 시 validation panel 유무로 매핑한다.

## 4. CLI

```bash
export PYTHONPATH=src
python3 src/main.py report-public-core-quality --limit 15
python3 src/main.py export-public-core-quality-sample --limit 10 --out docs/public_core_quality/samples/latest.json
```

## 5. 마이그레이션

`supabase/migrations/20250416100000_phase13_public_core_quality.sql`

## 6. 테스트

`src/tests/test_phase13.py`

## 7. 운영 SQL 예시

```sql
select id, quality_class, universe_name, created_at
from public.public_core_cycle_quality_runs
order by created_at desc
limit 10;
```
