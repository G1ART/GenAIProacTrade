# HANDOFF — Phase 14 (Research Engine Kernel)

## 현재 제품 위치

- **Phase 11–13**: 동결·닫힘 상태 이전과 동일(트랜스크립트 seam, 공개 코어 사이클, 품질 게이트·잔차 트리이지).
- **Phase 14 (닫힘)**: **첫 연구 엔진 커널** — `research_programs` / `research_hypotheses` / `research_reviews` / `research_referee_decisions` / `research_residual_links`. Phase 13 품질·잔차 큐를 **입력**으로 쓰되, **결정적 스코어링·워치리스트 랭킹과 분리**.

## Phase 14로 가능해진 것

1. **단일 잠금 연구 질문**으로 프로그램을 DB에 고정하고, 시드 가설 3건(유동성·공시 복잡도·게이팅/미싱니스)을 생성.
2. **결정적 리뷰 렌즈** 4종(mechanism, pit_data, residual, compression)을 라운드당 1회씩 기록(최대 **2라운드**).
3. **심판**이 `kill` / `sandbox` / `candidate_recipe` 중 하나로 강제 — `thin_input` 단독 기판에서는 **`candidate_recipe` 금지**.
4. **잔차 링크**로 가설과 Phase 13 `unresolved_residual_items`·버킷을 연결.
5. **`export-research-dossier`**로 질문·가설·리뷰·심판·이견·미해결을 한 JSON에 묶음.

## 의도적으로 아직 없는 것

- 다지평·다자산·UI, 라이브 프리미엄 필수 입력, 자동 프로덕트 승격, LLM 필수 리뷰.
- `candidate_recipe`는 **연구 단계 라벨**일 뿐 스코어 경로에 쓰이지 않음(`state_change.runner`는 `research_engine` 미참조).

## 마이그레이션 (누적)

- **Phase 14**: `20250417100000_phase14_research_engine_kernel.sql`

## 다음 단계 권장 (코드 현실 기준)

- **Phase 15 프리미엄 ROI**: Phase 13·14가 이미 가리키는 단일 seam(예: estimates 또는 price-quality)만 PoC — 스파인 병합 금지.
- **Phase 15 공개 데이터 연구 확장**: 품질 `strong`/`usable_with_gaps` 비율을 올리는 백필·패널 깊이 후 동일 커널로 가설·검증 반복.

**권장**: DB가 `thin_input` 위주면 연구 심판이 샌드박스에 머물기 쉬우므로, 사업 우선순위가 “아이디어 검증”이면 **공개 데이터 두께**를, “잔차 설명에 유료 맥락”이면 **단일 프리미엄 seam**을 먼저 고르는 것이 맞다.

---

## Phase 13 이전 요약

- `docs/phase13_evidence.md`, Phase 12·11 문서 참고.
