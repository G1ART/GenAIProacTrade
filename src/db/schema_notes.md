# DB 스키마 메모 (Phase 0)

## 테이블

- `raw_sec_filings`: SEC에서 가져온 **원본 메타데이터**를 JSON으로 보존. 동일 `(cik, accession_no)`는 **중복 삽입하지 않음** (애플리케이션에서 선조회 후 insert).
- `silver_sec_filings`: 정규화된 요약 레이어. `(cik, accession_no, revision_no)` 유니크. 초기 `revision_no = 1`.

## RLS

Supabase에서 RLS를 켠 경우, **service role** 키는 RLS를 우회한다. Phase 0는 서버 워커 전제로 service role만 사용한다.

## 마이그레이션

SQL 파일 위치: `supabase/migrations/`. Supabase CLI 또는 대시보드 SQL 에디터로 적용한다.
