# HANDOFF — Phase 8 (Outlier Casebook + Daily Scanner)

## HEAD / 마이그레이션

- 패치 후 `git rev-parse HEAD` 로 SHA 기록.
- **Phase 8 마이그레이션**: `20250411100000_phase8_casebook_scanner.sql` (`20250410100000_phase71` 이후).

## Phase 8에서 닫힌 것

1. **Outlier Casebook**: `outlier_casebook_runs` + `outlier_casebook_entries` — 후보별 휴리스틱 이상 유형(`reaction_gap`, `thesis_challenge_divergence`, `contamination_override`, `regime_mismatch`, `persistence_failure`, `unexplained_residual`). 각 행에 discrepancy / expected vs observed / uncertainty / limitation / **message 계약 5필드** / `source_trace` / `is_heuristic=true`.
2. **탐지 입력**: Phase 6 후보·점수·컴포넌트, Phase 4 `factor_market_validation_panels`·`forward_returns_daily_horizons`(티커 있을 때), Phase 7 메모·harness 입력. **선행수익은 사례 해석 조인용**이며 Phase 6 스코어 피처 금지와 충돌 없음(스코어링 재주입 아님).
3. **Daily Scanner**: `scanner_runs` + `daily_signal_snapshots`(1:1) + `daily_watchlist_entries` — **저잡음**: 기본 `top_n=15`, `min_priority_score=20`, `max_candidate_rank=60`, 클래스 게이트. 통과 0건이면 빈 워치리스트 허용.
4. **메시지 계약 모듈**: `src/message_contract/` — `OVERLAY_FUTURE_SEAMS_DEFAULT` = `not_available_yet` (뉴스/지분/포지션/거시 오버레이 미구현 명시).
5. **코드**: `src/casebook/outlier_builder.py`, `build_run.py`; `src/scanner/prioritizer.py`, `daily_build.py`.
6. **CLI**: `smoke-phase8`, `build-outlier-casebook`, `build-daily-signal-snapshot`, `report-daily-watchlist`, `export-casebook-samples`.
7. **문서**: `README.md` Phase 8 절, `docs/phase8_evidence.md`, `src/db/schema_notes.md`, `docs/phase8_samples/README.md`.
8. **테스트**: `src/tests/test_phase8_casebook_scanner.py`.

## 운영 명령 (요약)

```bash
cd ~/GenAIProacTrade && source .venv/bin/activate && export PYTHONPATH=src
python3 src/main.py smoke-phase8
python3 src/main.py build-outlier-casebook --universe sp500_current --candidate-limit 600
python3 src/main.py export-casebook-samples --state-change-run-id <RUN_UUID> --limit 20 --out-dir docs/phase8_samples/latest
python3 src/main.py build-daily-signal-snapshot --universe sp500_current
python3 src/main.py report-daily-watchlist
```

## 의도적 비범위 (Phase 8)

- 코크핏/UI, 알림 스팸, 매매·포트폴리오·실행, 벤치마크 마케팅, 가짜 뉴스/포지션 오버레이, 광범위 신규 소스 수집, 가설 엔진 본구현.

## 남은 리스크 / 갭

- 이상치 판정은 **휴리스틱 v1**; 오탐·미탐 가능.
- 검증 패널·선행수익 **날짜 정렬**은 근사; 티커 없으면 forward 조인 생략.
- 케이스북/스캐너 **실 샘플 ID**는 로컬 DB에서 위 CLI로 확정 후 보고.

## 다음 권장 단계

- 운영자 검토 후 `outlier_heuristic_v2` 임계·유형 조정.
- (선택) 뉴스/지분 등 오버레이는 **nullable + not_available_yet** 유지 채로 단계적 연결.

---

## Phase 7 / 7.1 (요약, 변경 없음)

- 마이그레이션 `20250409100000` + `20250410100000`, `src/harness/`, CLI `build-ai-harness-inputs`, `generate-investigation-memos`, `export-phase7-evidence-bundle` 등 — README·`docs/phase7_evidence_bundle.md` 참고.

## Universe Backfill / Phase 6

- 이전 HANDOFF와 동일; README Backfill·Phase 6 절 참고.
