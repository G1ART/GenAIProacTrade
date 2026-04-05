# HANDOFF — Phase 11 (단일 벤더 트랜스크립트 PoC — FMP)

## 벤더 / 바인딩

- **선택 경로**: **Financial Modeling Prep** — `earning_call_transcript` **v3** 단일 구현 (`src/sources/fmp_transcript_client.py`).
- **환경 변수**: `FMP_API_KEY` (필수로 실제 호출), `TRANSCRIPTS_PROVIDER` 기본값 `fmp`.
- **자격이 없으면**: CLI는 **가짜 성공을 내지 않음** — `probe-transcripts-provider`는 구성 실패로 `operational_runs`/`operational_failures`에 기록될 수 있고, `ingest-transcripts-sample`은 즉시 실패.

## `partial` vs `available` (earnings_call_transcripts)

- **available**: 샘플 분기에 대해 HTTP 200 + 유효 세그먼트 텍스트 + 정규화 `ok` — 오버레이가 “본문 수준으로 쓸 수 있음”을 의미.
- **partial**: 엔드포인트/파이프라인은 확인됐으나 해당 심볼·분기에 빈 응답·빈 세그먼트·형식 이슈 등으로 **완전 샘플은 아님** — 그래도 Phase 10 placeholder만이 아닌 **실측 근거**가 메타에 남음.

## 다운스트림 (트랜스크립트 인지)

- **일일 워치리스트** (`daily_watchlist_entries`): `transcript_enrichment_json` + 정규화 행이 준비된 경우에만 `message_why_matters`에 **짧은 문장** 추가. **결정적 점수·랭킹에는 미사용**; 트랜스크립트 없어도 빌드 실패하지 않음.

## 마이그레이션 / 테이블

- `20250414100000_phase11_transcripts_fmp_poc.sql` — `data_source_registry` 행 `fmp_earning_call_transcripts_poc`, `transcript_ingest_runs`, `raw_transcript_payloads_fmp`, `normalized_transcripts`, `daily_watchlist_entries.transcript_enrichment_json`.

## CLI

- `probe-transcripts-provider`, `ingest-transcripts-sample`, `report-transcripts-overlay-status`, `export-transcript-normalization-sample`.

## 관측성

- `operational_runs`: `run_type=transcript_overlay`, `component` = `fmp_transcript_probe` | `fmp_transcript_ingest_sample`.
- `source_overlay_runs`: 프로브/ingest 페이로드 요약.

## 의도적으로 없는 것

- 두 번째 트랜스크립트 벤더, estimates/price-quality 실연동(동일 패치), 코크핏·실행, 스파인 병합, 점수 오염.

## 다음 권장

- **트랜스크립트**: 더 많은 심볼·분기 샘플 + 라이선스 범위 내 재배포 정책 정리, 또는 **analyst estimates** 단일 PoC로 동일 패턴 복제.

---

## Phase 10 (요약)

- 소스 레지스트리, 오버레이 가용성, 어댑터 seam, `overlay_awareness_json`, `docs/phase10_evidence.md`.

## Phase 9 이전

- README·이전 절 참고.
