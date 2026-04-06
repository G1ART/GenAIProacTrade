# HANDOFF — Phase 11.1 · Phase 12 (프리미엄 seam 동결 + 공개 코어 full-cycle)

## 현재 제품 위치

- **Phase 11 (동결)**: FMP 트랜스크립트는 **seam 수준 PoC**로 충분. 추가 벤더·대량 ingest **비활성**.
- **Phase 11.1 (닫힘)**: PIT-safe 다운스트림, ingest 차단 시에도 `operational_runs`, raw **감사 이력**, 레지스트리 **activation 진실성**.
- **Phase 12 (닫힘)**: `run-public-core-cycle` 한 방에 공개 코어 체인 + `docs/public_core_cycle/latest/` 번들; 프리미엄 없이 end-to-end 시연 가능.

## Phase 11.1 요약

1. **PIT**: `build_transcript_enrichment_for_candidate_context(ticker, as_of_calendar_date)` — `available_at` → `published_at` → `event_date` 중 첫 유효값이 **후보 as_of 이하여야** 메시지 보강 후보. 날짜 없는 행은 제외.
2. **차단 관측성**: `ingest-transcripts-sample`도 키 없으면 **세션 후** `configuration_error`.
3. **activation**: `fmp_earning_call_transcripts_poc` — 프로브/ingest가 `partial|available`일 때만 `active`, 그 외(미설정·권한·네트워크 등) **`inactive`**.
4. **감사**: `raw_transcript_payloads_fmp_history`에 upsert 전 스냅샷; `revision_id` = **전체 본문 SHA-256**; `provenance_json.refresh_audit`에 이전 id/ingest_run.

## Phase 12 요약

- **CLI**: `run-public-core-cycle`, `report-public-core-cycle`.
- **흐름**: (옵션) state change 생성 → harness inputs → memos → casebook → daily watchlist → `cycle_summary.json` + `operator_packet.md`.
- **관측성**: 상위 `operational_runs.run_type=public_core_cycle`; 단계별 기존 run 타입과 타임스탬프로 연계.
- **증거**: `docs/phase12_evidence.md`.

## 마이그레이션

- Phase 11: `20250414100000_phase11_transcripts_fmp_poc.sql`
- Phase 11.1: `20250415100000_phase111_transcript_audit_pit.sql` (`raw_transcript_payloads_fmp_history`)

## 의도적으로 없는 것

- 제2 프리미엄 벤더, estimates/price-quality 실연동, UI/실행/포트폴리오, 스파인 병합.

## 다음 권장 (코드 현실 기준)

- 운영 DB에서 `run-public-core-cycle` 스모크 후 번들 커밋 여부 정책만 정하면 됨.
- 연구·거버넌스 쪽이면 Phase 9 레지스트리 확장; 프리미엄이면 **별도 PoC**로 estimates 등 단일 seam만.

---

## Phase 10 (요약)

- 소스 레지스트리, 오버레이 가용성, 어댑터 seam, `overlay_awareness_json`.

## Phase 9 이전

- README·이전 절 참고.
