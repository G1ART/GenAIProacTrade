# GenAIProacTrade MVP 구현 로드맵 v3 — 저장소 요약 (원본: `GenAIProacTrade_MVP_Implementation_Roadmap_KR_v3.docx`)

원본 워드는 IR 덱 기준으로 잠근 **Today / Research / Replay** 제품 형태를 투자자 데모 가능 수준으로 만드는 내부 실행 문서입니다.  
**“엔진을 더 쌓는 계획”이 아니라 “보여줄 수 있는 제품을 최단거리로 완성하는 계획”** 입니다.

## 북극성 (제품 장면)

- **Today**: 시간축별 활성 모델군이 만든 **저평가↔고평가 스펙트럼 보드**
- **Research**: **메시지 → 정보 → 맞춤형 리서치 샌드박스**
- **Replay**: **현실 복기 + 가상 복기**

## MVP 완성 판정 — 7개 장면

| 장면 | 사용자가 느껴야 할 것 | 완성 판정 요지 |
|------|----------------------|----------------|
| Today 보드 | 지금 무엇을 봐야 하는지 한눈에 | 시간축, 스펙트럼, 한 줄 메시지, rationale, 변화 |
| Watchlist 필터 | 내 종목 우선순위 | 워치 기준 재정렬·상태 변화 |
| 종목 상세 | 지금 어떻게 받아들일지 | message → information → deeper rationale |
| Ask AI | 깊게 물어보면 이어짐 | why now / what changed / what to watch 등 |
| Custom Sandbox | 가설 시험 | 입력·horizon·결과 비교가 실제 동작 |
| 현실 복기 | 판단 되돌아보기 | 당시 메시지·행동·이후 결과 연결 |
| 가상 복기 | what-if | 시나리오가 제품 안에서 동작 |

## 6개 워크스트림

- **A** Today Spectrum Engine  
- **B** Message Layer v1  
- **C** Research + Ask AI + Sandbox  
- **D** Replay (현실+가상)  
- **E** UX / 언어 / 셸 (47d/47e 등)  
- **F** Runtime trust / ingest / 데모 데이터  

Today/Research/Replay와 무관하면 MVP 직전에는 뒤로 미룸.

## 실행 순서 (문서 Slide 11)

1. 47d 셸 재배치 + 47e 유저 언어 마감  
2. Message Layer v1 스키마 + Today 카드 계약  
3. Horizon model registry + spectrum scoring + rationale  
4. Detail / Ask AI / Sandbox 최소 동작  
5. Reality + Counterfactual Replay 연결  
6. Phase 53 + frozen snapshot + price overlay로 데모 장면 고정  

## 패치 판정 한 줄

**이 패치가 Today / Research / Replay 중 하나를 투자자 데모 가능한 수준으로 끌어올리는가?** — 아니면 뒤로 미룸.

## 금지 (MVP 직전)

실시간 완전 자동화에 과도 투자, 브로커/주문 확장, 무한 자유 샌드박스, Today를 research-state 대시보드로 후퇴, 규제 모호한 buy/sell 카피, MVP 전 vertical 다발.

---

*본 파일은 `.docx`에서 추출한 내용을 바탕으로 한 요약이며, 세부 표·부록은 원본 워드를 권장합니다.*
