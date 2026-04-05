# tech500 factor ai architecture blueprint ko v2

> 원본: `tech500_factor_ai_architecture_blueprint_ko_v2.docx` — 레포 내 보관용 자동 추출본(표·머리글은 단순화됨).

Public-Market Knowledge Graph +Tech500 Factor Engine + AI Harness OS

통합 프로덕트 아키텍처 설계도대화 기반 통합본 · 플랜 모드 로드맵 및 구현 경로의 기준 문서

항목

내용

문서 목적

공개 시장 데이터의 point-in-time 진실 저장소 위에서 deterministic state-change/factor engine과 agentic research harness를 결합한 투자 조사·의사결정 운영체계

제품 정의

숫자는 deterministic, 상태 변화 감지는 state-change engine, 의미 해석은 agentic, 최종 결정은 human-supervised

설계 원칙

숫자는 deterministic, 의미 해석은 agentic, 최종 결정은 human-supervised

사용 방식

이 문서를 기준 헌법으로 삼고, 이후 세부 로드맵·작업지시서·검수 기준은 모두 여기서 파생한다.

Status: Constitution-level product specification for roadmap, implementation, and review discipline

1. Executive Summary

우리가 만드는 것은 단순한 팩터 스캐너도, 단순한 AI 요약 툴도 아닙니다. 제품의 중심은 세 층으로 구성됩니다. 첫째, 공시·가격·소유구조·포지셔닝·거시·뉴스를 point-in-time 기준으로 보존하는 Truth Engine입니다. 둘째, 그 위에서 절대 갭뿐 아니라 상태 변화의 속도와 가속도를 읽어 선제 신호를 만드는 State Change & Factor Engine입니다. 셋째, 그 신호와 잔차를 병렬 조사·반론·메시지로 번역하는 AI Harness & Decision Layer입니다. 즉, 이 제품은 market-reactive 이벤트 추종기가 아니라, 공개 지표의 상태전이를 먼저 감지해 인간의 결정을 앞당기는 market-productive operating system입니다.

이 문서의 목적은 기능 나열이 아니라, 무엇을 절대로 잘못 만들지 않을지를 먼저 고정하는 데 있습니다. 모든 숫자와 시간축은 코드와 검증기로 결정되고, AI는 의미 추출·원인 탐색·반론 구성·메시지 작성에 집중합니다. 알림은 작은 노이즈에 과민하게 반응해서는 안 되며, 수준(Level)·속도(Velocity)·가속도(Acceleration)·지속성(Persistence)·오염도(Contamination)·레짐 적합도(Regime Fit)를 함께 고려해 의미 있는 상태 변화만 인간에게 전달해야 합니다. 따라서 제품은 스크리너가 아니라, 조기경보·조사·설명·결정지원이 결합된 투자 조사실 운영체계입니다.

2. 헌법급 설계 원칙

2.1 절대 원칙

• 숫자 계산, point-in-time 가용성 판정, 팩터 산식, 거래비용 반영, 리밸런싱 로직은 deterministic code만 담당한다.

• AI는 구조화 추출, 주석 해석, 사건 연결, 잔차 원인 조사, 반론 정리, 인간용 메모 작성에 집중한다.

• 모든 해석은 ‘확인됨’, ‘유력한 가설’, ‘확인 불가’ 중 하나로 표기한다.

• 원본(raw)은 절대 덮어쓰지 않는다. 정정 공시, 재처리, 재해석은 revision으로 추가한다.

• 모든 판단은 trace가 있어야 하며, 나중에 어떤 데이터와 어떤 claim이 그 판단을 만들었는지 거슬러 올라갈 수 있어야 한다.

• 프로덕션 승격은 연구 성공과 동일하지 않다. out-of-sample, turnover, cost-adjusted, regime stability를 통과한 것만 운영 엔진으로 승격한다.

2.2 제품이 피해야 할 실패 패턴

실패 패턴

무엇이 문제인가

설계 대응

Look-ahead bias

나중에 공개된 정보를 과거 전략에 섞으면 백테스트가 거짓이 된다.

accepted timestamp, available_ts, revision_ts를 별도 저장하고 event-time join만 허용

생존편향

살아남은 종목만으로 과거를 보면 성과가 과대평가된다.

listing lifecycle과 delisting-aware price layer를 별도 관리

거래비용 무시

논문상 유의한 신호도 실전에서는 사라질 수 있다.

gross와 net 결과를 분리하고 turnover 기반 비용 차감을 기본값으로 강제

팩터 남발

조합을 무한 생성하면 우연 적합이 늘어난다.

가설 레지스트리와 승격 절차를 강제

AI 과권한

LLM이 숫자 진실을 만들면 검증이 무너진다.

AI는 주장만 하고, 숫자 확정은 룰 엔진이 담당

설명 없는 신호

왜 맞았고 왜 틀렸는지 모르면 운영화가 불가능하다.

outlier casebook과 counter-case agent를 제품 중심에 둔다

3. 제품 정의와 북극성

제품의 공식 정의는 다음과 같습니다. ‘미국 상장 기술주 Top 500 유니버스를 분기별로 재구성하면서, 공개된 규제·시장·거시·뉴스 데이터를 point-in-time 기준으로 보존하고, 그 위에서 deterministic state-change/factor engine과 agentic research harness를 결합해, mispricing 후보 탐지 → 원인 조사 → 인간 의사결정 지원까지 연결하는 investment operating system.’ 여기서 핵심은 가격 반응 그 자체가 아니라, 가격 반응을 낳는 상태 변화의 조기 탐지입니다.

북극성은 단일 질문으로 요약됩니다. ‘지금 시점에서, 공개 데이터가 말하는 펀더멘털과 시장 가격 사이의 괴리를 얼마나 신뢰 가능하게 찾고, 그 괴리의 방향과 변화 속도를 얼마나 빨리 인간의 결정으로 연결할 수 있는가.’ 따라서 이 제품은 추천 엔진이 아니라, 진실 보존형 상태전이 감지기이자 메시지 번역기입니다.

3.1 market-reactive가 아닌 market-productive 제품 정의

시장반응형 제품은 이미 널리 알려진 이벤트나 가격 움직임을 뒤쫓습니다. 예를 들어 지수 편입·편출, 뉴스 헤드라인, 단순 실적 서프라이즈 이후의 가격 점프를 신호로 삼는 방식입니다. 반면 이 제품은 그런 결과 이벤트를 그대로 쫓지 않습니다. 대신 그 결과를 낳는 공개 지표의 상태전이, 즉 펀더멘털과 시장 인식 구조가 바뀌는 초입을 먼저 찾는 데 집중합니다. 따라서 제품의 질문도 “무슨 이벤트가 일어났는가”보다 “무엇이 바뀌고 있으며, 그 변화가 시장 가격에 아직 충분히 반영되지 않았는가”가 됩니다.

구분

Market-reactive

Market-productive

기준 신호

이미 관측된 이벤트·가격 반응

이벤트를 낳는 상태 변화와 구조적 전이

주된 질문

무슨 일이 발생했는가

무엇이 바뀌고 있으며 얼마나 빨라지는가

타이밍

사후 대응 중심

사전 경보·선제 관찰 중심

AI의 역할

뉴스 요약과 해설

이질적 공개 데이터를 연결해 변화의 의미와 오염도를 번역

3.2 상태전이(State Change) 관점과 사용자 가치

제품은 단순한 절대 갭만 보지 않습니다. 같은 갭이라도 개선 속도가 붙는지, 악화가 둔화되는지, 단기 노이즈인지, 여러 공개 데이터 소스가 같은 방향을 가리키는지에 따라 의미가 완전히 달라지기 때문입니다. 따라서 이 제품의 핵심 관찰 대상은 값 자체가 아니라 값의 움직임이며, 특히 “수준 + 속도 + 가속도 + 지속성”의 조합입니다.

• Level: 현재 갭의 절대 크기. 지금 상태가 얼마나 벌어져 있는가를 본다.

• Velocity: 갭의 1차 변화율. 개선/악화가 어느 속도로 진행되는지 본다.

• Acceleration: 갭의 2차 변화율. 변화 속도 자체가 더 붙는지, 둔화되는지 본다.

• Persistence: 변화가 일시적 스파이크인지, 여러 관측 구간에 걸쳐 유지되는지 본다.

• Contamination: founder/CEO 뉴스, 규제 이슈, crowded positioning 같은 외생 오염이 신호를 왜곡하는지 본다.

• Regime Fit: 현재 거시·섹터 환경에서 해당 신호가 역사적으로 얼마나 전달되기 쉬운지 본다.

이 구조의 최종 산출물은 “매수/매도 버튼”이 아니라 메시지입니다. 저수준 개인 투자자에게도 유용한 툴이 되려면, 시스템은 숫자와 잡음을 그대로 던지는 대신 “무엇이 바뀌었는가, 왜 중요한가, 아직 무엇은 미확인인가, 지금은 관찰/분할진입/보류 중 무엇이 적절한가”를 사람말로 번역해야 합니다. 즉, 이 제품의 대중적 가치는 예측의 과장이 아니라 공개 정보의 조기경보와 의미 번역에 있습니다.

4. 통합 아키텍처 개요

4.1 전체 레이어 구조

Layer

이름

역할

산출물

L1

Source Ingestion

SEC, ownership, short, macro, news를 raw로 적재

원본 파일·응답·해시

L2

Point-in-Time Lake

시간축·식별자·revision을 정규화

issuer/security/event 기준 normalized tables

L3

State Change & Deterministic Factor Engine

절대 갭, 속도, 가속도, 지속성, 오염도, 레짐 적합도를 계산하고 유니버스 재구성, 팩터 계산, 회귀·백테스트, residual 계산을 수행

state change panel, factor panel, rankings, backtests

L4

AI Harness Layer

추출, 해석, 반론, 아웃라이어 조사, memo 생성

claims, hypotheses, memos

L5

Decision Cockpit

watchlist, alert, tactical brief, CIO memo를 인간에게 제공

결정 가능한 화면·메시지

L6

Feedback & Learning

인간의 액션과 사후 결과를 저장

decision logs, label sets, improvement queue

4.2 데이터 진실과 AI 유연성의 결합 방식

이 설계의 핵심은 하드 스파인과 소프트 조사층의 분리입니다. 하드 스파인은 코드와 검증기로만 이루어지며, 시간축과 숫자의 진실을 보존합니다. 소프트 조사층은 AI가 맡으며, 원문 공시의 의미 해석, 뉴스와 펀더멘털의 충돌, 포지셔닝 오염, founder-sensitive 종목의 내러티브 충격 등을 조사합니다. 두 층이 분리되어 있어야 유연성과 신뢰성을 동시에 가져갈 수 있습니다.

5. Public-Market Knowledge Graph

5.1 코어 엔티티 모델

• Issuer: CIK 중심의 회사 엔티티. 이름 이력, 거래소 이력, SIC, 상장 상태를 포함한다.

• Security: ticker, share class, listing lifecycle 등 시장 거래 단위를 표현한다.

• Filing Event: 10-Q, 10-K, 8-K, 13D/G, Form 4, 13F 등 규제 이벤트의 표준 표현체다.

• Snapshot: issuer-quarter, issuer-month, security-day 등 분석 가능한 시점 스냅샷이다.

• Narrative Event: 뉴스 클러스터, 규제 이슈, founder/CEO 논란, 거시 발표 등 비정형 충격을 이벤트화한 객체다.

• Decision Object: signal, alert, memo, human action, invalidation condition, outcome를 포함하는 최종 의사결정 기록이다.

5.2 저장 계층

계층

성격

포함 내용

Bronze

불변 raw

ZIP, JSON, XML, TXT, HTML, 응답 헤더, 다운로드 메타데이터, 파일 해시

Silver

정규화

issuer master, security mapping, filing identity, timestamps, note sections, ownership, positioning, macro, news mention rows

Gold

의미 계층

issuer_quarter_snapshot, factor_panel, event_store, outlier_casebook, daily_signal_snapshot, memo inputs

5.3 point-in-time 필수 필드

모든 핵심 레코드에는 최소 다섯 개의 시간이 필요합니다. event_ts는 사건 자체의 시각, available_ts는 시스템이 해당 정보를 사용할 수 있게 된 시각, effective_start_ts와 effective_end_ts는 효력 구간, revision_ts는 나중에 수정되거나 재처리된 시각을 의미합니다. 이 다섯 축이 없으면 공시, ownership, macro, news를 한 프레임으로 묶을 수 없습니다.

필드

설명

event_ts

회사가 보고했거나 사건이 발생한 시각

available_ts

시스템이 합법적으로 해당 정보를 사용할 수 있게 된 시각

effective_start_ts

해당 레코드가 효력을 갖기 시작한 시점

effective_end_ts

후속 revision 또는 superseding event가 오기 전까지의 종료 시점

revision_ts

정정·재처리·재평가가 입력된 시각

6. 데이터 소스 우선순위

공개 데이터는 모두 동일한 무게를 갖지 않습니다. 제품은 source-of-truth 계층과 overlay 계층을 구분해야 합니다. source-of-truth는 숫자와 시각을 만드는 근간이고, overlay는 설명력과 조사 밀도를 올리는 레이어입니다.

Tier

영역

설계 원칙

A

SEC 규제 원천 데이터

재무제표, 주석, filings, insider, 13F, 13D/G 등 코어 진실 계층. 원본과 정규화 테이블을 모두 보존한다.

B

시장구조·포지셔닝

short volume, FTD 등. core alpha보다 stress indicator와 contamination overlay로 사용한다.

C

거시·레짐

macro release와 revision-aware time series. 신호 자체보다 regime gate와 설명 계층으로 사용한다.

D

뉴스·내러티브

coverage는 넓지만 노이즈가 많다. 예측 엔진보다 outlier explanation과 event clustering에 우선 배치한다.

E

가격·기업행위

provider abstraction을 두고 delisting-aware·corporate-action-aware 레이어로 관리한다.

7. Deterministic Factor Engine

7.1 역할 정의

• 기술주 Top 500 유니버스를 SIC 기반으로 분기별 재구성한다.

• Alphabet, Meta 등 참조군은 분리 보관하되 코어 통계에서 제외할 수 있도록 flag 구조를 둔다.

• owner-sensitive 종목은 overlay bucket으로 분리하고, core model과 residual model을 별도로 운영한다.

• raw return과 excess return을 모두 계산한다.

• gross result와 turnover-adjusted net result를 항상 함께 제시한다.

• 팩터 강도, 잔차, 급변 이벤트를 기준으로 investigation candidate를 산출한다.

7.2 State Change Engine

Deterministic Factor Engine의 중심에는 State Change Engine이 있어야 합니다. 이 레이어는 재무 팩터와 가격 괴리를 단순 정적 점수로 보지 않고, 시간이 흐르면서 어떻게 변하는지를 계산합니다. 핵심 목적은 “이미 반영된 패턴”을 추격하는 것이 아니라, 공개 지표가 말하는 구조 변화가 아직 가격에 충분히 반영되지 않은 초입을 포착하는 것입니다. 따라서 state change score는 valuation의 대체재가 아니라, valuation·quality·ownership·positioning·macro·narrative 신호를 시간축 위에서 묶는 선제 감지 레이어입니다.

구성 요소

정의

설계 목적

Level

현재 갭 또는 상태의 절대값

현재 괴리의 크기를 파악하되 단독으로 과잉해석하지 않음

Velocity

최근 관측 구간의 1차 변화율

개선·악화가 붙는 초기 국면을 조기 포착

Acceleration

변화율의 변화, 즉 2차 변화율

추세가 강화되는지 둔화되는지 구분

Persistence

변화가 몇 개 구간 연속 유지되는가

일시적 스파이크와 구조적 전이를 분리

Contamination

외생 뉴스·오너·포지셔닝 오염도

신호가 왜곡되었는지 경고 레이어 제공

Regime Fit

현재 시장 환경에서의 전달 적합성

같은 신호라도 지금 통하는 환경인지 확인

Alert는 이 상태전이 점수를 그대로 발사하지 않고, 최소 변화폭, 지속성, 교차소스 일치도, 오염도 한계치를 동시에 만족할 때만 발생시켜야 합니다. 즉, 시스템은 작은 흔들림에는 무딜 수 있어야 하고, 중요한 상태 변화에는 빠를 수 있어야 합니다. 이것이 “민감하되 시끄럽지 않은” 제품의 핵심 품질입니다.

7.3 초기 코어 팩터 묶음

팩터

요약 정의

제품 내 역할

Accruals / Earnings Quality

장부상 이익과 현금흐름 괴리

이익의 질과 이후 수익률 약화 가능성 탐지

Gross Profitability

매출총이익 대비 자산 효율

질 좋은 수익성의 상대 우위 측정

Asset Growth

자산 팽창 속도

공격적 확장의 후행 약세 가능성 추적

Capex Intensity

설비투자 강도

인프라·제조·반도체식 사이클 신호 분해

R&D Intensity

연구개발비 강도

tech-only cross-section에서 혁신 지출의 질 평가

Composite Financial Strength

복합 재무건전성 점수

단일 지표가 아닌 변화 묶음의 합성 판단

7.4 승격 기준

연구 성공과 운영 승격은 분리되어야 합니다. 어떤 팩터든 point-in-time 가용성을 충족해야 하며, 다음달·다음분기 raw/excess return 둘 다에서 의미가 있는지 확인해야 합니다. 또한 monotonicity, decay, turnover, 거래비용 차감 후 잔존성, rolling window 안정성, regime split 견고성을 통과해야만 프로덕션 후보가 됩니다.

• Screening: IC, quantile spread, turnover, decay

• Validation: out-of-sample, walk-forward, regime split

• Execution: transaction-cost-adjusted net value

• Governance: hypothesis registry ID가 없는 팩터는 검정도, 승격도 하지 않는다.

8. AI Harness Layer

8.1 역할과 경계

AI Harness Layer는 숫자를 대신 계산하지 않습니다. 대신, 사건의 의미를 구조화하고, 서로 다른 데이터 소스 사이의 모순을 찾고, 잔차의 원인을 탐색하고, 인간이 이해 가능한 문서로 재구성합니다. 특히 state change score가 의미하는 바를 사람말로 번역하고, 왜 지금 알림이 떴는지와 왜 아직 성급한 행동은 위험한지를 함께 설명해야 합니다. 즉, AI는 계산 엔진이 아니라 조사실·반론실·메시지 엔진입니다.

Agent

핵심 역할

금지 또는 제한

Orchestrator

조사 설계, 병렬도·budget·종료 조건 관리

직접 숫자 확정 금지

Filing Intelligence

공시와 주석을 구조화 event로 추출

검증 전 숫자 확정 금지

Verification / QA

원문 수치, accepted timestamp, stitching 검증

설명 서사 생성은 부역할

Factor Interpretation

팩터 결과와 동종업계 상대위치 해석

팩터 계산 금지

Narrative / Context

뉴스·거시·포지셔닝 오염 조사

core truth 대체 금지

Counter-Case

반대 논리와 실패 가능성 강제 생성

단독 의사결정 금지

Decision Memo

alert, brief, CIO memo 작성

근거 없는 권고 금지

8.2 트리거 기반 승격

모든 티커에 대해 deep research를 돌리면 비용과 속도가 무너집니다. 따라서 AI 하네스는 트리거가 걸린 케이스만 깊게 조사합니다. 트리거는 residual shock, filing shock, ownership/positioning shock, narrative shock, unexplained candidate의 다섯 묶음으로 고정합니다.

트리거

예시

Residual Shock

모델상 강한 bullish인데 실제 반응이 비정상적으로 약하거나, 반대로 강한 bearish인데 시장이 버티는 경우

Filing Shock

10-Q, 10-K, 8-K, 13D/G, Form 4, 13F 등 핵심 공시 변화

Ownership / Positioning Shock

insider cluster, 기관 보유 급변, short volume spike, FTD spike

Narrative Shock

founder/CEO 이슈, 규제·소송·보안사고 클러스터, sector-wide macro break

Unexplained Candidate

눈에 띄는 이벤트 없이도 residual이 큰 경우. mispricing 후보 우선군

8.3 메시지 계약

에이전트 간 통신은 자유 서술이 아니라 구조화된 claim 메시지로 제한해야 합니다. 각 claim은 statement, support, counter-evidence, verdict, needs_verification, trace_refs를 가져야 하며, run_id, task_id, issuer_id, ticker, as_of_ts를 포함한 envelope로 감싸야 합니다. 또한 사람에게 전달되는 메시지는 숫자 그대로가 아니라 plain-language translation 필드를 포함해야 합니다. 이 구조가 없으면 trace가 무너지고, 저수준 사용자에게는 메시지가 아닌 데이터 dump가 됩니다.

9. End-to-End 운영 흐름

9.1 기본 플로우

Step

단계

무엇이 일어나는가

1

Ingest

원천 데이터 수집, raw 저장, 파일 해시 및 응답 메타데이터 기록

2

Normalize

issuer/security/event 기준으로 정규화하고 timestamps와 revisions를 고정

3

Compute

유니버스 재구성, 팩터 계산, residual·risk·turnover 산출

4

Detect

이상징후와 investigation candidate 추출

5

Investigate

오케스트레이터가 필요한 agent만 호출해 깊이 조사

6

Resolve

상충 claim을 정리하고 확인/가설/불가를 구분

7

Deliver

alert, tactical brief, CIO memo를 생성

8

Feedback

인간의 액션과 이후 결과를 decision log에 저장

9.2 인간에게 전달되는 출력물

• Alert: 3~5줄 길이의 즉시 인지용 경보. 무엇이 바뀌었는지와 초기 해석만 전달한다.

• Tactical Brief: 반나절 내 판단용 1페이지 요약. bull case, bear case, contamination flags, 제안 액션을 포함한다.

• CIO Memo: 깊은 조사 결과. 숫자의 진실, 타임라인, 핵심 논리, 반론, unexplained portion, invalidation conditions를 모두 담는다.

9.3 메시지 우선 출력 철학

제품의 1차 산출물은 trade instruction이 아니라 message입니다. Alert는 “무엇이 바뀌었는가”를, Tactical Brief는 “왜 중요한가와 무엇이 아직 미확인인가”를, CIO Memo는 “행동 논리와 무효화 조건”을 전달해야 합니다. 모든 메시지는 최소한 숫자의 진실, 상태 변화의 방향, 오염도 경고, 반대 논리, 현재 권장 액션 클래스를 함께 제공해야 합니다. 권장 액션 클래스는 execute보다 watch / accumulate-on-confirmation / hold / avoid / re-check로 먼저 설계하는 것이 맞습니다. 그래야 제품이 과잉 확신형 추천 엔진으로 오해되지 않습니다.

10. 거버넌스와 운영 규율

10.1 Human-in-the-loop

이 제품은 AI 중심이지만, 의사결정 책임은 인간에게 남겨야 합니다. 매수·매도 실행, 신규 팩터 프로덕션 승격, founder-sensitive 분류 변경, source priority 변경, 리스크 룰 완화는 반드시 인간 승인 항목으로 고정합니다. 반면 조사 개시, 메모 생성, watchlist 업데이트, 가설 등록은 시스템이 자율적으로 수행할 수 있습니다.

10.2 Trace와 감사 가능성

• 어떤 이벤트가 트리거였는가

• 어떤 agent들이 호출되었는가

• 각 agent가 무슨 claim을 냈는가

• 어떤 claim이 채택되거나 기각되었는가

• 최종 memo에는 무엇이 반영되었는가

• 인간이 어떤 결정을 내렸는가

• 그 결정 이후 실제 결과가 어땠는가

나중에 ‘왜 그날 이 종목을 bullish로 봤는가’라는 질문에 데이터·claim·memo·action을 통해 역추적할 수 있어야 시스템이 강해집니다.

11. 구현 우선순위와 플랜 모드 기준 경로

이 문서는 구현 코드를 쓰기 위한 직접적인 기반 문서이므로, build order는 제품의 철학을 보존하도록 설계되어야 합니다. 핵심은 ‘연구용 성공’이 아니라 ‘운영용 견고성’입니다. 따라서 초기 단계일수록 AI보다 truth spine을 먼저 고정해야 합니다.

Phase

이름

종료 조건

0

Constitution Lock

이 문서를 SSOT로 고정하고 금지사항·용어·승격 기준을 잠근다.

1

Truth Spine

issuer master, raw/silver/gold 구조, point-in-time timestamps, revision policy를 완성한다.

2

Core State Change & Factor Engine

SIC 유니버스 재구성, 초기 6개 팩터, level/velocity/acceleration panel, turnover/cost-adjusted backtest, residual 계산이 돈다.

3

AI Harness Minimum

Filing, Verification, Memo agent가 붙고, trigger 기반 deep investigation이 가능해진다.

4

Casebook & Cockpit

outlier casebook, alerts, briefs, CIO memo, decision log가 연결된다.

5

Hypothesis Engine

가설 레지스트리, 실험 큐, 프로덕션 승격 프로세스가 자동화된다.

11.1 Cursor용 구현 규율

• 플랜 모드는 항상 이 문서를 읽고 시작하며, 새로운 기능 제안은 어느 레이어를 확장하는지 먼저 명시한다.

• truth spine 미완성 상태에서 agent 기능을 먼저 확장하지 않는다.

• 모든 신규 데이터 소스는 source tier, time semantics, entity mapping, revision policy를 먼저 정의해야 한다.

• 새 팩터는 hypothesis registry 항목, 검정 기준, 폐기 기준 없이 구현하지 않는다.

• 메시지·memo·alert 포맷은 자유롭게 바꾸지 말고 message contract를 통해 버전 관리한다.

• 모든 패치 후 HANDOFF / architecture status / known gaps를 함께 업데이트한다.

12. 비목표와 금지사항

유연성을 위해 범위를 넓히되, 제품 정체성을 흐리는 기능은 초기 단계에서 의도적으로 배제해야 합니다. 아래 항목은 최소한 v1~v2 범위에서는 비목표로 두는 것이 맞습니다.

• AI가 최종 투자 결정을 자동 실행하는 구조

• 고빈도 체결 최적화나 execution algo 중심 제품으로의 조기 확장

• 설명 가능한 trace 없이 생성형 요약만 제공하는 뉴스 앱화

• 거래비용·상장폐지·revision을 무시한 연구용 데모 백테스트

• 가설 레지스트리 없이 즉흥적으로 팩터를 계속 추가하는 방식

• 모든 티커에 항상 deep investigation을 돌리는 과한 agent swarm 구조

13. 최종 요약

이 설계도는 두 개의 문서를 결합한 결과가 아니라, 하나의 일관된 제품 정의로 읽혀야 합니다. Public-Market Knowledge Graph는 제품의 골격입니다. State Change & Deterministic Factor Engine은 그 골격 위에서 공개 지표의 절대 갭과 변화 방향을 계량화합니다. AI Harness Layer는 그 수치를 해석하고 반론을 세우며, Decision Cockpit은 그 결과를 인간이 행동 가능한 메시지로 번역합니다. 즉, 핵심은 반응형 패턴 추격이 아니라 상태전이 기반 선제 경보입니다.

따라서 앞으로의 플랜 모드 로드맵은 이 문서의 순서를 그대로 따라야 합니다. 먼저 진실 저장소와 시간축을 잠그고, 그 위에 state change/factor engine을 올리며, 그 다음에만 AI 조사층을 붙이고, 마지막으로 운영용 cockpit과 hypothesis engine을 확장해야 합니다. 이 순서를 어기면 제품은 화려해 보일 수 있어도 신뢰를 잃습니다.

Appendix A. 플랜 모드에서 반드시 먼저 답해야 할 질문

• 이 기능은 어느 레이어에 속하는가: Truth, Factor, Harness, Cockpit, Feedback 중 어디인가.

• 이 기능은 source-of-truth를 바꾸는가, 아니면 overlay를 추가하는가.

• 이 기능은 상태전이 감지 품질(Level/Velocity/Acceleration/Persistence/Contamination/Regime Fit)을 실제로 강화하는가.

• 이 기능은 새로운 time semantics를 도입하는가.

• 이 기능은 사람의 결정 책임 경계를 흐리지는 않는가.

• 이 기능은 어떤 acceptance criteria를 통과해야 merge 가능한가.

Appendix B. 계획 문서에 항상 포함되어야 할 산출물

• 아키텍처 영향 범위

• 데이터 모델 영향 범위

• agent 영향 범위

• 수용 기준 및 실패 기준

• 추적 가능한 handoff 문구

• 미완료 리스크와 후속 작업
