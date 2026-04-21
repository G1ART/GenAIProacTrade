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
| Q1 | Today가 registry만 읽는가? | **조건부 닫힘 (AGH v1 Patch 8 강화)** | 기본 `METIS_TODAY_SOURCE=registry` + `validate-metis-brain-bundle` 통과 번들이면 시드 미사용. Patch 7 의 `rows_limit` + `total_rows` + `truncated` 위에, Patch 8 은 (a) **3-tier bundle vocabulary** (`demo` / `sample` / `production`) 를 `/api/runtime/health.mvp_brain_gate.brain_bundle_tier` 로 노출해 운영자가 현재 Today 가 읽는 번들 성숙도를 즉시 인식 가능, (b) `data/mvp/metis_brain_bundle_v2.json` graduation script (`scripts/agh_v1_patch_8_production_bundle_graduation.py`) 로 R-branch 실 Supabase 에서 번들 promote → `production` tier 경로 확보. |
| Q2 | 각 시간축에 active family 존재? | **닫힘** | `metis_brain_bundle_v0` + `bundle_ready_for_horizon` |
| Q3 | challenger/active 구분? | **닫힘** | short challenger 등 |
| Q4 | artifact 없이 Today 불가? | **스키마상 닫힘** | 번들 무결성 검사; **실데이터 Heart→Artifact 자동 생산**은 별도(게이트 export/merge 파이프) |
| Q5 | message가 memo와 분리된 1급? | **대부분 닫힘** | `MessageObjectV1`, 스냅샷 스토어, Slice B Ask 연동 |
| Q6 | 카드에 headline·why_now·rationale? | **닫힘** | 시드/번들 스펙트럼 행 + object detail |
| Q7 | 동명 종목·지평별 위치 차이? | **닫힘** | 지평별 행·`horizon_lens_compare` |
| Q8 | price overlay가 rank movement 변경? | **닫힘** | `mock_price_tick=1` |
| Q9 | Research message→information→deeper? | **강화 닫힘 (AGH v1 Patch 8)** | Patch 5–7 의 intent router + `ResearchAnswerStructureV1` + 가드레일 + `locale_coverage` + 3-cluster + bounded contract card 위에, Patch 8 이 (a) **A1 — `ResearchAnswerStructureV1` 에 `what_changed_bullets_ko/en`** 2 스택을 추가해 Research 응답이 "What was asked / Current read / What changed recently / Why it matters" **4-stack** 으로 한 단계 더 분명해짐 (guardrail + `_SYSTEM_PROMPT` 동기화), (b) **A5 — tooltip `sub` 에 what_changed 와 confidence band 를 `SUB_SEP` 으로 합성**, (c) **B2 샌드박스 큐 4-state** (`queued/running/completed/blocked`) + `humanizeProducedRefs` + `B3` per-entry recent sandbox requests + `B4` contract card status_after 로 Ask→Research→Sandbox 경로의 "다음 한 걸음" 이 상태까지 UI 에 투명. |
| Q10 | Replay가 당시 family·결과 연결? | **강화 닫힘 (AGH v1 Patch 8)** | Patch 7 의 3-lane SVG + step count summary + time-delta tooltip 위에, Patch 8 이 (a) **A3 — `/api/replay/governance-lineage` 가 step note 를 포함** (각 step 의 작업·범위·결과 요약), (b) **30 일 이상 lineage 공백 annotation** 을 plot 에 overlay 해 "이 갭은 활동 부재였음" 을 시각적으로 선언. `humanizeActiveArtifactLabel` 은 계속 raw id 차단. |

---

## 3. 빌드 플랜 Stage 대비 (문서 Stage 순)

| Stage | 목표 | 진척 |
|-------|------|------|
| 0 Brain Lock | Artifact·Gate·Registry·Today 소스 계약 | **닫힘**(스키마+번들+검증 CLI+DB→게이트 빌드) |
| 1 Today 수직 | Registry 스펙트럼·밴딩·워치·rank | **닫힘**(registry 우선·폴백 시드) |
| 2 Message v1 | 1급 객체·스냅샷 | **거의 닫힘**(저장·해석·Ask 스레드) |
| 3 Research 최소 | 계층·Ask·샌드박스 | **최소 닫힘** |
| 4 Replay | lineage·counterfactual·결정 | **대부분 닫힘 (AGH v1 Patch 8 강화)** — Patch 7 3-lane SVG + step count summary + time-delta tooltip 위에, Patch 8 이 **step note (각 step 의 작업/범위/결과 요약) + 30 일 이상 lineage gap annotation** 을 추가해 "공백 = 사건 없음" 을 명시적으로 선언. |
| 5 Shell/KO-EN/데모 동결 | — | **Patch 8 production graduation 으로 상향**: (a) **A4+D1 — 로캘 `demo` → `sample` graduation** (`LEGACY_LOCALE_ALIASES` 유예 + no-leak 테스트) 로 UI 에서 "데모/demo" 용어 제거, (b) **D3 — 3-tier vocabulary `demo/sample/production` chip** 이 utility nav 에 상시 노출, (c) `screenshots_patch_8/freeze_*.html` + `sha256_manifest.json` 로 7 개 snapshot 고정 (SPA shell / Today detail KO·EN / Replay lineage / health KO·EN / Research JSON schema). playwright 기반 실 브라우저 스크린샷은 여전히 이월. |
| 6 Trust | — | **부분 닫힘 (AGH v1 Patch 8)** — Patch 7 의 bounded contract card + operator gate + cli_hint/operator_note 단일 출처 위에, Patch 8 이 (a) **B4 contract card `status_after` slot + 4-state chip mirror** 로 "액션 후 상태" 를 계약에 명시, (b) **D3 bundle-tier chip** 으로 현재 읽고 있는 번들 성숙도 (`demo/sample/production`) 를 상시 노출, (c) **E2 `/api/runtime/health` degraded 200 + `degraded_reasons`** 로 부분 실패를 숨기지 않고 surface. 전용 Trust 패널 / surface-level signature 는 후속. |

---

## 4. 형태/기능적으로 아직 “제품 완성”에 남은 큰 것

1. **실검증 → 번들 스펙트럼 행** 자동 생성(지금은 게이트·pointer 중심; spectrum rows는 시드/데모 번들 의존 가능).  
2. **운영 단일 경로**: `build-metis-brain-bundle-from-factor-validation` 성공률·실패 리포트를 팀이 매일 볼 수 있게 CI/헬스에 고정.  
3. **Replay ↔ outcome**: 결정 ledger·알림과 **동일 message_snapshot_id**로 끝까지 조인 검증(이벤트 빌더 확장).  
4. **스펙 §7**: free-form 승격·registry 우회 방지 — 정책 테스트·리뷰 체크리스트.
5. **S&P 500 스케일 준비 (Patch 8 Scale Readiness Note 요약)**: Patch 8 이 Patch 7 이 설치해 둔 low-risk readiness 위에 **F1 (factor validation batch upsert + panel_truncated_at_limit 가시화) + F3 (bundle panel cache + evaluator single reload)** 를 **실코드로 닫음**. 500 티커 **conditional green**: (a) `v2` 번들이 `production` tier, (b) `/api/runtime/health.health_status == ok` + `brain_bundle_tier == production`, (c) `panel_truncated_at_limit == false` 3 개가 green 이면 운영 시작 가능. 남은 Patch 9 후보: CF-8·A packet/queue retention 테이블 + 야간 배치 + 서버측 GROUP BY (F5 이월), CF-8·B `agentic_harness_packets_v1.target_scope` JSONB 인덱스 + `list_packets` 필터 (F6 이월), CF-8·C message snapshot 지연 생성 (F4 이월), CF-8·D `_horizon_lens_compare` 번들 단위 캐시 (F4 이월). 상세: `docs/plan/METIS_Scale_Readiness_Note_Patch8_v1.md`.

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
