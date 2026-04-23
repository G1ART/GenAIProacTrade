# METIS Product Shell vs Ops Cockpit — 분리 운영 Runbook v1

> 대상: 개발자 / 운영자 / 데모 진행자.
> 목적: Patch 10A 이후 "사용자에게 보여주는 화면" 과 "운영자만 보는 화면" 이 **한 바이너리, 두 경로**로 공존하는 구조에서, 헷갈리지 않고 안전하게 구동·검증·롤백하는 절차.

---

## 1. 경로 한 눈에 보기

| 경로 | 무엇이 뜨나 | 조건 |
|---|---|---|
| `/` | 새로운 **Product Shell** (사용자용) | 항상. Patch 10A 이후 기본값. |
| `/ops` | 기존 **Ops Cockpit** (운영자용) | `METIS_OPS_SHELL ∈ {1, true, yes}` 일 때만. 없으면 404. |
| `/api/product/*` | Product Shell 전용 DTO | 항상. Mapper 로 엔지니어링 ID 스크러빙됨. 10A=today 1 route, 10B=+research/replay/ask/ask-quick/requests = **총 6 route**. |
| `/api/*` | 기존 내부 API | 항상. Cockpit 이 사용. |

## 2. 로컬에서 Product Shell 띄우기

```bash
cd /path/to/GenAIProacTrade
PYTHONPATH=src python3 -m phase47_runtime.app
# 기본: http://127.0.0.1:5050/
```

브라우저에서 `http://127.0.0.1:5050/` 로 들어가면 **Product Shell** 이 뜬다. 여기에는 Ops 관련 UI 가 일절 없다.

## 3. 로컬에서 Ops Cockpit 동시에 띄우기

```bash
METIS_OPS_SHELL=1 PYTHONPATH=src python3 -m phase47_runtime.app
# 동일 포트에서 / 와 /ops 둘 다 접근 가능
```

- `http://127.0.0.1:5050/`    → Product Shell
- `http://127.0.0.1:5050/ops` → Ops Cockpit

`METIS_OPS_SHELL` 을 주지 않고 접근하면 `/ops` 는 **404**를 반환한다. 이 4-0-4 는 기능 고장이 아니라 **보안 기본값**이다.

## 4. 데모 시나리오별 권장 실행

### 4.1 고객 데모 (사용자 관점)

```bash
# 의도적으로 METIS_OPS_SHELL 을 unset 으로 둔다.
unset METIS_OPS_SHELL
PYTHONPATH=src python3 -m phase47_runtime.app
```

화면이 곧 Product Shell 하나로 고정된다. 데모 중 실수로 주소창에 `/ops` 를 쳐도 404 로 보호됨.

### 4.2 내부 리뷰 (엔지니어링 관점)

```bash
METIS_OPS_SHELL=1 PYTHONPATH=src python3 -m phase47_runtime.app
```

Product Shell 과 Ops Cockpit 을 탭으로 나란히 열고 수치·근거를 교차 점검한다.

### 4.3 CI / 스크립트 검증

```bash
# 무네트워크 계약 검증 runbook
PYTHONPATH=src python3 scripts/agh_v1_patch_10a_product_shell_runbook.py

# 스냅샷 (HTML/JS/CSS/DTO) 동결
PYTHONPATH=src python3 scripts/agh_v1_patch_10a_product_shell_freeze_snapshots.py
```

두 스크립트 모두 **외부 호출이 없고**, 결과는 `data/mvp/evidence/` 아래에 결정론적으로 떨어진다.

## 5. 배포 체크리스트 (Railway / 유사 PaaS)

1. 앱 프로세스 환경변수:
   - 고객용 단일 shell 원하면 `METIS_OPS_SHELL` **설정하지 않음**.
   - 내부 리뷰/데모 공용 URL 이면 `METIS_OPS_SHELL=1` 설정.
2. 확인 경로:
   - `GET /api/product/today` → `PRODUCT_TODAY_V1` 계약 JSON.
   - `GET /api/product/research?presentation=landing` → `PRODUCT_RESEARCH_LANDING_V1` (Patch 10B).
   - `GET /api/product/research?presentation=deepdive&asset_id=...&horizon_key=short` → `PRODUCT_RESEARCH_DEEPDIVE_V1` (Patch 10B).
   - `GET /api/product/replay?asset_id=...&horizon_key=short` → `PRODUCT_REPLAY_V1` (Patch 10B).
   - `GET /api/product/ask?asset_id=...&horizon_key=short` → `PRODUCT_ASK_V1` (Patch 10B).
   - `GET /api/product/ask/quick?intent=explain_claim&asset_id=...&horizon_key=short` → `PRODUCT_ASK_QUICK_V1` (Patch 10B).
   - `GET /api/product/requests` → `PRODUCT_REQUEST_STATE_V1` (Patch 10B).
   - `GET /api/runtime/health` → 기존 헬스 (Ops 측 계약 유지).
3. `/ops` 접근 로그가 갑자기 늘면 **누가 내부 URL 공유했는지 추적**. 고객용 주소에는 절대 섞이지 않는다.
4. **Patch 10C coherence 검증 (배포 후 스모크)**:
   - 같은 focus (`asset_id=AAPL`, `horizon_key=short`) 로 네 표면 DTO 를 뽑고 `coherence_signature.fingerprint` 가 4 곳 모두 동일한지 확인:
     ```bash
     for p in "/api/product/today" \
              "/api/product/research?presentation=deepdive&asset_id=AAPL&horizon_key=short" \
              "/api/product/replay?asset_id=AAPL&horizon_key=short" \
              "/api/product/ask?asset_id=AAPL&horizon_key=short"; do
       curl -s "http://localhost:$PORT$p" | python3 -c 'import sys,json; d=json.load(sys.stdin); \
         fp=(d.get("coherence_signature") or (d.get("hero_cards") or [{}])[0].get("coherence_signature") or {}).get("fingerprint"); \
         print("'$p'",fp)'
     done
     ```
   - Today 는 `hero_cards[0].coherence_signature.fingerprint` 를, 나머지는 top-level `coherence_signature.fingerprint` 를 비교. 네 값이 모두 같으면 **cross-surface coherence green**.
   - Ask AI trust closure 검증: `POST /api/product/ask` 로 `"Buy AAPL now with a price target"` 같은 advice-style 프롬프트를 보내면 응답 body 가 `banner.kind="out_of_scope"` 로 단락되어야 한다 (LLM 호출 없음 + engineering ID 누수 0).

## 6. 트러블슈팅

| 증상 | 원인 후보 | 해결 |
|---|---|---|
| `/` 에서 500 error + "product_shell rebuild missing" | `static/index.html` 유실 | `git status` 로 파일 존재 확인; 또는 Patch 10A 브랜치 재체크아웃 |
| `/ops` 가 404 | `METIS_OPS_SHELL` 미설정 | 의도한 경우 그대로. 필요시 env 설정 후 재시작 |
| `/api/product/today` 가 500 | view_models 가 번들 로드 실패 | `METIS_BRAIN_BUNDLE` 경로 확인 (Patch 9 Runbook 참조) |
| 화면에 `art_*` / `factor_*` / `template_fallback` 같은 단어가 보임 | Mapper 스크러버 우회 | `src/tests/test_agh_v1_patch_10a_copy_no_leak.py` / `test_agh_v1_patch_10b_copy_no_leak.py` / `test_agh_v1_patch_10c_copy_no_leak.py` 순서로 즉시 실행 후 실패 시 해당 레이어 수정 |
| 네 표면 중 한 곳에서 `coherence_signature.fingerprint` 값이 다름 | `shared_focus_block` 미 embed 또는 rationale_summary 불일치 | `src/tests/test_agh_v1_patch_10c_coherence.py` 실행 후 diff 로 해당 표면 mapper 수정 |
| Ask AI 가 advice/price target 문장을 그대로 돌려줌 | post-LLM `scan_response_for_hallucinations` 가 새 패턴 놓침 | `src/phase47_runtime/product_shell/view_models_ask.py` 의 `scan_response_for_hallucinations` regex 확장 + 골든셋 분기 추가 |

## 7. 롤백 절차

Patch 10A 전 상태로 일시 롤백이 필요할 때:

```bash
git checkout <commit-before-10a> -- \
  src/phase47_runtime/static/index.html \
  src/phase47_runtime/static/ops.html \
  src/phase47_runtime/static/ops.js \
  src/phase47_runtime/app.py \
  src/phase47_runtime/routes.py
```

`ops.html` / `ops.js` 는 원래 `index.html` / `app.js` 였으므로, 롤백 시 파일명을 원복해야 Cockpit 이 다시 루트에 뜬다. 본격 롤백은 가능하면 **태그 전체 되감기**로 하라.

## 8. 연결 문서

- [docs/plan/METIS_Product_Shell_Rebuild_v1_Spec_KR.md](../plan/METIS_Product_Shell_Rebuild_v1_Spec_KR.md)
- [docs/plan/METIS_Product_Shell_Rebuild_v1_Patch_10A_Plan_KR.md](../plan/METIS_Product_Shell_Rebuild_v1_Patch_10A_Plan_KR.md)
- [docs/ops/METIS_Railway_Supabase_Deployment_Runbook_v1.md](./METIS_Railway_Supabase_Deployment_Runbook_v1.md)
- [docs/ops/METIS_Production_Bundle_Graduation_Runbook_v1.md](./METIS_Production_Bundle_Graduation_Runbook_v1.md)
