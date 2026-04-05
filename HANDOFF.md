# HANDOFF — Phase 10 (소스 레지스트리 · 프리미엄 오버레이 seam · 권리/계보)

## HEAD / 마이그레이션

- 패치 후 `git rev-parse HEAD` 로 SHA 기록.
- **Phase 10 마이그레이션**: `20250413100000_phase10_source_registry_overlays.sql` (Phase 9 이후).

## 로드맵 코어 vs Phase 10

- **원 로드맵에서 이미 닫힌 축**(구현 현실): 공개 우선 결정적 스파인, 검증·state change, harness/casebook/scanner 백엔드, 관측성·연구 레지스트리, 실DB 증거(Phase 8–9 문서).
- **Phase 10이 추가하는 것**(로드맵을 넓히되 철학 유지): **공개 데이터 상한**을 인정하고, 프리미엄·독점·내부·파트너 소스를 **등록·분류·권리 메타**로 묶은 뒤, **고ROI 오버레이**(콜 트랜스크립트, 컨센서스 추정, 고품질 가격/인트라데이, 선택적 옵션)를 **모델링만** 하고 자격이 없으면 `not_available_yet`로 둠. 벤더 대량 연동·UI·실행 **비범위**.

## 현재 웨지 (제품 서술)

- 공개 결정적 스파인 + 불일치 보존 메시지 계층 + 잔차/이상치 케이스북 + **자동 승격 없는** 연구 진화 경로.
- Phase 10 이후: 동일 웨지에 **소스 권리·계보·선택적 오버레이 준비**가 얹힘.

## Phase 10에서 닫힌 것

1. **소스 레지스트리** 및 위성 테이블(access / entitlements / coverage / rights notes / overlay availability / gap report 저장).
2. **ROI 순위 행렬**(코드 `OVERLAY_ROI_RANKED` + `export-source-roi-matrix` + `report-overlay-gap`).
3. **어댑터 seam**(transcripts / estimates / price_quality) — `probe()`·정규화 타깃·PIT·실패 동작·권리 메타; `fetch_normalized`는 자격 없을 때 빈 결과.
4. **다운스트림 인지**: `overlay_awareness_json` on casebook entries & watchlist rows; `PREMIUM_OVERLAY_SEAMS_DEFAULT`.
5. **CLI**: `seed-source-registry`, `report-source-registry`, `report-overlay-gap`, `smoke-source-adapters`, `export-source-roi-matrix`.
6. **문서/테스트**: `docs/phase10_evidence.md`, `src/tests/test_phase10_sources.py`, `src/db/schema_notes.md`, README Phase 10 절.

## 프리미엄 오버레이 우선순위 (요약)

1. Earnings call transcripts — 메모/케이스북 서사 대 filing 긴장.
2. Analyst estimates — 기대 vs 실현 잔차.
3. Higher-quality price / intraday — 시그널일·품질 (스파인 **대체** 아님).
4. (선택) Options / microstructure — 연구 레인.

## 의도적으로 없는 것

- 다수 벤더 병렬 ingest, 가짜 프리미엄 샘플, 코크핏 확장, 매매/포트폴리오, 벤치마크 마케팅, **없는 프리미엄을 생산 스코어에 자동 전환**, 공개 스파인 오염.

## 다음 권장 단계

- 단일 벤더 PoC(예: 트랜스크립트) 선택 → 계약·PIT·정규화 어댑터 **한 줄** 구현 → `source_overlay_availability`를 `partial`/`available`로 갱신하는 절차만 추가.

---

## Phase 9 (요약)

- `operational_runs`, 연구 레지스트리, Phase 8 실DB 증거: `docs/phase9_evidence.md`.

## Phase 8 이전

- README·이전 절 참고.
