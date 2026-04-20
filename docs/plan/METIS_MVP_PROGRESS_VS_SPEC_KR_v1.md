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
| Q1 | Today가 registry만 읽는가? | **조건부 닫힘 (AGH v1 Patch 7 강화)** | 기본 `METIS_TODAY_SOURCE=registry` + `validate-metis-brain-bundle` 통과 번들이면 시드 미사용. `seed`/`auto`+번들 불완 시 시드 폴백. Patch 7 에서 `/api/today/spectrum` 에 **`rows_limit` (default 200, cap 1000) + `total_rows` + `truncated`** 가 추가되어 500 ticker 확장 시 UI 페이로드가 무제한 커지는 것을 막음. rows 슬라이스는 rank/quintile/movement 계산 **이후** 에 적용되어 top-N 이 rank 에 거짓말하지 않음. |
| Q2 | 각 시간축에 active family 존재? | **닫힘** | `metis_brain_bundle_v0` + `bundle_ready_for_horizon` |
| Q3 | challenger/active 구분? | **닫힘** | short challenger 등 |
| Q4 | artifact 없이 Today 불가? | **스키마상 닫힘** | 번들 무결성 검사; **실데이터 Heart→Artifact 자동 생산**은 별도(게이트 export/merge 파이프) |
| Q5 | message가 memo와 분리된 1급? | **대부분 닫힘** | `MessageObjectV1`, 스냅샷 스토어, Slice B Ask 연동 |
| Q6 | 카드에 headline·why_now·rationale? | **닫힘** | 시드/번들 스펙트럼 행 + object detail |
| Q7 | 동명 종목·지평별 위치 차이? | **닫힘** | 지평별 행·`horizon_lens_compare` |
| Q8 | price overlay가 rank movement 변경? | **닫힘** | `mock_price_tick=1` |
| Q9 | Research message→information→deeper? | **강화 닫힘 (AGH v1 Patch 7)** | Patch 5 의 intent router + `ResearchAnswerStructureV1` + 가드레일 + Patch 6 의 `locale_coverage` 삼중 가드 + Research 5-section 렌더러 위에, Patch 7 이 (a) **3-cluster 재그룹** (current_read / open_questions / bounded_next) 으로 같은 5 섹션을 더 적은 덩어리로 읽히게, (b) evidence 칩을 packet kind 별로 그룹핑 + humanize, (c) `locale_coverage='degraded'` 카피를 "부분 응답 / Partial response" 제품 톤으로, (d) **bounded action contract card** (will_do / will_not_do / after_enqueue 3 줄) 을 invoke 버튼 **바로 위** 에 렌더해 액션의 경계를 액션 지점에서 명시, (e) invoke UI 의 모든 문자열을 `tr()` 로 이관 + 서버 `cli_hint`/`operator_note` 단일 출처 + 큐 상태 one-time polling (background polling 없음) 으로 operator gate 정신 준수. 즉 "왜 / 무엇이 미증명 / 무엇을 봐야 / 어떤 bounded sandbox 필요?" 4축 acceptance 가 **시각적으로도** 3 덩어리로 스캔 가능하며, bounded action 의 경계가 UI 표면에서 투명. |
| Q10 | Replay가 당시 family·결과 연결? | **강화 닫힘 (AGH v1 Patch 7)** | Patch 6 의 Replay compact + SVG timeline plot + tooltip primitive 위에, Patch 7 이 (a) **SVG timeline 을 3-lane 구조** (governed apply / spectrum refresh / sandbox followup) 로 재작성해 "what happened when" 이 한눈에 스캔 가능, (b) lineage step indicator 위에 **step count summary** ("4단계 중 N단계 완료 / N of 4 steps complete") 배너, (c) 각 step 의 `created_at_utc` 를 추출해 **time-delta tooltip** (`이전 대비 +3h` / `+3h after previous`) 를 step 간 차이로 surface, (d) **tooltip sub-line multi-part split** (SUB_SEP=" · ") 로 rail chip / lineage steps / plot events 의 hover 가 "outcome · delta · from→to" 를 다차원 요약으로 드러냄. `/api/replay/governance-lineage` 는 `?limit` (default 200, cap 500) 으로 스케일 safe. `humanizeActiveArtifactLabel` 은 계속 raw id 차단. |

---

## 3. 빌드 플랜 Stage 대비 (문서 Stage 순)

| Stage | 목표 | 진척 |
|-------|------|------|
| 0 Brain Lock | Artifact·Gate·Registry·Today 소스 계약 | **닫힘**(스키마+번들+검증 CLI+DB→게이트 빌드) |
| 1 Today 수직 | Registry 스펙트럼·밴딩·워치·rank | **닫힘**(registry 우선·폴백 시드) |
| 2 Message v1 | 1급 객체·스냅샷 | **거의 닫힘**(저장·해석·Ask 스레드) |
| 3 Research 최소 | 계층·Ask·샌드박스 | **최소 닫힘** |
| 4 Replay | lineage·counterfactual·결정 | **대부분 닫힘 (AGH v1 Patch 7 강화)** — Patch 6 UI compact + SVG timeline plot + Patch 7 **3-lane SVG** (apply / spectrum refresh / sandbox followup) + **step count summary** + **step 간 time-delta tooltip** + multi-part tooltip sub-line |
| 5 Shell/KO-EN/데모 동결 | — | **Patch 6 초기 동결 (4-block Today + Research 5-section + Replay compact + KO/EN `tsr.*` + HTML snapshot sha256 manifest) → Patch 7 product hardening 으로 상향**: A1 IA 2-tier nav (primary/utility), A2 Today 타이포 토큰 + recent-activity + consolidated audit, A3 Research 3-cluster + 제품 톤 카피, A4 Replay 3-lane, A5 tooltip sub-line, B2 bounded action contract card. playwright 기반 실 브라우저 스크린샷은 여전히 이월 (`screenshots_patch_7/` 는 정적 HTML + sha256 manifest). |
| 6 Trust | — | **부분 닫힘 (AGH v1 Patch 7)** — Patch 6 의 no-leak 스캐너 + locale honesty + operator-gated UI invoke 위에 Patch 7 의 (a) **bounded action contract card** (will_do / will_not_do / after_enqueue) 로 액션 경계를 액션 지점에서 명시, (b) `cli_hint`/`operator_note` 서버 단일 출처, (c) invoke 후 one-time 큐 상태 polling 으로 fake autonomy language 없이 진행 상태 노출. 전용 Trust 패널 / surface-level signature / cockpit health surface 제품 톤 재작성은 후속. |

---

## 4. 형태/기능적으로 아직 “제품 완성”에 남은 큰 것

1. **실검증 → 번들 스펙트럼 행** 자동 생성(지금은 게이트·pointer 중심; spectrum rows는 시드/데모 번들 의존 가능).  
2. **운영 단일 경로**: `build-metis-brain-bundle-from-factor-validation` 성공률·실패 리포트를 팀이 매일 볼 수 있게 CI/헬스에 고정.  
3. **Replay ↔ outcome**: 결정 ledger·알림과 **동일 message_snapshot_id**로 끝까지 조인 검증(이벤트 빌더 확장).  
4. **스펙 §7**: free-form 승격·registry 우회 방지 — 정책 테스트·리뷰 체크리스트.
5. **S&P 500 스케일 준비 (Patch 7 Scale Readiness Note 요약)**: Patch 7 은 C2a (governance_scan N+1 hoist) + C2b (Today rows_limit) + C2c (Replay lineage limit cap) + C2d (perf instrumentation) 로 **low-risk readiness** 를 먼저 설치했지만, S&P 500 rollout 은 아래 4 finding 이 남아 있어 **아직 Patch 7 만으로 선언할 수 없음**: (F1) factor validation cadence row-by-row Supabase insert → batch RPC 필요 (CF-7·1), (F3) bundle panel-fetch 중복 → 빌드 로컬 캐시 (CF-7·2), (F5) `packet_store` retention / queue counter scan → archive + counter cache (CF-7·4), (F6) research structured linear scan → `(asset, horizon, kind, created_at)` 인덱스 (CF-7·3). 상세: `docs/plan/METIS_Scale_Readiness_Note_Patch7_v1.md`.

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
