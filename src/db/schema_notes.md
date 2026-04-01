# DB 스키마 메모 (Phase 0–1)

## 데이터 계층 역할

| 테이블 | 역할 |
|--------|------|
| `issuer_master` | **Issuer identity**. CIK가 canonical key. 티커·이름·SIC 등은 최근 관측값으로 갱신. |
| `filing_index` | **Filing identity**. “이 accession 공시가 존재한다”는 구조적 인덱스. raw와 독립 조회. |
| `raw_sec_filings` | **원문 보존층**. `payload_json`에 edgartools 기준 스냅샷. **업데이트 없음.** |
| `silver_sec_filings` | **정규화 해석층**. `normalized_summary_json`. revision으로 이력 확장. |
| `ingest_runs` | **수집 실행 감사**. run 단위 성공/실패 집계·메타. |

## Idempotency 정책 (요약)

### Raw duplicate policy

- 유니크: `(cik, accession_no)`.
- 동일 키가 이미 있으면 **insert 하지 않음** (immutable). 원본 덮어쓰기 없음.

### Filing identity uniqueness policy

- 유니크: `(cik, accession_no)`.
- 재실행 시 **upsert**: `last_seen_at` / `updated_at` 및 일부 메타 갱신, `first_seen_at`은 최초 insert 시만 유지.

### Silver revision policy

- 유니크: `(cik, accession_no, revision_no)`.
- Phase 1: `revision_no = 1`만 사용. 동일 키가 있으면 **insert 생략** (같은 입력으로 silver 무한 증식 방지).
- 향후 정규화 규칙 변경 시 `revision_no` 증가로 append-only 이력을 쌓는 것을 권장.

### Issuer master

- 유니크: `cik`.
- 재실행 시 **upsert**: `first_seen_at` / `created_at` 유지, `last_seen_at`·`ticker`·이름·SIC 등 갱신.

## RLS

Service role 키는 RLS를 우회한다. 로컬 워커는 service role 전제.

## 마이그레이션

`supabase/migrations/` 에서 **시간순**으로 적용한다.

1. `20250401000000_phase0_raw_silver_sec_filings.sql`
2. `20250402120000_phase1_issuer_filing_ingest_runs.sql`
