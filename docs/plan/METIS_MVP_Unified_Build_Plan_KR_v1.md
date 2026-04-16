# METIS MVP Unified Build Plan — KR v1
# Status: Canonical
# Purpose: Metis MVP를 최단거리로 구현하기 위한 단일 로드맵/세부 실행 플랜
# Scope: 선행 관계, 스프린트 정의, 산출물, acceptance, 금지사항, 현재 코드 기준 패치 우선순위
# Supersedes: PLAN_MODE_ROADMAP_CURSOR_CONTINUOUS_BUILD, MVP_ROADMAP_SYNTHESIS_KR_v3의 실행 계획 부분
# Priority Rule: 본 문서와 다른 구현 계획 문서가 충돌할 경우, 본 문서를 우선한다.

---

## 0. 이 플랜의 기본 원칙

이 플랜은 “엔진을 더 많이 쌓는 계획”이 아니다.
정확히는 다음이다.

- **인프라 과다를 멈춘다**
- **Brain과 Heart를 제품 표면에 연결한다**
- **Today / Research / Replay의 투자자 데모 장면을 닫는다**

한 줄 요약:
**Metis MVP의 선행 과제는 스킨이 아니라 Brain이다.**

---

## 1. 현재 상태 요약

이미 있는 것:
- deterministic truth spine
- factor/validation substrate
- 일부 state_change baseline
- memo/harness substrate
- browser shell
- Today/Research/Replay 방향성
- trust/health/injest 일부

> **진척 갱신 (2026-04):** Artifact·Promotion Gate·Registry 스키마와 번들 검증, Today의 registry 우선 입력, factor_validation→게이트/번들 빌드 CLI, 메시지 스냅샷·Research/Ask 연동 등이 코드에 반영됨. §1 아래 “아직 없는 것”은 문서 최초 작성 시점 기준이며, **현재 스펙 대비 갭·스프린트 우선순위**는 `docs/plan/METIS_MVP_PROGRESS_VS_SPEC_KR_v1.md`를 본다.

아직 없는 것:
- active horizon model registry
- artifact packet contract
- promotion gate
- Today의 registry read-only wiring
- model artifact ↔ message object 연결
- registry lineage ↔ replay linkage

따라서 첫 구현 우선순위는 “UI polish”가 아니라 **Artifact → Registry → Today 브리지**다.

---

## 2. 전체 구현 순서

본 플랜은 번호를 아래처럼 잠근다.

### Stage 0 — Brain Lock
Artifact v0 + Promotion Gate v0 + Registry v0 + Today 입력 소스 계약

### Stage 1 — Today Vertical Slice
Today가 registry를 읽고 spectrum/banding/message/rank movement를 보여주는 최소 수직 슬라이스

### Stage 2 — Message Layer v1
message object를 1급 객체로 세우고 memo와 분리

### Stage 3 — Research Surface Minimum
message → information → deeper rationale + Ask AI + bounded sandbox 최소 동작

### Stage 4 — Replay Vertical Slice
reality replay + counterfactual replay를 registry lineage와 연결

### Stage 5 — Shell / Language / Demo Freeze
47d/47e / KO-EN / frozen snapshot / price overlay / demo polish

### Stage 6 — Trust Closeout
53류 trust/hardening을 MVP 데모 신뢰 수준까지 닫기

---

## 3. Stage 0 — Brain Lock

### 3.1 목표
Metis MVP의 뇌를 코드와 데이터 모델 수준에서 명시적으로 세운다.

### 3.2 이유
지금까지의 가장 큰 구조 갭은
“모델 후보가 어디서 어떻게 만들어져 어떤 규칙으로 Today에 올라오는가”가
제품 계약으로 닫혀 있지 않다는 점이다.

### 3.3 필수 산출물
1. Model Artifact Packet v0 스키마
2. Promotion Gate Record v0 스키마
3. Active Horizon Model Registry v0 스키마
4. Registry read-only contract for Today
5. artifact/challenger/active 상태 정의
6. 최소 horizon 집합 정의
7. 최소 universe 정의

### 3.4 최소 범위
- horizon 3개 또는 4개
- universe 1개 (예: large-cap research slice)
- sector override는 선택적
- active 각 horizon당 1개
- challenger 각 horizon당 0~2개

### 3.5 Acceptance
- 시드 fixture가 아니라 registry entry를 직접 만들 수 있다
- Today 컴포넌트가 registry contract를 읽을 수 있다
- artifact packet 없이는 active family를 생성할 수 없다
- registry entry에 replay lineage pointer가 존재한다

### 3.6 금지
- UI부터 먼저 고치는 것
- memo 결과를 registry 대체로 쓰는 것
- free-form prompt output을 직접 Today에 연결하는 것

---

## 4. Stage 1 — Today Vertical Slice

### 4.1 목표
Today의 입력을 시드/fixture에서 registry로 바꾸고,
최소한의 underpriced↔overpriced spectrum board를 실제로 작동시킨다.

### 4.2 필수 산출물
1. horizon selector
2. registry-backed model family fetch
3. spectrum scoring endpoint or adapter
4. color banding
5. one-line message slot
6. rationale summary slot
7. rank movement slot
8. watchlist ordering
9. price overlay 반영

### 4.3 Acceptance
- horizon을 바꾸면 다른 registry entry가 보인다
- 같은 종목이 horizon에 따라 다른 위치를 가질 수 있다
- Today가 seed JSON 없이 동작한다
- price overlay로 rank movement가 바뀐다
- watchlist만 재정렬 가능하다

### 4.4 Hard No
- Today를 연구 상태판처럼 만드는 것
- factor raw table를 hero surface로 노출
- buy/sell 카피를 성급하게 넣는 것

---

## 5. Stage 2 — Message Layer v1

### 5.1 목표
Message를 memo의 부산물이 아니라 제품 1급 객체로 만든다.

### 5.2 필수 산출물
1. message object schema
2. artifact packet → message generation contract
3. registry entry → message linkage
4. headline / why_now / what_changed / what_remains_unproven / what_to_watch / action_frame / confidence_band
5. linked_evidence pointer

### 5.3 Acceptance
- Today 카드가 정보표가 아니라 message card로 보인다
- message object가 저장/조회 가능하다
- message가 memo와 독립된 객체다
- Research와 Replay가 같은 message snapshot을 참조한다

### 5.4 Hard No
- memo_builder 품질을 message layer 완료로 간주
- 카드 카피만 고쳐서 message layer를 대체
- linked_evidence 없이 감성 카피만 만드는 것

---

## 6. Stage 3 — Research Surface Minimum

### 6.1 목표
Research를 engine brag zone이 아니라 심화 탐색 공간으로 만든다.

### 6.2 필수 산출물
1. Detail hierarchy: message → information → deeper rationale
2. Ask AI prompt set
3. bounded sandbox input form
4. bounded sandbox result view
5. horizon/lens 비교
6. disagreement-preserving explanation

### 6.3 Acceptance
- 상세 화면 첫 블록이 message다
- Ask AI가 why now / what changed / what to watch를 대답한다
- 사용자가 제한된 구조 안에서 hypothesis를 입력할 수 있다
- 결과가 horizon별 차이를 보여준다

### 6.4 Hard No
- unrestricted free chat sandbox
- 내부 명령어 같은 UX
- raw telemetry dump

---

## 7. Stage 4 — Replay Vertical Slice

### 7.1 목표
Replay를 재미 요소가 아니라 의사결정 학습 루프로 닫는다.

### 7.2 필수 산출물
1. reality replay flow
2. counterfactual replay templates
3. timeline view
4. Today → Replay deep link
5. registry lineage linkage
6. message snapshot linkage

### 7.3 Acceptance
- 당시 active model family가 무엇이었는지 보인다
- 당시 message와 이후 결과가 연결된다
- 최소 4개의 counterfactual template이 작동한다
- Today 카드에서 replay 진입이 가능하다

### 7.4 Hard No
- replay가 registry lineage 없이 추상 설명으로만 존재
- 재미있는 what-if toy로만 남는 것

---

## 8. Stage 5 — Shell / Language / Demo Freeze

### 8.1 목표
이미 작업 중인 47d/47e와 shell polish를 뇌/메시지/리플레이 위에 맞게 닫는다.

### 8.2 필수 산출물
1. Today-first home
2. KO/EN natural product language
3. empty/loading/error states rewrite
4. frozen snapshot pack
5. price overlay demo mode
6. high-end card hierarchy
7. investor demo route

### 8.3 Acceptance
- 첫 화면이 Today 중심이다
- 내부 운영어가 사라진다
- 국문/영문 모두 자연스럽다
- 같은 frozen snapshot 위에서 데모가 재현 가능하다

### 8.4 Hard No
- shell이 뇌보다 앞서가게 방치
- 디자인이 registry 미구현을 가리는 가림막이 되는 것

---

## 9. Stage 6 — Trust Closeout

### 9.1 목표
신뢰/운영/하드닝을 MVP 데모 수준으로 닫는다.

### 9.2 필수 산출물
1. signed payload/HMAC closeout
2. dead-letter / replay protection
3. health parity
4. lineage tracing
5. demo observability surface

### 9.3 Acceptance
- ingest와 runtime 상태가 추적 가능하다
- artifact → registry → message → replay 흐름이 추적 가능하다
- failure modes가 조용히 삼켜지지 않는다

### 9.4 Hard No
- Trust patch가 Brain 선행 작업을 밀어내는 것
- observability만 늘리고 product core를 미루는 것

---

## 10. 현재 코드 기준 최우선 패치 묶음

### Patch Bundle A — Artifact v0 / Registry v0 / Today Source Swap
가장 먼저 해야 한다.

포함:
- artifact schema
- promotion gate schema
- registry schema
- registry service/adapter
- Today input swap stub
- seed fallback 제거 또는 테스트 전용 격리

### Patch Bundle B — Message Contract v1
A 직후.

포함:
- message schema
- message generation contract
- rationale summary contract
- linked evidence structure

### Patch Bundle C — Replay Lineage v1
B 직후.

포함:
- registry lineage pointer
- message snapshot pointer
- decision ledger minimal join

### Patch Bundle D — Research / Sandbox Minimum
C 이후.

### Patch Bundle E — Shell / KO-EN / Demo Freeze
D 이후.

### Patch Bundle F — Trust Closeout
E 이후.

---

## 11. 14일 압축 플랜

### Day 1–2
- Artifact v0
- Promotion Gate v0
- Registry v0
- Today source contract lock

게이트:
- registry entry를 만들고 읽을 수 있어야 한다

### Day 3–5
- Today source swap
- spectrum scoring adapter
- banding
- watchlist ordering
- rank movement

게이트:
- same name이 horizon에 따라 다른 위치를 가져야 한다

### Day 5–7
- Message Layer v1
- rationale summary
- linked evidence
- card contract

게이트:
- Today 카드가 message-first여야 한다

### Day 7–9
- Detail / Ask AI / bounded sandbox minimum

게이트:
- Research가 message → information → deeper rationale를 지켜야 한다

### Day 9–11
- Replay lineage
- reality replay
- counterfactual templates

게이트:
- Today에서 Replay로 자연스럽게 넘어가야 한다

### Day 11–14
- 47d/47e 보정
- frozen snapshot
- price overlay
- demo script
- trust closeout 최소

게이트:
- 투자자 앞에서 10분 내 가치 전달 가능

---

## 12. 구현 중 항상 지킬 문장

1. Today는 registry만 읽는다.  
2. Artifact 없는 모델은 없다.  
3. Memo는 message를 대체하지 못한다.  
4. Heart는 자유롭되, Brain은 엄격해야 한다.  
5. Skin은 Brain 위에 닫힌다.  
6. Replay는 lineage 없이는 성립하지 않는다.  

---

## 13. 기존 문서와의 관계

- 기존 Plan Mode의 phase 번호와 장기 철학은 참고 가능하다.
- 하지만 MVP 구현 우선순위는 본 문서가 다시 잠근다.
- 기존 MVP_ROADMAP_SYNTHESIS의 Today / Research / Replay 장면 정의는 유지한다.
- 기존 handoff의 wedge / message-first / replayable decision memory 정의는 유지한다.
- 기존 constitution patch와 audit에서 드러난 Brain gap은 본 문서가 선행 과제로 격상한다.

---

## 14. 구현자가 지금 당장 시작해야 할 첫 수직 슬라이스

**Artifact v0 + Registry v0 + Today 입력을 시드에서 registry로 바꾸는 최소 수직 슬라이스**

이것이 닫히기 전까지는:
- 추가 UI polish
- 추가 shell 패치
- 추가 trust ornament
- 추가 memo embellishment
를 MVP 진전으로 간주하지 않는다.
