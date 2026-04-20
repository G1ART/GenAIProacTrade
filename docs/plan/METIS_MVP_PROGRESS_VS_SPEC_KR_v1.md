# METIS MVP — 스펙 대비 진척·갭 (운영 스냅샷 v1)

권위: `METIS_MVP_Unified_Product_Spec_KR_v1.md`, `METIS_MVP_Unified_Build_Plan_KR_v1.md`  
목적: **북극성(Truth → Registry → Message → Today/Research/Replay)** 대비 지금 코드가 어디까지 왔는지, 플랜 §1의 “없는 것” 목록을 **현재 기준으로 재평가**한다.  
(빌드 플랜 §1은 문서 작성 시점 스냅샷이며, 이후 Brain 번들·게이트·Today registry 경로 등이 구현되었다.)

---

## 1. 북극성 한 줄

**Active Horizon Model Registry를 Today가 읽고**, 검증·승격된 아티팩트가 **message snapshot**으로 Research/Replay까지 이어지는 **연구 거버넌스형 의사결정 OS**.

---

## 2. 제품 스펙 §10 공식 판정 — 코드/데이터 기준 요약

| # | 질문 (스펙 원문) | 현재 상태 | 비고 |
|---|------------------|-----------|------|
| Q1 | Today가 registry만 읽는가? | **조건부 닫힘** | 기본 `METIS_TODAY_SOURCE=registry` + `validate-metis-brain-bundle` 통과 번들이면 시드 미사용. `seed`/`auto`+번들 불완 시 시드 폴백. |
| Q2 | 각 시간축에 active family 존재? | **닫힘** | `metis_brain_bundle_v0` + `bundle_ready_for_horizon` |
| Q3 | challenger/active 구분? | **닫힘** | short challenger 등 |
| Q4 | artifact 없이 Today 불가? | **스키마상 닫힘** | 번들 무결성 검사; **실데이터 Heart→Artifact 자동 생산**은 별도(게이트 export/merge 파이프) |
| Q5 | message가 memo와 분리된 1급? | **대부분 닫힘** | `MessageObjectV1`, 스냅샷 스토어, Slice B Ask 연동 |
| Q6 | 카드에 headline·why_now·rationale? | **닫힘** | 시드/번들 스펙트럼 행 + object detail |
| Q7 | 동명 종목·지평별 위치 차이? | **닫힘** | 지평별 행·`horizon_lens_compare` |
| Q8 | price overlay가 rank movement 변경? | **닫힘** | `mock_price_tick=1` |
| Q9 | Research message→information→deeper? | **강화 닫힘(AGH v1 Patch 5)** | Patch 5에서 `layer5_intent_router_v1`(7 kinds 결정론 라우팅) + `ResearchAnswerStructureV1`(summary/residual/what_to_watch/evidence_cited/proposed_sandbox_request) + `validate_research_structured_v1` 가드레일을 통해 "왜 / 무엇이 미증명 / 무엇을 봐야 / 어떤 bounded sandbox 필요?" 4축 acceptance 발음 완료. Today object detail에 `sandbox_options_v1` + `research_status_badges_v1` 노출. |
| Q10 | Replay가 당시 family·결과 연결? | **닫힘(AGH v1 Patch 5)** | 타임라인 lineage + `registry_entry_id` 필드는 종전 스프린트에서 닫힘, Patch 5에서 `api_governance_lineage_for_registry_entry`에 `sandbox_followups` + `total_sandbox_requests/completed/blocked` 확장, `/api/sandbox/requests`·`/api/replay/governance-lineage` 라우트 추가. 즉 operator는 "validation → evaluator → proposal → decision → apply → spectrum refresh → sandbox rerun" 체인을 단일 뷰에서 복원 가능. |

---

## 3. 빌드 플랜 Stage 대비 (문서 Stage 순)

| Stage | 목표 | 진척 |
|-------|------|------|
| 0 Brain Lock | Artifact·Gate·Registry·Today 소스 계약 | **닫힘**(스키마+번들+검증 CLI+DB→게이트 빌드) |
| 1 Today 수직 | Registry 스펙트럼·밴딩·워치·rank | **닫힘**(registry 우선·폴백 시드) |
| 2 Message v1 | 1급 객체·스냅샷 | **거의 닫힘**(저장·해석·Ask 스레드) |
| 3 Research 최소 | 계층·Ask·샌드박스 | **최소 닫힘** |
| 4 Replay | lineage·counterfactual·결정 | **부분**·계속 (registry id on timeline) |
| 5 Shell/KO-EN/데모 동결 | — | **의도적 후순위**(사용자: 데모 스크립트 저우선) |
| 6 Trust | — | **후순위** |

---

## 4. 형태/기능적으로 아직 “제품 완성”에 남은 큰 것

1. **실검증 → 번들 스펙트럼 행** 자동 생성(지금은 게이트·pointer 중심; spectrum rows는 시드/데모 번들 의존 가능).  
2. **운영 단일 경로**: `build-metis-brain-bundle-from-factor-validation` 성공률·실패 리포트를 팀이 매일 볼 수 있게 CI/헬스에 고정.  
3. **Replay ↔ outcome**: 결정 ledger·알림과 **동일 message_snapshot_id**로 끝까지 조인 검증(이벤트 빌더 확장).  
4. **스펙 §7**: free-form 승격·registry 우회 방지 — 정책 테스트·리뷰 체크리스트.

---

## 5. 자동 점검 (런타임)

`GET /api/runtime/health` 응답에 **`mvp_product_spec_survey_v0`** 블록이 포함된다.  
CLI: `PYTHONPATH=src python3 src/main.py print-mvp-spec-survey --repo-root .` (CI: `--fail-on-false`).  
(자동 가능한 Q1–Q5 신호 + 나머지는 수동 증명 목록.)

---

## 6. 다음 스프린트(데모 문서 제외)

**Sprint “Brain surface truth”** (2주 압축 가정):

1. 검증 run → **spectrum row / artifact 메타**까지 번들 빌더 확장(또는 최소 1지평 E2E).  
2. Replay 타임라인 이벤트에 **registry_entry_id·message_snapshot_id** 필수화 및 테스트.  
3. `mvp_product_spec_survey` Q6–Q10을 가능한 범위에서 자동화(예: 샘플 API 스모크).

이 문서는 구현이 바뀔 때마다 버전을 올려 갱신한다.
