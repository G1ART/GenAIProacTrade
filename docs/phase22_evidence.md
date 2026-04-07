# Phase 22 증거 — Public-depth iteration under repair series

## 목적

동일 `public_repair_iteration_series` 아래 **`member_kind=public_depth`** 멤버로 공개 깊이 확장 런을 적재하고, **`phase22_ledger`**·`public_depth_operator_signal`·에스컬레이션·시리즈 브리프로 **감사 가능한 한 루프**를 남긴다. 프로덕션 스코어 경로는 `public_repair_iteration` / `public_repair_campaign`을 **참조하지 않는다**(`state_change.runner` 테스트 유지).

## 스키마·마이그레이션

| 파일 | 내용 요약 |
|------|-----------|
| `supabase/migrations/20250425100000_phase22_public_depth_iteration.sql` | `member_kind`, `public_depth_run_id`, XOR·부분 유니크 인덱스 |

적용 후: `python3 src/main.py smoke-phase22-public-depth-iteration` (프로젝트 루트, `PYTHONPATH=src`).

## 재현 가능한 검증 (로컬, 2026-04-01 클로징)

| 명령 | 결과 |
|------|------|
| `PYTHONPATH=src pytest src/tests/test_phase22_public_depth_iteration.py -q` | **15 passed** |
| `PYTHONPATH=src pytest src/tests -q` | **278 passed** |

**경고 3건:** 전부 서드파티 `edgar` 패키지의 `DeprecationWarning`(HtmlDocument / html / htmltools). 프로젝트 테스트 실패가 아니다. 요약은 pytest `warnings summary`에 출력된다.

## 시리즈 브리프·활성 시리즈 (운영 절차 증거)

1. 활성 시리즈 UUID (닫힌 시리즈는 사용하지 않음):

   ```bash
   export PYTHONPATH=src
   python3 src/main.py report-latest-repair-state --program-id latest --universe YOUR_UNIVERSE --active-series-id-only
   ```

2. 브리프 산출:

   ```bash
   python3 src/main.py export-public-depth-series-brief --series-id ACTIVE_SERIES_UUID \
     --out docs/public_depth/series_brief_latest
   ```

**클로징 기준:** 위 1)에서 얻은 UUID로 2)를 실행해 JSON(+동반 Markdown 경로가 있으면 해당 산출물)이 정상 생성되면, 해당 시리즈에 대한 Phase 22 **브리프 증거 체인**은 완료로 본다. UUID·유니버스·`--out` 경로는 환경마다 다르다.

## 골든 패스(한 루프) 참고

```bash
export PYTHONPATH=src
python3 src/main.py advance-public-depth-iteration --program-id latest --universe YOUR_UNIVERSE \
  --out docs/public_depth/advance_depth_latest
```

Phase 15/16 재실행은 **`--execute-phase15-16-revalidation`** 이고, **게이트가 이전 대비 새로 열린 경우에만** 동작한다.

## 관련 코드·정책

- 서비스: `src/public_repair_iteration/service.py` (depth iteration, ledger, 브리프)
- 분류: `marginal_policy` / `depth_signal` (개선 4분류, 운영자 신호)
- 패치 요약: `docs/phase22_patch_report.md`
- 운영 템플릿: `docs/OPERATOR_POST_PATCH.md` · `./scripts/operator_post_patch_smokes.sh`

## 핸드오프 시 확인할 것

| 질문 | 어디서 확인 |
|------|-------------|
| 마이그레이션이 대상 DB에 적용됐는가? | Supabase 마이그레이션 목록 + `smoke-phase22-public-depth-iteration` |
| 어떤 시리즈가 활성인가? | `report-latest-repair-state`의 `active_series_id` 또는 `--active-series-id-only` |
| 멤버·분포·에스컬레이션 브랜치 요약은? | `export-public-depth-series-brief` 출력 JSON |
| 다음 궤도는 공개 깊이 심화인가, 수리 반복인가, 플래토 리뷰인가? | 브리프의 권고·`public_depth_operator_signal`·Phase 20/21 에스컬레이션 |

상위 핸드오프: 저장소 루트 `HANDOFF.md` (Phase 22 절).
