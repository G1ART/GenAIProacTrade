# Phase 13 패치 결과 보고서

**문서 기준일**: 2026-04-01  
**워크오더**: `GenAIProacTrade_Phase13_Workorder_2026-04-06.md` (Public-Core Quality Gate & Residual Triage)

## HEAD / 커밋

| 구분 | SHA |
|------|-----|
| 패치 직전 | `b14ce87fd66435090213dd8190ead6530c5479ae` |
| 패치 직후 | `20d8cb3` (feat `1d72476` + 패치 보고서 SHA 갱신) |

## 변경 파일 요약

| 경로 | 역할 |
|------|------|
| `supabase/migrations/20250416100000_phase13_public_core_quality.sql` | `public_core_cycle_quality_runs`; `outlier_casebook_entries`에 triage 컬럼 |
| `src/public_core/quality.py` | 메트릭 수집, 등급 분류, 갭 순위, 트리이지 요약, DB 행 조립 |
| `src/public_core/cycle.py` | 사이클 종료 시 품질 계산·insert·요약/운영자 MD 반영 |
| `src/casebook/residual_triage.py` | 버킷 상수·오버레이 힌트·필드 부여 |
| `src/casebook/outlier_builder.py` | 엔트리마다 triage 필드 부여 |
| `src/db/records.py` | gating/후보 수 조회, 품질 run insert·최근 조회 |
| `src/main.py` | `report-public-core-quality`, `export-public-core-quality-sample`; trace_json 확장 |
| `src/tests/test_phase13.py` | 회귀 가드 |
| `src/tests/test_phase111_phase12.py` | 품질 번들 mock·CLI 등록 |
| `docs/phase13_evidence.md`, `HANDOFF.md`, `README.md`, `src/db/schema_notes.md` | 문서 |
| `.gitignore` | `docs/public_core_quality/samples/*.json` |

## 마이그레이션

- **파일**: `20250416100000_phase13_public_core_quality.sql`
- **필수**: 원격 DB에 적용 후 `run-public-core-cycle` 시 `public_core_cycle_quality_runs` insert 성공.

## 새 CLI

| 명령 | 설명 |
|------|------|
| `report-public-core-quality --limit N` | 최근 품질 행 JSON 출력 |
| `export-public-core-quality-sample --limit N --out PATH` | 동일 데이터를 파일로 저장 |

## 테스트

```bash
cd src
python -m pytest tests/test_phase13.py tests/test_phase111_phase12.py -q
python -m pytest tests/ -q
```

**결과**: 전체 스위트 **176 passed** (Phase 13 추가분 반영 후 기준).

## 한 문단: Phase 13이 운영 가치를 어떻게 올리는가

이전에는 공개 코어 사이클이 **파이프라인 관점에서 성공**해도, 후보가 대부분 `insufficient_data`이거나 워치리스트가 비어 있을 때 **“좋은 실행인지, 입력이 얇은 실행인지”**가 한눈에 구분되기 어려웠다. Phase 13은 **코드에 고정된 임계값**으로 `quality_class`를 부여하고, 그 근거 메트릭·갭 이유 순위·프리미엄 오버레이 coarse 상태·케이스북 잔차 버킷을 **DB와 운영자 패킷**에 남긴다. 덕분에 감사·리뷰 주체는 “성공 플래그”가 아니라 **재현 가능한 증거**로 실행의 실질을 판단할 수 있고, 미해결 잔차는 **향후 프리미엄 seam을 어디에 쓸지**까지 문장 수준으로 예약할 수 있다(스코어 경로는 여전히 오염하지 않음).
