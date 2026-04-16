# METIS MVP Unified Product Spec — KR v1
# Status: Canonical
# Purpose: Metis MVP의 형태/구조/기능 스펙을 단일 권위 문서로 잠근다.
# Scope: 제품 정의, 시스템 경계, AI 연구실 구조, Today/Research/Replay 계약, 금지사항, 완료 기준
# Supersedes: MVP_ROADMAP_SYNTHESIS_KR_v3, PLAN_MODE_ROADMAP_CURSOR_CONTINUOUS_BUILD, 기존 분산형 북극성/헌법/로드맵 문서의 제품 정의 부분
# Priority Rule: 본 문서와 다른 문서가 충돌할 경우, 본 문서를 우선한다.

---

## 0. 한 문장 정의

Metis는 **public-data-first, point-in-time disciplined truth spine** 위에서,  
**AI-native research engine room**이 생성·검증·승격한 **active horizon model family**를 통해  
사용자에게 **Today / Research / Replay** 형태의 **message-first decision support**를 제공하는  
**research-governed investment operating system**이다.

---

## 1. 이 문서가 해결하는 혼선

이 프로젝트는 그동안 세 종류의 문서가 병렬로 존재했다.

1. 뼈대/기판 중심 문서  
2. Today / Research / Replay 중심 제품 문서  
3. AI Harness / Research Room / Model 승격 논리를 새로 격상한 문서

문제는 이 셋이 각각 맞는 말을 하면서도, 구현자가 읽으면 우선순위를 다르게 해석할 여지가 있었다는 점이다.

본 문서는 다음을 하나로 잠근다.

- 제품의 핵심 얼굴은 **Today / Research / Replay**
- 제품의 지능 중심은 **AI Research Engine Room + Active Horizon Model Registry**
- 제품의 진실성과 재현성은 **Deterministic Truth Spine + Promotion Gate**
- 제품의 설명 가능성과 사용자 가치는 **Message Layer + Replay Layer**
- 제품의 셸/언어/디자인은 중요하지만, **뇌가 없으면 MVP가 완성되지 않는다**

---

## 2. 북극성

### 2.1 북극성 문장
**Today / Research / Replay 3축으로 돌아가는 horizon-aware, replayable decision operating system**

### 2.2 사용자가 얻어야 하는 세 가지
1. 오늘 지금 무엇을 봐야 하는가  
2. 왜 지금 그렇게 받아들여야 하는가  
3. 그 판단을 나중에 어떻게 복기할 수 있는가  

### 2.3 핵심 흐름
**Truth → Model → Message → Decision → Replay**

중요:
- 제품은 raw research viewer가 아니다.
- 제품은 generic AI investing assistant도 아니다.
- 제품은 “추천기”보다는 **attention allocation + interpretation + review loop**를 제공한다.
- Today는 buy/sell 명령 화면이 아니라 **상대적 저평가↔고평가 스펙트럼 보드**다.

---

## 3. 뼈 / 심장 / 뇌 / 피부

이 문서는 제품을 아래 4개 층으로 본다.

### 3.1 Bones — Deterministic Truth Spine
역할:
- SEC / XBRL / market / PIT / availability / alignment / risk-free / replay lineage의 진실성을 담당한다.
- 어떤 데이터가 언제 실제로 알 수 있었는지에 대한 규율을 책임진다.
- AI가 절대 overwrite하거나 우회하면 안 되는 층이다.

포함:
- raw / silver / snapshot / factor / validation / as-of join / price overlay substrate
- signal_available_date / filing lag / revision metadata / horizon labeling
- replay용 timestamp / version / source provenance

원칙:
- Bones는 코드와 스키마가 책임진다.
- Bones는 explanation이 아니라 truth discipline이다.

### 3.2 Heart — AI Research Engine Room
역할:
- 여러 research persona가 model family 후보를 제안·반박·정제하는 백스테이지 연구실이다.
- Heart는 제품의 지능 중심이지만, 사용자 홈의 hero 화면은 아니다.
- Heart는 Today를 직접 쓰지 않고, **artifact packet**을 만든다.

포함 가능 persona 예시:
- Quality / durability
- Value / reversion
- Expectation reset
- Sector specialist
- Regime / risk overlay
- Skeptic / falsifier
- Residual / outlier investigator

원칙:
- Heart는 자유롭게 탐색할 수 있다.
- 그러나 Heart의 출력은 반드시 구조화된 artifact packet이어야 한다.
- Heart는 buy/sell/execute를 대신 결정하지 않는다.

### 3.3 Brain — Active Horizon Model Registry
역할:
- Heart가 만든 후보 중 실제 제품 표면에 올릴 모델군을 채택·보관·버전 관리하는 계층
- 각 시간축별 active model family와 challenger family를 관리
- Today는 오직 Brain만 읽는다

이 문서의 가장 중요한 선언:
**MVP에서 Today의 읽기 전용 입력 소스는 Active Horizon Model Registry뿐이다.**

즉:
- 시드 JSON
- 임시 fixture
- ad hoc research output
- free-form memo
- raw validation table
- 임의의 prompt response
는 Today의 최종 입력 소스가 될 수 없다.

### 3.4 Skin — Product Surface
역할:
- 사용자가 만나는 실제 제품 장면
- Today / Research / Replay / KO/EN / Shell / navigation / visual hierarchy

중요:
- Skin은 필요하지만 Brain이 없는 Skin은 데모용 껍데기에 불과하다.
- MVP는 Skin만으로 닫히지 않는다.

---

## 4. 표면적 긴장에 대한 공식 해석

### 4.1 “연구 엔진은 히어로가 아니다” vs “심장 = 연구 엔진 룸”
둘 다 맞다.

공식 해석:
- **Hero**는 사용자 네비게이션과 홈에서 전면에 보이는 화면을 뜻한다.
- **Heart**는 제품의 지능 중심이자 백스테이지 연구 파이프라인을 뜻한다.

따라서:
- Hero = Today / Research / Replay
- Heart = AI Research Engine Room

즉:
- Research engine은 제품의 지능 중심이다.
- 그러나 홈에서 사용자가 먼저 보는 히어로 스크린은 아니다.

### 4.2 “엔진을 더 쌓는 계획이 아니다” vs 모델 코어 고도화
공식 해석:
- **Infrastructure accretion**을 더 쌓는 것은 MVP의 우선순위가 아니다.
- 그러나 **Brain 구현**은 “엔진 과다”가 아니라 MVP 필수 조건이다.

한 줄로 잠근다:
**인프라 과다 ≠ 뇌 구현이다.**
Truth substrate를 끝없이 더 쌓는 것은 나중으로 미룰 수 있지만,
active horizon model family와 promotion gate를 닫는 일은 MVP 중심부다.

### 4.3 “Today는 추천/매수매도 화면이 아니다” vs 스펙트럼·밴딩
둘 다 맞다.

공식 해석:
- Today는 구조화된 상대 우위/위험 스펙트럼이다.
- 밴딩과 action framing은 허용된다.
- buy / sell / execute / should buy now 같은 규제 모호 문구는 금지한다.

---

## 5. 제품의 실제 영웅 장면

## 5.1 Today
Today는 제품의 핵심 얼굴이다.

Today가 보여줘야 하는 것:
- 시간축 버튼: short / medium / medium-long / long
- 각 시간축별 active model family 표시
- underpriced ↔ overpriced spectrum
- banding: extreme underpriced / underpriced / neutral / overpriced / extreme overpriced
- one-line message
- rationale summary
- watchlist filter
- rank movement
- pseudo-real-time price-linked reranking

Today의 본질:
- 하나의 만능 모델이 종목을 줄 세우는 것이 아니다.
- 각 시간축별 현재 active family가 따로 존재할 수 있다.
- 동일 종목은 시간축에 따라 위치가 달라질 수 있다.

금지:
- 추천/주문/집행 중심 UI
- raw factor table를 히어로 카드로 올리는 것
- research-state dashboard로 후퇴하는 것

## 5.2 Research
Research는 엔진 자랑 공간이 아니다.

Research의 역할:
- message → information → deeper rationale
- Ask AI
- bounded custom sandbox
- disagreement preserving explanation
- what changed / what remains unproven / what to watch

Research는 사용자가 더 깊게 들어가는 공간이지,
raw engine telemetry를 전면에 노출하는 공간이 아니다.

## 5.3 Replay
Replay는 시그니처 웨지다.

반드시 포함:
- reality replay
- counterfactual replay
- decision trace
- 당시 active family / message / outcome 연결
- now/then 비교

Replay는 재미 요소가 아니라
이 제품이 “리서치 소프트웨어”가 아니라 “의사결정 소프트웨어”가 되게 하는 핵심 층이다.

---

## 6. MVP의 중심 객체들

## 6.1 Model Artifact Packet
Heart의 기본 출력 단위다.

모든 AI research persona 또는 deterministic kernel은 자유 텍스트 대신 아래 구조를 생산해야 한다.

필수 필드:
- artifact_id
- created_at
- created_by (agent/persona/kernel)
- horizon
- universe
- sector_scope
- thesis_family
- feature_set
- feature_transforms
- weighting_rule
- score_formula
- banding_rule
- ranking_direction
- invalidation_conditions
- expected_holding_horizon
- confidence_rule
- evidence_requirements
- validation_pointer
- replay_eligibility
- notes_for_message_layer

원칙:
- packet이 없으면 승격도 없다.
- packet 없는 natural-language suggestion은 Today에 들어갈 수 없다.

## 6.2 Promotion Gate Record
Artifact가 Brain으로 올라가기 위한 심사 기록이다.

필수 필드:
- artifact_id
- evaluation_run_id
- pit_pass
- coverage_pass
- monotonicity_pass
- regime_notes
- sector_override_notes
- challenger_or_active
- approved_by_rule
- approved_at
- supersedes_registry_entry
- reasons
- expiry_or_recheck_rule

## 6.3 Active Horizon Model Registry Entry
Today가 직접 읽는 최종 레코드다.

필수 필드:
- registry_entry_id
- horizon
- active_model_family_name
- active_artifact_id
- challenger_artifact_ids
- universe
- sector_scope
- effective_from
- effective_to
- scoring_endpoint_contract
- message_contract_version
- replay_lineage_pointer
- status

선언:
- Today는 registry entry만 읽는다.
- Research는 registry + message + evidence를 읽는다.
- Replay는 registry lineage + message snapshot + outcome를 읽는다.

## 6.4 Message Object
Message Layer v1의 기본 단위다.

필수 필드:
- headline
- why_now
- what_changed
- what_remains_unproven
- what_to_watch
- action_frame
- confidence_band
- linked_evidence
- linked_registry_entry_id
- linked_artifact_id

원칙:
- memo 품질이 message object를 대체할 수 없다.
- message object는 제품 1급 객체다.

---

## 7. AI-native Research Room의 자유와 경계

## 7.1 허용
- 다관점 persona 운용
- 서로 다른 horizon family 제안
- sector-specific lens 제안
- challenger 모델 제안
- 기존 모델 반박
- outlier case investigation
- disagreement preserving notes

## 7.2 금지
- PIT 규율 무시
- validation 없이 Today 게시
- free-form memo만으로 모델 승격
- 매 턴마다 score semantics를 제멋대로 변경
- buy/sell/execute를 검증 결과 대체물로 사용하는 것
- 제품 표면이 registry를 우회하는 것

## 7.3 기본 원칙
**탐색은 자유롭게, 출력은 구조화해서, 채택은 검증 규칙으로, 사용자 노출은 registry만.**

---

## 8. MVP 범위와 제외 범위

### 8.1 MVP에 반드시 포함
1. Artifact v0
2. Promotion Gate v0
3. Active Horizon Model Registry v0
4. Today read-only source swap (시드 → registry)
5. spectrum scoring + banding
6. Message Layer v1
7. rationale summary
8. watchlist ordering
9. Research hierarchy
10. Ask AI prompt set
11. bounded sandbox 최소 작동
12. reality replay
13. counterfactual replay
14. frozen snapshot + price overlay
15. KO/EN polish

### 8.2 MVP에서 제외
- fully autonomous trading
- broker execution
- unrestricted general-purpose agent swarm
- full multi-asset breadth
- full team permission system
- massive premium-data expansion
- “가장 정확한 모델” 류의 과장 카피

---

## 9. 현재 코드 상태를 이 문서가 어떻게 재해석하는가

현재까지 구현된 뼈대와 하네스는 버리는 것이 아니다.
그것들은 Bones와 일부 Heart substrate로 재해석된다.

그러나 본 문서 기준으로 아직 닫히지 않은 핵심은 다음이다.
- Brain = Active Horizon Model Registry
- Artifact → Promotion → Registry 브리지
- Today의 입력 소스 계약
- message object의 1급 객체화
- replay lineage의 registry 연결

즉:
지금까지 만든 것은 필요하다.
하지만 그것만으로 MVP는 닫히지 않는다.

---

## 10. MVP 완료의 공식 판정 기준

MVP 완료는 아래 질문에 모두 “예”여야 한다.

1. Today가 registry만 읽는가?
2. 각 시간축에 active family가 존재하는가?
3. challenger/active 구분이 존재하는가?
4. artifact packet 없이 모델이 Today에 올라갈 수 없는가?
5. message object가 memo와 분리된 1급 객체인가?
6. 종목 카드가 headline + why_now + rationale summary를 제공하는가?
7. same name이 horizon에 따라 다른 위치를 가질 수 있는가?
8. price overlay가 rank movement를 바꾸는가?
9. Research가 message → information → deeper rationale 순서를 지키는가?
10. Replay가 당시 active family와 이후 결과를 연결하는가?

하나라도 아니오면 MVP는 미완료다.

---

## 11. 구현자 규율

- 뇌 없는 스킨 패치 금지
- registry 우회 금지
- seed fixture를 장기 구조로 오인 금지
- “하네스가 있으니 모델 코어도 있다”는 오판 금지
- validation path와 production path 무질서 결합 금지
- buy/sell 표현으로 모델 검증 부족을 가리는 것 금지
- “나중에 붙일 예정”으로 Brain을 뒤로 미루는 것 금지

---

## 12. 문서 우선순위 규칙

본 문서는 제품 형태/구조/기능 정의에 관한 유일한 권위 문서다.

따라서:
- 기존 MVP_ROADMAP_SYNTHESIS_KR_v3의 제품 정의는 본 문서에 흡수된다.
- 기존 PLAN_MODE_ROADMAP_CURSOR_CONTINUOUS_BUILD의 철학 및 phase 언어는 본 문서에 종속된다.
- 기존 North Star / handoff / constitution patch / audit 문서들은 보조 참고 문서다.
- 새 패치, Cursor handoff, phase workorder는 본 문서를 직접 참조해야 한다.

---

## 13. 구현자가 다음 턴부터 기억해야 할 한 문장

**Metis MVP는 Today / Research / Replay의 껍데기를 만드는 작업이 아니라, AI Research Engine Room이 생성·검증·승격한 active horizon model family를 registry를 통해 Today에 공급하고, message와 replay까지 이어지게 만드는 작업이다.**
