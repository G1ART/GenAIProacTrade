# Phase 23 증거 — 원 커맨드 클로즈아웃 (운영 실측)

## 목적

패치 후 **UUID 없이** `run-post-patch-closeout --universe U` 한 번으로 마이그레이션 리포트(가능 시) → phase17–22 스모크 → 시리즈 해석 → 결정적 전진 → 브리프·요약 MD까지 닫는 흐름을 남긴다.

## 운영 실측 스냅샷 (2026-04-07, `sp500_current`)

| 항목 | 결과 |
|------|------|
| 명령 | `export PYTHONPATH=src` 후 `python3 src/main.py run-post-patch-closeout --universe sp500_current` |
| 마이그레이션 `schema_migrations` 프로브 | **실패(예상 가능)** — PostgREST `PGRST106`, 노출 스키마 `public` / `graphql_public` 만 허용 → `supabase_migrations` 미노출 |
| 스키마 진실(스모크) | **phase17–22 전부 통과** (`verify_db_phase_state` 내장 체인) |
| 활성 시리즈 해석 | **성공**, 규칙 `active_compatible_series` |
| 시리즈 ID (감사용만) | `eda6a9b1-18f9-4490-8649-db54066bbb7b` — **운영자가 입력·복붙하지 않음** |
| Chooser | `advance_repair_series` — 근거 `depth_signal_repeat_targeted_public_repair`, 에스컬레이션 `hold_and_repeat_public_repair` |
| 전진 실행 | **성공** (`advance_repair_series`) |
| 요약 MD | `docs/operator_closeout/latest_closeout_summary.md` (실행 시각 UTC `2026-04-07T16:19:35.299688+00:00`) |
| 산출 브리프 | `docs/operator_closeout/closeout_advance_repair.json` / `.md`, `closeout_depth_series_brief.json` / `.md` |

## 추가로 “반드시” 해야 하는가?

**아니요.** 위 실행으로 패치 클로즈아웃 자동 단계는 완료되었다.

**선택(권장이 아닌 의무 아님):**

- `closeout_advance_repair.md` / `closeout_depth_series_brief.md` 를 읽고 다음 운영 주기(추가 수리 vs 공개 깊이 vs 플래토 리뷰)를 판단한다.
- 대시보드에서 SQL 마이그레이션 적용 이력을 **별도**으로 맞춰 보고 싶다면 Supabase UI에서 확인하면 된다(API 프로브와 무관).
- 이후 코드/DB 패치가 있으면 동일 명령으로 다시 클로즈아웃하면 된다.

## 재현 (로컬·CI)

| 명령 | 기대 |
|------|------|
| `PYTHONPATH=src pytest src/tests/test_phase23_operator_closeout.py -q` | Phase 23 단위 테스트 통과 |
| `PYTHONPATH=src pytest src/tests -q` | **296 passed** (저장소 기준; `edgar` deprecation 경고만) |

## 관련 문서

- 패치 요약: `docs/phase23_patch_report.md`
- 운영 절차: `docs/OPERATOR_POST_PATCH.md`
- 핸드오프: `HANDOFF.md` (Phase 23 절)
- 코드: `src/operator_closeout/`, `resolve_iteration_series_for_operator` in `src/public_repair_iteration/depth_iteration.py`

## 핸드오프 시 확인 질문

| 질문 | 어디서 확인 |
|------|-------------|
| 클로즈아웃이 끝까지 갔는가? | `latest_closeout_summary.md` 의 Action executed / Success |
| 스키마는 실제로 맞는가? | 같은 파일의 Database phase smokes = True |
| 다음 자동 전진은 무엇이었는가? | Chooser decision + 생성된 repair/depth 브리프 |
| 공개 우선 궤도인가? | Public-first path 절 + 에스컬레이션/신호 |
