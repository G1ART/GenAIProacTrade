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
| Q1 | Today가 registry만 읽는가? | **조건부 닫힘 (AGH v1 Patch 9 강화)** | 기본 `METIS_TODAY_SOURCE=registry` + `validate-metis-brain-bundle` 통과 번들이면 시드 미사용. Patch 7 의 `rows_limit` + Patch 8 의 3-tier bundle vocabulary 위에, Patch 9 는 (a) **A1 `brain_bundle_path()` 가 env>v2>v0 순서로 자동 감지** 하고 v2 가 quick integrity 를 통과할 때만 v2 를 사용 (그 외는 v0 fallback), (b) `/api/runtime/health.mvp_brain_gate` 에 `brain_bundle_path_resolved` / `brain_bundle_v2_exists` / `brain_bundle_v2_integrity_failed` / `brain_bundle_fallback_to_v0` 4 필드를 추가 + v2 integrity fail 시 `degraded_reasons.append("v2_integrity_failed")` 로 조용히 덮지 않음, (c) UI `hydrateBundleTierChip` 이 **fallback variant** (`tsr-chip--degraded`) 로 "번들: 폴백 (v0)" 를 운영자에게 상시 노출, (d) **A2 production-tier 4 integrity 체크** (active/challenger 일관성 / horizon 별 spectrum rows ≥ 1 / tier metadata coherence / write evidence) 가 `tier="production"` 호출시 활성. 즉 demo fingerprint 를 production 으로 잘못 승격할 수 없음. |
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
| 5 Shell/KO-EN/데모 동결 | — | **Patch 10A Product Shell 분리로 상향 (2026-04-23)** — 사용자용 `/` 와 운영자용 `/ops` 를 **하드 2-파일 분리** (`METIS_OPS_SHELL=1` env 게이트, 미설정 시 /ops 404), 신규 `product_shell.css` design tokens + 8 priority components + SVG hand-roll 스파크라인, `product_shell.*` 46 키 KO/EN parity, HTML/JS/CSS/DTO 4 면 no-leak regex 스캐너로 엔지니어링 ID 누수 차단. 여전히 Patch 9 production actualization 으로 상향된 기반: **Patch 9 production actualization 으로 상향**: Patch 8 의 `demo`→`sample` 로캘 graduation + bundle-tier chip 위에, Patch 9 가 (a) **D1 — bundle-tier chip fallback variant** (`tsr-chip--degraded` + `tsr-tier-chip--fallback`) 로 "번들: 폴백 (v0)" 을 운영자에게 상시 노출 + tooltip 에 `degraded_reasons` 언급, (b) **D2 — primary nav 강조 / utility demote** (feature 제거 0, 폰트·opacity 차등), (c) **B4 — invoke copy 에 "운영자 게이트 · 대기열 · 자동 승격 없음"** 명시 (no-leak 스캐너 `test_agh_v1_patch9_copy_no_leak.py` 가 이 문구들의 실존을 파라미터 테스트로 강제), (d) `screenshots_patch_9/freeze_*.html` + `sha256_manifest.json` 7 개 snapshot. playwright 기반 실 브라우저 스크린샷은 여전히 이월. |
| 6 Trust | — | **부분 닫힘 (AGH v1 Patch 9)** — Patch 7/8 의 bounded contract card + operator gate + cli_hint + 3-tier bundle chip + degraded 200 위에, Patch 9 가 (a) **B1 recent sandbox requests 드로어** (humanize 된 kind·result·blocking·input·lifecycle-aware next step hint) 로 운영자가 액션을 요청한 뒤 "내 요청이 어디까지 갔는지" 를 SPA 안에서 확인 가능, (b) **B2 워커 tick hint** 로 "워커가 주기적으로 큐를 확인합니다" 를 queued/running 에서만 노출 (자동 승격 환상 제거), (c) **A1 A2 — production bundle integrity 4 체크 + v2 integrity fail 시 `degraded_reasons`** 로 프로덕션 번들이 은밀히 demo fingerprint 로 오용되는 리스크 차단. 전용 Trust 패널 / surface-level signature 는 후속. |

---

## 3.5 Product Shell vs Ops Cockpit (Patch 10A, 2026-04-23)

스펙 §5 (Today/Research/Replay) 는 **사용자 표면** 에 대한 계약이다. Patch 10A 이전까지 이 표면은 운영자용 Cockpit UI 와 물리적으로 같은 번들에 묶여 있었고, 그 결과 엔지니어링 ID (`art_*`, `reg_*`, `factor_*`, `horizon_provenance` 등) 가 사용자에게 노출되는 구조적 누수가 상존했다.

Patch 10A 는 이 누수를 **UI 튜닝이 아닌 아키텍처 분리**로 닫는다:

- **하드 2-파일 분리**: `/` → `static/index.html` + `product_shell.js` + `product_shell.css` (사용자용). `/ops` → `static/ops.html` + `static/ops.js` (운영자용, `METIS_OPS_SHELL=1` 환경변수 게이트, 미설정 시 404).
- **/api/product/* 접두어**: 사용자 DTO 는 `src/phase47_runtime/product_shell/view_models.py` 의 mapper 레이어를 지나 `strip_engineering_ids` 재귀 스크러버 → `PRODUCT_TODAY_V1` 계약으로 내보낸다. 기존 `/api/*` 는 Cockpit 전용으로 보존.
- **Today 계약 (스펙 §5.1 강화)**: `trust strip → today-at-a-glance → hero horizon cards ×4 → selected movers → watchlist strip (subdued) → advanced disclosure` 레이아웃, hero 카드에 **grade chip (신호 강도 A+~F) + stance label (방향성) + confidence badge (데이터 품질)** 3축 분리 병치, CTA 주 "근거 보기" 는 **Today 내부 inline evidence drawer** 로 확장 (Research 하드 네비 없음), SVG hand-roll 스파크라인, 샘플 시 honest degraded 문구.
- **언어 계약**: `product_shell.*` 46 키 KO/EN parity + `test_agh_v1_patch_10a_copy_no_leak.py` 가 HTML/JS/CSS/DTO 4 면을 regex 스캔해 엔지니어링 토큰 / 권유 명령형 부재를 강제.
- **Research / Replay / Ask AI**: 10A 에서는 "곧 도착" 제품 톤 스텁 카드만 — 매수/매도 권유 문구 없음, 과장된 예측 확신 없음 (Spec §4.3, §5.1 준수). 10B 에서 정식 재설계.

상세: [`docs/plan/METIS_Product_Shell_Rebuild_v1_Spec_KR.md`](./METIS_Product_Shell_Rebuild_v1_Spec_KR.md), 운영 절차: [`docs/ops/METIS_Product_Shell_vs_Ops_Cockpit_Split_Runbook_v1.md`](../ops/METIS_Product_Shell_vs_Ops_Cockpit_Split_Runbook_v1.md).

---

## 4. 형태/기능적으로 아직 “제품 완성”에 남은 큰 것

1. **실검증 → 번들 스펙트럼 행** 자동 생성(지금은 게이트·pointer 중심; spectrum rows는 시드/데모 번들 의존 가능).  
2. **운영 단일 경로**: `build-metis-brain-bundle-from-factor-validation` 성공률·실패 리포트를 팀이 매일 볼 수 있게 CI/헬스에 고정.  
3. **Replay ↔ outcome**: 결정 ledger·알림과 **동일 message_snapshot_id**로 끝까지 조인 검증(이벤트 빌더 확장).  
4. **스펙 §7**: free-form 승격·registry 우회 방지 — 정책 테스트·리뷰 체크리스트.
5. **S&P 500 스케일 준비 (Patch 9 Scale Readiness Note 요약)**: Patch 8 F1/F3 closure 위에 Patch 9 가 **CF-8·A (packet/queue retention archive + server-side count RPC) + CF-8·B (target_scope JSONB 인덱스 + list_packets filter push-down) + CF-8·C (message snapshot lazy-generation)** 를 **실코드로 닫음**. 500 티커 **operational green (Patch 9)**: (a) `v2` 번들이 `production` tier, (b) `/api/runtime/health.health_status == ok` + `brain_bundle_tier == production`, (c) `brain_bundle_v2_integrity_failed == false`, (d) `panel_truncated_at_limit == false`, (e) `harness-retention-archive` 가 운영 주기로 돌고 있음 — 5 개가 green 이면 운영 시작 가능. 남은 Patch 10 후보: CF-8·D `_horizon_lens_compare` 번들 단위 캐시 (Today fan-out), CF-9·A `harness-retention-archive` 주기화 (Railway cron 또는 worker 사이드채널), CF-9·B production bundle graduation 의 Supabase r-branch 자동화. 상세: `docs/plan/METIS_Scale_Readiness_Note_Patch9_v1.md`.

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
