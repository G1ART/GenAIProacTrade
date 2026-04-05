# Phase 8 — 증거·재현 절차

## 전제

- `20250411100000_phase8_casebook_scanner.sql` 적용.
- 최근 `state_change_runs` (completed) + 후보·점수·(선택) 검증 패널·선행수익·Phase 7 메모가 존재.

## A) 케이스북 (실데이터 ≥3 샘플)

1. 케이스북 생성:

```bash
export PYTHONPATH=src
python3 src/main.py build-outlier-casebook --universe sp500_current --candidate-limit 600
```

2. 출력에서 `casebook_run_id` 복사 후 샘플 덤프:

```bash
python3 src/main.py export-casebook-samples \
  --casebook-run-id <CASEBOOK_RUN_UUID> \
  --limit 20 \
  --out-dir docs/phase8_samples/latest
```

`--state-change-run-id`만 알면 해당 run의 **최신** casebook run을 자동 선택한다.

3. `entries.json` 상위 3행의 `id`, `candidate_id`, `outlier_type`을 완료 보고에 기록.

## B) 일일 스캐너 (실 run 1회)

```bash
python3 src/main.py build-daily-signal-snapshot --universe sp500_current --top-n 15 --min-priority-score 20
python3 src/main.py report-daily-watchlist
```

JSON 안의 `scanner_run_id`, `daily_signal_snapshot`, `watchlist`를 보관. **워치리스트가 비어 있을 수 있음**(저잡음 정책).

## 저잡음 정책

- `top_n` (기본 15), `min_priority_score` (기본 20), `max_candidate_rank` (기본 60).
- 클래스 제한: `investigate_now` \| `investigate_watch` \| `recheck_later`.

## 상위 스펙 문서

- 워크스페이스에 없으면: `docs/spec/*.md` (또는 원본 `.docx`) — Phase 8은 워크오더 해석을 충돌 없이 따름.
