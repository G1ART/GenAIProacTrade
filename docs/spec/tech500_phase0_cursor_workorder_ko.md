# tech500 phase0 cursor workorder ko

> 원본: `tech500_phase0_cursor_workorder_ko.docx` — 레포 내 보관용 자동 추출본(표·머리글은 단순화됨).

Tech500 Factor Engine / AI Harness OS

Phase 0 Cursor Work Order v1

문서 유형

즉시 실행 지시문

버전

v1.0

상태

초안 고정본

상위 문서

Cursor Agent Protocol + Plan Mode Roadmap

이 문서는 구현 경로를 고정하기 위한 운영 문서입니다. 상위 제품 스펙 문서와 모순되게 해석해서는 안 되며, 구현 중 판단이 충돌할 경우 항상 상위 문서를 우선합니다.

1. 목표

본 문서는 Phase 0를 실제로 집행하기 위한 Cursor용 실행 지시문이다. 목표는 최소 동작 가능한 source-of-truth spine을 세우는 것이다. 결과물은 완성형 제품이 아니라, 다음 Phase들이 올라갈 수 있는 재현 가능한 뼈대여야 한다.

2. 이번 패치의 범위

• Python worker 기본 구조 생성

• Supabase 연결 및 기초 스키마 생성

• EdgarTools 설치 및 SEC identity 구성

• 환경변수 로더 및 설정 파일 정리

• 샘플 ingest 1건과 smoke test 구현

• README / .env.example / HANDOFF 초기화

3. 예상 파일 구조

아래 구조는 예시이지만, 역할 분리가 유지되어야 한다.

경로

역할

src/config/

환경변수, settings, runtime profile

src/db/

Supabase client, schema helpers, migrations notes

src/ingest/sec/

SEC metadata fetch, filings list, raw store

src/parse/xbrl/

EdgarTools wrappers, parser adapters

src/models/

raw/silver/gold domain models

src/jobs/

scheduled ingest, snapshot update, smoke jobs

src/tests/

기본 smoke test와 parser/DB sanity test

docs/

README, HANDOFF, roadmap refs

4. 환경변수 최소 세트

항목

내용

SUPABASE_URL

Supabase 프로젝트 URL

SUPABASE_SERVICE_ROLE_KEY

서버 측 쓰기 작업용 키

OPENAI_API_KEY

후속 AI 계층용. Phase 0에서는 필수 호출 없음

EDGAR_IDENTITY

SEC 접근용 이름 또는 이메일

SENTRY_DSN

선택. 기본 에러/추적 수집용

APP_ENV

local / staging / prod

5. Cursor 실행 순서

□

체크 항목

기준

의존성 추가

requirements.txt 또는 pyproject에 edgartools, supabase client, settings 라이브러리 추가

설정 계층

환경변수 로더와 settings 모델 생성

DB 계층

Supabase client wrapper 및 raw/silver 저장 함수 생성

SEC 계층

issuer filings metadata를 가져오는 최소 fetch 함수 구현

파서 계층

EdgarTools import 및 샘플 financial extraction wrapper 준비

스모크 잡

샘플 issuer 1개를 입력받아 metadata를 저장하는 run script 작성

문서 갱신

README, .env.example, HANDOFF 업데이트

6. 샘플 acceptance test

• 로컬에서 환경변수 주입 후 worker 진입점이 실행된다.

• 샘플 issuer에 대해 SEC filings metadata fetch가 성공한다.

• raw 테이블 또는 raw 저장 경로에 원본 응답이 기록된다.

• silver 테이블 또는 silver 모델에 정규화된 최소 메타데이터가 저장된다.

• 실패 시 에러 로그가 남고, 작업이 조용히 삼켜지지 않는다.

7. 커밋 전 필수 검수

□

체크 항목

기준

실행 명령 문서화

대표님이 복붙 가능한 run/test/install 명령이 README에 있는가

민감정보 분리

실제 키가 repo에 커밋되지 않는가

역할 분리

ingest, parse, db, config가 한 파일에 뒤섞이지 않았는가

문서 최신성

HANDOFF가 현재 구현 상태를 정확히 반영하는가

다음 Phase 연결성

Phase 1이 바로 이어질 수 있도록 issuer master/filings identity의 씨앗이 있는가

8. Cursor에게 명시할 문구

아래 요약은 Cursor Agent에게 그대로 붙여넣을 수 있는 운영 지침으로 사용한다.

항목

내용

핵심 지침

이번 작업은 제품 완성이 아니라 source-of-truth spine 부팅이다. 임시성 편의 구현보다 구조 분리가 우선이다.

주의사항

LLM 중심 기능을 넣지 말고 deterministic ingest와 저장 구조부터 닫아라.

완료 정의

worker 기동, SEC metadata fetch, raw/silver 저장, README/HANDOFF 갱신까지 모두 끝나야 완료다.

보고 형식

변경 파일, 실행 명령, 테스트 결과, 남은 리스크, 다음 1순위를 빠짐없이 보고하라.

9. Phase 0 종료 후 즉시 넘어갈 다음 단계

Phase 0 종료 직후에는 Phase 1로 넘어가 issuer master, filings identity, raw/silver 레이어 고도화, notes/ownership/positioning ingest 스켈레톤 확장에 착수한다. 이때도 point-in-time과 원본 보존 원칙을 흔들지 않는다.
