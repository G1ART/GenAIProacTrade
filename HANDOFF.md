# HANDOFF — Phase 13 (공개 코어 품질 게이트 · 잔차 트리이지)

## 현재 제품 위치

- **Phase 11 (동결)**: FMP 트랜스크립트는 **seam 수준 PoC**로 충분. 추가 벤더·대량 ingest **비활성**.
- **Phase 11.1 (닫힘)**: PIT-safe 다운스트림, ingest 차단 시에도 `operational_runs`, raw **감사 이력**, 레지스트리 **activation 진실성**.
- **Phase 12 (닫힘)**: `run-public-core-cycle` 한 방에 공개 코어 체인 + `docs/public_core_cycle/latest/` 번들; 프리미엄 없이 end-to-end 시연 가능.
- **Phase 13 (닫힘)**: 사이클마다 **임계값 기반 품질 등급** + DB 증거(`public_core_cycle_quality_runs`), 케이스북 **잔차 버킷**·프리미엄 ROI 힌트, 운영자 패킷에 **실행 vs 실질 얇음**·**오버레이 부재 vs 약한 공개 증거** 구분.

## Phase 13 요약

1. **품질 게이트**: `strong` \| `usable_with_gaps` \| `thin_input` \| `degraded` \| `failed` — 전부 `src/public_core/quality.py` 상수 임계값.
2. **DB**: `public_core_cycle_quality_runs`에 메트릭·갭 순위·오버레이 coarse·잔차 요약·미해결 큐 JSON.
3. **케이스북**: `residual_triage_bucket`, `premium_overlay_suggestion` (트리이지 전용; 스파인 비오염).
4. **CLI**: `report-public-core-quality`, `export-public-core-quality-sample`.
5. **관측**: `operational_runs.trace_json`에 `public_core_cycle_quality_run_id`, `cycle_quality_class` 포함(성공 시).

## 마이그레이션 (누적)

- Phase 11: `20250414100000_phase11_transcripts_fmp_poc.sql`
- Phase 11.1: `20250415100000_phase111_transcript_audit_pit.sql`
- **Phase 13**: `20250416100000_phase13_public_core_quality.sql`

## 공개 코어 full-cycle 상태

- **닫힘**: 단일 CLI로 체인 실행 + 로컬 번들 + **품질·잔차 증거**까지 연결됨.
- 프리미엄 데이터 **불필요**로도 품질 분류·갭 이유·트리이지는 동작(오버레이는 관측 메타).

## MVP를 아직 “엄격”이라고 부르기 어려운 이유 (현실적 블로커)

- 유니버스·패널·가격 깊이에 따라 `thin_input`이 흔할 수 있음 — **정상 범주**이나, 운영자는 Phase 13 등급으로 구분 가능.
- 케이스북/스캐너는 **휴리스틱 v1**; 인과·수익 주장 없음.
- DB 마이그레이션 미적용 환경에서는 품질 **insert**만 실패할 수 있음(로컬 JSON에는 스냅샷 남김).

## 다음 단계 권장

1. **프리미엄 ROI**: `unresolved_residual_items`·`premium_overlay_suggestion`이 가리키는 **단일 seam**(예: estimates 또는 price-quality)만 PoC — 스파인 병합 금지.
2. **공개 코어 강화**: factor/검증 커버리지·유니버스 백필로 `thin_input` 비율 자체를 낮추는 쪽(데이터 공학).

**권장 우선순위**: 운영 목적이 “왜 얇은가” 가시화면 **Phase 13으로 이미 가능** → 다음은 **타깃 프리미엄 한 줄** 또는 **공개 데이터 깊이** 중 사업 우선순위에 맞게 선택.

---

## Phase 12 이전 요약

- **Phase 12 CLI**: `run-public-core-cycle`, `report-public-core-cycle`.
- **증거**: `docs/phase12_evidence.md`, `docs/phase13_evidence.md`.

## Phase 11.1 / Phase 10 이전

- README·`docs/phase11_evidence.md`·스키마 메모 참고.
