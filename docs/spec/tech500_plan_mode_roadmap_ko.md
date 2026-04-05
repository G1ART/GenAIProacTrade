# tech500 plan mode roadmap ko

> 원본: `tech500_plan_mode_roadmap_ko.docx` — 레포 내 보관용 자동 추출본(표·머리글은 단순화됨).

Tech500 Factor Engine / AI Harness OS

Plan Mode Roadmap v1

문서 유형

구현 단계 계획 문서

버전

v1.0

상태

초안 고정본

상위 문서

최상위 제품 스펙 문서

이 문서는 구현 경로를 고정하기 위한 운영 문서입니다. 상위 제품 스펙 문서와 모순되게 해석해서는 안 되며, 구현 중 판단이 충돌할 경우 항상 상위 문서를 우선합니다.

1. 로드맵 목적

이 로드맵은 제품 스펙을 실제 구현 단계로 분해한 계획 문서다. 각 Phase는 산출물, 선행조건, 리스크, 종료 조건을 함께 갖는다. Phase를 건너뛰거나 순서를 뒤집지 않는 것이 원칙이다.

2. 전체 경로 요약

Phase

핵심 결과물

Phase 0

Constitution Lock + Infra Bootstrap

Phase 1

Source-of-Truth Lake + Issuer Master

Phase 2

Core Factor Engine + Backtest Baseline

Phase 3

State Change Engine + Alert Semantics

Phase 4

AI Harness Layer + Decision Memo System

Phase 5

Outlier Casebook + Daily Scanner

Phase 6

Hardening, Observability, Research Registry

3. Phase 0 — Constitution Lock + Infra Bootstrap

목표는 제품 진실 엔진이 놓일 최소 인프라를 고정하는 것이다. 여기서는 Supabase, Railway worker, 필수 환경변수, XBRL 파싱 레이어, observability 뼈대, 저장 구조의 골격을 만든다.

• 프로젝트 레포 초기화 및 worker 서비스 부팅

• Supabase 연결 및 raw/silver/gold 기본 테이블 설계

• EdgarTools 설치 및 SEC identity 설정

• Sentry 또는 기본 tracing 계층 연결

• 기본 README / HANDOFF / 환경변수 템플릿 생성

종료 조건: 워커가 기동되고, SEC에서 한 개 issuer의 filings metadata를 가져와 raw와 silver에 저장할 수 있어야 한다.

4. Phase 1 — Source-of-Truth Lake + Issuer Master

이 Phase는 제품의 기초 체력이다. CIK 중심 issuer master를 만들고, filings / notes / insider / 13F / ownership / short / macro / news의 수용 스키마를 고정한다.

• issuer_id, ticker history, status, SIC를 포함한 issuer master 확정

• raw immutable ingest와 normalized silver 모델 분리

• accepted timestamp, filing date, period end, revision metadata 저장

• 데이터 소스별 ingestor skeleton 마련

종료 조건: 최소 10개 샘플 issuer에 대해 raw → silver 파이프라인이 일관되게 동작해야 한다.

5. Phase 2 — Core Factor Engine + Backtest Baseline

초기 6개 팩터를 deterministic하게 계산하고, raw/excess return 기준의 최소 백테스트 기반을 구축한다. 이때 계산은 LLM이 아니라 코드가 책임진다.

• accruals, gross profitability, asset growth, capex intensity, R&D intensity, composite strength 계산

• snapshot 모델과 as-of join 규칙 고정

• 기초 ranking, spread, turnover, transaction cost baseline 구현

종료 조건: 테스트 유니버스에서 월간 또는 분기 snapshot과 factor panel이 재현 가능하게 생성되어야 한다.

6. Phase 3 — State Change Engine + Alert Semantics

이 Phase에서 제품은 market-reactive 스캐너를 넘어 market-productive state-change 시스템으로 전환된다. 핵심 지표는 Level, Velocity, Acceleration, Persistence, Contamination, Regime Fit이다.

항목

내용

Level

현재 괴리 또는 상태가 어느 정도 크기인가

Velocity

그 상태가 어떤 방향으로 얼마나 빠르게 움직이는가

Acceleration

변화 속도 자체가 강화되는가 둔화되는가

Persistence

일시적 스파이크가 아니라 지속적 전이인가

Contamination

오너·규제·crowding·뉴스로 core signal이 오염됐는가

Regime Fit

현재 거시·시장 국면에서 이 신호가 유효할 가능성이 높은가

종료 조건: 단일 절대값이 아니라 상태전이 기반 alert score를 산출할 수 있어야 한다.

7. Phase 4 — AI Harness Layer + Decision Memo System

이 Phase에서 AI는 숫자 계산자가 아니라 조사실로 작동한다. Filing Intelligence, Verification, Narrative, Counter-Case, Memo Agent를 두고, 인간이 이해 가능한 메시지와 메모를 생성한다.

• 구조화된 claim schema 도입

• agent trace와 근거 연결

• Alert / Tactical Brief / CIO Memo 출력 체계 구축

• 확인됨 / 유력한 가설 / 확인 불가 구분 고정

종료 조건: 이상치 1건에 대해 멀티에이전트 조사와 결정 메모 생성이 가능해야 한다.

8. Phase 5 — Outlier Casebook + Daily Scanner

이 Phase에서 제품은 운영 툴로 전환된다. 재무신호와 실제 가격 반응의 괴리가 큰 종목을 casebook으로 남기고, 매일 actionable watchlist를 생성한다.

• 잔차 기반 우선순위 큐

• 뉴스·ownership·포지셔닝과의 연결 설명

• 저밀도 알림이 아니라 의미 번역형 메시지 제공

종료 조건: 장 마감 후 또는 지정 시각에 daily signal snapshot과 우선순위 알림이 생성되어야 한다.

9. Phase 6 — Hardening, Observability, Research Registry

마지막 Phase는 안정성과 확장성을 닫는 단계다. 여기서는 tracing, failure alert, research hypothesis registry, 신규 팩터 검정 큐를 정비한다.

• 실패한 ingest / parser / agent run 추적

• 비용, 지연, 토큰 사용량, 실패율 관찰

• 신규 팩터의 가설 등록과 승격/폐기 규칙 구축

종료 조건: 운영 중 오류가 나도 원인을 추적할 수 있고, 신규 연구가 본선 코드와 무질서하게 섞이지 않아야 한다.

10. 로드맵 운용 규칙

□

체크 항목

기준

Phase 건너뛰기 금지

상위 Phase 미완료 상태에서 하위 Phase 구현으로 점프하지 않는다

종료 기준 명시

각 Phase는 완료 요건을 충족해야만 다음으로 넘어간다

문서 동기화

Phase 종료 시 제품 스펙과 HANDOFF를 함께 갱신한다

리스크 기록

남은 리스크를 숨기지 않고 다음 Phase로 명시적으로 이월한다
