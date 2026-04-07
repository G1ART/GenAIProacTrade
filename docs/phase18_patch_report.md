# Phase 18 패치 결과 보고서

**문서 기준일**: 2026-04-06  
**워크오더**: `GenAIProacTrade_Phase18_Workorder_2026-04-06.md`

## 변경 요약

공개 기판 **제외 사유 기반** 수리 큐·타깃 빌드아웃 오케스트레이션을 추가한다. 커버리지 진단에 **심볼 큐**(`symbol_queues_out`)를 넘겨 액션 JSON에 샘플 심볼을 실을 수 있다. 개선 리포트는 오케스트레이션 런에 연결되거나, 두 `public_depth_coverage_reports` ID만으로 CLI에서 **독립 적재**할 수 있다(`public_buildout_run_id` null 허용). **프로덕션 스코어 경로**는 `public_buildout` 문자열을 **참조하지 않는다**(`promotion_rules.assert_no_auto_promotion_wiring`).

### 산출물 (파일·경로)

- **마이그레이션**: `supabase/migrations/20250421100000_phase18_public_buildout.sql`
- **패키지**: `src/public_buildout/` (`constants`, `actions`, `improvement`, `revalidation`, `orchestrator`)
- **진단**: `src/public_depth/diagnostics.py` — `compute_substrate_coverage(..., symbol_queues_out=...)`
- **DB**: `src/db/records.py` — Phase 18 CRUD·스모크
- **CLI**: `src/main.py` — 스모크·제외 액션·타깃 빌드·개선·재검증 트리거·브리프 export
- **거버넌스**: `src/research_registry/promotion_rules.py` — 경계 문구·runner `public_buildout` 금지
- **테스트**: `src/tests/test_phase18.py`
- **문서**: `docs/phase18_evidence.md`, `HANDOFF.md`, `README.md`, `src/db/schema_notes.md`, 본 파일

## 새 CLI

| 커맨드 | 역할 |
|--------|------|
| `smoke-phase18-public-buildout` | Phase 18 테이블 도달 |
| `report-public-exclusion-actions` | 제외 분포·액션 큐 JSON (`--persist` 시 스냅샷) |
| `run-targeted-public-buildout` | 사유별 상한 빌드 오케스트레이션 (`--dry-run` 지원) |
| `report-buildout-improvement` | 두 커버리지 리포트 ID로 델타 (`--persist` 시 개선 행) |
| `report-revalidation-trigger` | `recommend_rerun_phase15` / `recommend_rerun_phase16` |
| `export-buildout-brief` | JSON+Markdown 브리프 |

## 테스트

`PYTHONPATH=src python3 -m pytest -q` — `test_phase18` 및 기존 스위트 통과.

## 완료 보고서

운영 클로징 절차·체크리스트·후속 권고를 한 파일에 모은 문서: [phase18_completion_report.md](./phase18_completion_report.md).
