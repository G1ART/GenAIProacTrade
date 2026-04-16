# Metis 통합 헌법 · 실행 로드맵 v1

**상태**: 초안 (Metis Constitution Patch + Code Audit + `MVP_ROADMAP_SYNTHESIS_KR_v3` + `PLAN_MODE_ROADMAP_CURSOR_CONTINUOUS_BUILD` 정렬본)  
**날짜**: 2026-04-15  
**목적**: “뇌(Active Horizon Model Family + 승격 게이트)”를 MVP 핵심으로 올리되, 기존 북극성(Today / Research / Replay)과 패치 판정 문장을 **한 문서에서 모순 없이** 고정한다.

---

## 1. 제품 한 문장 (북극성 — 변경 없음)

**공개 데이터 우선 · 시점(PIT) 준수 · 연구 거버넌스가 얹힌 투자 운영 OS**  
표면은 **Today → Research → Replay**, 사용자 흐름은 **Data → Information → Message → Decision → Replay**.

---

## 2. 신체 은유와 책임 (Metis Constitution + 기존 문서 합치)

| 층 | 의미 | 포함 범위 (코드/문서와의 대응) |
|----|------|--------------------------------|
| **뼈·근육 (Bones)** | 결정적 진실층 | factor / market join / state_change / 검증 패널 / PIT (Audit §1.1–1.2) |
| **심장 (Heart)** | 경계 내 모델 탐색 | AI Horizon Model Lab — 후보 아티팩트 생산, **제품 직결 금지** (Constitution §3.2, §9.3) |
| **뇌 (Brain)** | 승격된 가시 신호 | Active Horizon Model Registry + 지평별 **active / challenger** (Audit 결론 C, Constitution §4) |
| **피부 (Skin)** | 메시지 우선 UX | 47d/47e 셸, Today 보드 UI, Ask AI(거버넌스), 샌드박스 UI |

**핵심 정렬 문장 (기존 PLAN_MODE 1.3과의 합의)**  
- 사용자에게 보이는 **히어로는 Message-first Today 표면**이다.  
- “연구 엔진이 히어로가 아니다”는 **내비게이션에서 연구 대시보드를 중심에 두지 말라**는 뜻이지, **심장(후보 생산)을 비MVP로 내리자는 뜻이 아니다**.  
- 심장은 **백스테이지**에서 아티팩트를 만들고, 뇌(레지스트리)만이 Today 랭킹/밴딩 입력이 된다.

---

## 3. Today가 읽을 수 있는 유일한 소스 (Constitution §3.1 — 제품 헌법)

Today 스펙트럼·밴딩·(확장 시) 랭킹은 **오직** 다음에서만 유도한다:

- `active_model_family_registry` (지평별 `active` / 선택적 `challenger` / 버전·유효기간)

**금지 (명시)** — Constitution + Audit §2.1 정리:

- 원시 factor panel 직접
- 원시 `state_change` 점수 단독
- 원시 `candidate_recipe` / 가설 레지스트리 직접
- 검증·레지스트리 테이블을 **승격 없이** 프로덕션 스코어에 직접 연결 (Audit §3.6과 동일)

**현재 구현과의 차이 (정직한 갭)**  
- Phase 47 런타임 Today 데모는 **시드 JSON** 기반이다 → **헌법상 “임시 스텁”**이며, 레지스트리 연동 시 **동일 UI 계약**으로 갈아끼운다.

---

## 4. Model Artifact Packet (Constitution §5 — 스키마 최소 고정)

후보·챌린저·액티브로 올리려면 **고정 스키마 패킷**이 있어야 한다. 필드 전부는 Constitution §5 목록을 권위로 하되, MVP 증명 최소 단위는 다음을 만족하면 된다:

- `artifact_id`, `artifact_version`, `horizon_key`, `universe_scope`
- `feature_families` / `score_formula_serialized`(또는 동등한 결정적 표현)
- `banding_rule`, `pit_join_policy`, `allowed_data_sources`, `forbidden_data_sources`
- `validation_summary`, `status`, `promotion_lineage`

패킷으로 표현되지 않으면 **승격 불가** (Constitution §5 마지막 문장).

---

## 5. 승격·게이트 (Heart → Brain 다리)

- **Lab 출력** → 검증·기준선 대조 (기존 recipe validation / state_change baseline 경로 **재사용**, Audit §3.4–3.5)  
- **승격 이벤트**는 별도 기록(감사 가능). 자동 승격 금지 (Audit §3.6, Constitution §3.2).  
- **Today**는 승격된 레지스트리만 읽음.

---

## 6. 실행 로드맵 — 스프린트 재배열 (PLAN_MODE 스프린트 번호 보존 + “뇌” 삽입)

기존 Sprint 1–8 번호는 유지하되, **병렬이 아니라 선행 관계**를 아래처럼 고정한다.

| 단계 | 내용 | 비고 |
|------|------|------|
| **0-Brain** | Model Artifact 스키마 v0 + in-repo 저장 + 읽기 API 스텁 | Constitution §5, Audit 권고 1 |
| **0-Registry** | Active registry v0 (지평당 1 active + 0~1 challenger) + promotion 이벤트 로그 | Constitution §8.3–8.4 |
| Sprint 1 | Today Spectrum **Engine** — 입력을 **레지스트리**로 전환(시드는 폴백만) | 기존 Sprint 1과 문구 합치 |
| Sprint 2 | Message Layer v1 (레지스트리·아티팩트 메타를 메시지 계약에 매핑) | |
| Sprint 3 | Today 페이지 제품화 | “피부” — 뇌 없이 피부만 확장 금지 (Constitution §7 금지 항) |
| Sprint 4–8 | Detail / Ask AI / Sandbox / Replay … (기존 PLAN_MODE 순서) | Replay는 **active family lineage** 필드 확보가 완료 판정에 포함 |

**MVP v3 “실행 순서 Slide 11”과의 맞춤**  
- 원문 3번 `Horizon model registry + spectrum scoring` = 본 문서 **0-Brain + 0-Registry + Sprint 1**에 해당.  
- 기존에 UI·샌드박스가 앞서 나간 경우 **회귀가 아니라 “입력 소스 교체”**로 처리한다.

---

## 7. 패치 판정 (단일 문장 — 기존 두 문서 병합)

**이 패치가 (1) Active registry / Artifact / 승격 게이트, 또는 (2) Today·Research·Replay 계약을 레지스트리 정렬로 끌어올리는가?**  
→ 둘 다 아니면 **피부·인프라만**이면 우선순위 낮음 (단, 보안·PIT 위반 수정은 예외).

(구 PLAN_MODE 문장 “Today/Research/Replay 데모”는 **(2)**의 하위 집합으로 유지.)

---

## 8. 해소한 “모순” 요약 (읽기 가이드)

| 겉으로 보이는 충돌 | 통합 해석 |
|--------------------|-----------|
| PLAN_MODE “연구 엔진은 히어로 아님” vs Constitution “심장” | 히어로 = **사용자 표면 메시지**; 심장 = **비가시 파이프라인**. 연구 **대시보드**를 홈에 두지 말 것. |
| MVP v3 “엔진 더 쌓기 아님” vs 모델 고도화 | “엔진”을 **인프라 과다**로 읽지 말고, **승격 가능한 뇌**는 MVP 본체로 읽는다. |
| Audit “결정적 커널” vs Constitution “창의적 AI” | 탐색은 경계 내 자율, **프로덕션 스코어는 패킷+검증만**. |

---

## 9. 기술·구조 갭 (다음 설계에서 반드시 닫을 것)

1. **브리지 부재** (Audit §3.6): 검증/레지스트리 ↔ Today 사이 **명시적 승격 파이프** 코드 없음.  
2. **Phase 14 단일 분기**: `next_quarter` 고정은 **실험 한 갈래**로만 유지, 아키텍처는 지평 확장 가능하게 (Audit §3.1, Constitution §10 B).  
3. **47 런타임 Today**: 시드 기반 → 레지스트리 기반으로 **스왑 계획** 없으면 헌법 §3.1 위반 상태가 지속됨.  
4. **Replay lineage**: “어떤 active family가 말했는가” 필드가 MVP 완료 기준에 포함 (Constitution §11.6, §8.5).  
5. **Ask AI / Sandbox**: 현재는 번들·시드 거버넌스; 추후 **아티팩트 설명/반증** 모드로 연결할지 별도 계약.

---

## 10. 문서 계층 (이 파일 이후)

- **본 파일** (`METIS_UNIFIED_CONSTITUTION_AND_ROADMAP_v1.md`): 헌법 + 스프린트 선후관계 + 패치 판정.  
- **`PLAN_MODE_ROADMAP_CURSOR_CONTINUOUS_BUILD.md`**: 스프린트별 수용 기준·안티골 상세 — 본 파일 §6과 충돌 시 **본 파일 우선**.  
- **`MVP_ROADMAP_SYNTHESIS_KR_v3.md`**: IR 7장면·워드스트림 요약 — 본 파일과 충돌 시 **본 파일 우선**.  
- **Metis 원본** (Downloads): 감사 사실·패치 동기 — **아키텍처 권위는 본 파일 + Constitution 필드 정의**.

---

## 11. 다음 액션 (한 줄)

**Model Artifact v0 + Active Registry v0 + Today 입력을 시드에서 레지스트리로 바꾸는 최소 수직 슬라이스**를 우선 머지한다.

---

*끝.*
