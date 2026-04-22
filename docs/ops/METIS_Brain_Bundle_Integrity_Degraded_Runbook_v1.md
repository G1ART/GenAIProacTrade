# METIS Brain Bundle Integrity · Degraded Runbook (v1)

**작성 근거**: AGH v1 Patch 9 §A1 (`brain_bundle_path()` env>v2>v0 auto-detect + quick integrity gate + health exposure). `v2` production bundle 이 존재하지만 **구조적으로 깨졌을 때** 운영자가 어떻게 감지하고 대응하는가.

**스펙 권위**: `docs/plan/METIS_MVP_Unified_Product_Spec_KR_v1.md` §10 Q1 (Today registry-only), `docs/plan/METIS_MVP_Unified_Build_Plan_KR_v1.md` §12 ("Skin closes on Brain").

**비-scope**:
- v2 를 처음 빌드/승격하는 방법 → `docs/ops/METIS_Production_Bundle_Graduation_Runbook_v1.md`.
- Railway / Supabase 배포 인프라 → `docs/ops/METIS_Railway_Supabase_Deployment_Runbook_v1.md`.

---

## 1. 이 런북이 주는 것

- `/api/runtime/health.degraded_reasons` 에 `v2_integrity_failed` 가 뜨는 순간 **10 분 안에** 판단 + 복구 하는 표준 절차.
- UI bundle-tier chip 이 "폴백 (v0)" variant 로 바뀌었을 때 운영자가 해석해야 할 signal.
- v2 의 어떤 필드가 깨졌는지 **원인 세분화** (A/B/C/D 4 가지 케이스).
- 각 케이스별 **복구 SQL / 터미널 명령**.

## 2. 3-tier vocabulary 복습 (Patch 8 → 9)

| tier | 경로 | UI chip | 의미 |
|------|------|---------|------|
| `production` | `data/mvp/metis_brain_bundle_v2.json` | 기본 tone | Supabase live build 의 R-branch 승격 완료, integrity 4 체크 pass |
| `sample` | `data/mvp/metis_brain_bundle_v0.json` | 기본 tone | 시드 스펙트럼 + demo fingerprint. 개발/데모용 |
| `fallback` (신규 Patch 9) | `data/mvp/metis_brain_bundle_v0.json` (강제) | **`tsr-chip--degraded` + `tsr-tier-chip--fallback`** ("번들: 폴백 (v0)") | v2 가 존재하지만 quick integrity 실패 → 런타임이 조용히 v0 로 fallback + `degraded_reasons` 방출 |

본 런북은 **세 번째 행** ("fallback") 이 발생한 순간부터의 절차다.

## 3. 감지 신호 3 개

Patch 9 에서는 아래 3 개 신호가 **동시에** 뜬다. 하나만 보고 판단하지 말 것 (false positive 방지).

1. **`GET /api/runtime/health`** 응답에서:
   - `"health_status": "degraded"` (또는 "ok" 이지만 `degraded_reasons` 존재).
   - `"degraded_reasons": [..., "v2_integrity_failed", ...]`.
   - `"mvp_brain_gate": { "brain_bundle_v2_exists": true, "brain_bundle_v2_integrity_failed": true, "brain_bundle_fallback_to_v0": true }`.
2. **UI bundle-tier chip**:
   - 텍스트가 "번들: 폴백 (v0)" / "Bundle: fallback (v0)" 로 변경.
   - 클래스에 `tsr-chip--degraded` 가 추가되어 살짝 경고 톤.
   - tooltip 이 "`v2` 번들이 있지만 integrity 검사를 통과하지 못했습니다. `/api/runtime/health.degraded_reasons` 를 확인하세요" 류의 문구.
3. **Supabase SQL** (아래 §5·3) 에서 최근 승격 이력과 disk 상태가 불일치.

세 신호가 함께 뜨면 **운영 Today 는 여전히 v0 로 응답중이고 기능은 유지** 되지만, v2 promotion 이 되돌려진 상태이므로 조용히 두면 안 된다.

## 4. Pre-triage (2 분)

`터미널` — 1) 현재 파일 존재 확인:

```bash
cd /Users/hyunminkim/GenAIProacTrade && ls -la data/mvp/metis_brain_bundle_v2.json data/mvp/metis_brain_bundle_v0.json
```

`터미널` — 2) 환경 변수 override 확인 (override 가 잘못된 경로를 가리키는지):

```bash
printenv METIS_BRAIN_BUNDLE
```

`터미널` — 3) health report 직접 조회:

```bash
curl -sS http://127.0.0.1:8765/api/runtime/health | python3 -m json.tool | grep -A 20 mvp_brain_gate
```

`터미널` — 4) integrity 의 세분화된 원인 보기:

```bash
cd /Users/hyunminkim/GenAIProacTrade && PYTHONPATH=src python3 -c "from pathlib import Path; from metis_brain.bundle import brain_bundle_integrity_report_for_path; import json; print(json.dumps(brain_bundle_integrity_report_for_path(Path('.')), indent=2, ensure_ascii=False))"
```

이 출력의 `resolved_path`, `override_used`, `v2_exists`, `v2_quick_integrity_ok`, `v2_integrity_failed`, `fallback_to_v0` 를 메모.

## 5. 원인 세분화 (4 케이스)

### 케이스 A — `METIS_BRAIN_BUNDLE` env override 가 잘못된 경로

증상: `override_used: true` + 해당 파일이 quick integrity fail.

원인: 개발자가 `.env` 에 테스트용 경로를 남겼거나, deploy env 에 stale 값.

조치 (`터미널`):

```bash
cd /Users/hyunminkim/GenAIProacTrade && unset METIS_BRAIN_BUNDLE && python3 -c "from pathlib import Path; from metis_brain.bundle import brain_bundle_integrity_report_for_path; import json; print(json.dumps(brain_bundle_integrity_report_for_path(Path('.')), indent=2, ensure_ascii=False))"
```

Railway 에서는 **Variables** 탭에서 해당 키 제거 후 redeploy.

### 케이스 B — v2 파일이 truncate / partial write

증상: `v2_exists: true` + `v2_quick_integrity_ok: false`. 파일 크기가 비정상적으로 작거나 JSON parse 실패.

원인: graduation script 가 atomic write 를 중단당함 (Ctrl-C, disk full 등).

조치 — **즉시 rollback**:

```bash
cd /Users/hyunminkim/GenAIProacTrade && git status data/mvp/metis_brain_bundle_v2.json
# 만약 git 에 이전 유효 버전이 있다면:
git checkout HEAD -- data/mvp/metis_brain_bundle_v2.json
```

또는 Supabase 에서 재승격 (Graduation Runbook §4 참조).

### 케이스 C — v2 파일이 JSON 은 유효하지만 필수 root key 누락

증상: `v2_exists: true` + `v2_quick_integrity_ok: false` + 파일 크기 정상.

원인: 부분적으로 수정된 번들 (예: 수동 편집 중 artifact_registry key 삭제).

조치:

1. 어떤 root key 가 빠졌는지 확인 (`터미널`):

```bash
cd /Users/hyunminkim/GenAIProacTrade && python3 -c "import json; d=json.load(open('data/mvp/metis_brain_bundle_v2.json')); print(sorted(d.keys()) if isinstance(d, dict) else type(d))"
```

필수 root key 4 개 (Patch 9 `_quick_integrity_ok` 기준): `schema_version`, `artifact_registry`, `promotion_gates`, `active_horizon_model_registry`. 빠졌다면 이전 버전으로 rollback (§케이스 B).

### 케이스 D — production tier integrity 가 실패 (quick integrity 는 통과)

증상: `v2_quick_integrity_ok: true` 인데, graduation script 재실행 시 `validate_active_registry_integrity(..., tier="production")` 가 4 체크 중 하나에서 실패.

원인: Patch 9 A2 의 4 체크 (active/challenger 일관성, horizon 별 spectrum rows, tier metadata coherence, write evidence) 중 하나에 위배. 예: `graduation_tier` 가 `pit:demo:*` 로 시작.

조치 (`터미널`):

```bash
cd /Users/hyunminkim/GenAIProacTrade && PYTHONPATH=src python3 -c "
import json
from pathlib import Path
from metis_brain.bundle import BrainBundleV0, validate_active_registry_integrity
raw = json.load(open('data/mvp/metis_brain_bundle_v2.json'))
bundle = BrainBundleV0.model_validate(raw)
errs = validate_active_registry_integrity(bundle, tier='production')
print(json.dumps(errs, indent=2, ensure_ascii=False))
"
```

출력된 errors 를 보고 (metadata coherence → Supabase 에서 재빌드, write evidence → `as_of_utc` 누락 확인, spectrum rows → horizon cover 재생성, active/challenger → `active_family_id != challenger_family_id` 점검).

## 6. 임시 rollback 3 경로

1. **v0 강제** — 운영을 즉시 안전 상태로:

```bash
export METIS_BRAIN_BUNDLE=/abs/path/to/GenAIProacTrade/data/mvp/metis_brain_bundle_v0.json
```

(Railway: Variables 탭). 이 경우 UI chip 은 여전히 "폴백" 이지만 production tier 호출이 사라지면서 `v2_integrity_failed` degraded reason 은 제거될 수 있다.

2. **v2 삭제** — v2 파일을 일시 제거해 자동으로 v0 로:

```bash
cd /Users/hyunminkim/GenAIProacTrade && mv data/mvp/metis_brain_bundle_v2.json data/mvp/metis_brain_bundle_v2.json.corrupted
```

Patch 9 `brain_bundle_path()` 는 v2 없음 → v0 선택. `degraded_reasons` 에 `v2_integrity_failed` 도 제거된다 (v2 존재 자체가 사라지므로).

3. **git rollback** — 마지막 유효 버전으로:

```bash
cd /Users/hyunminkim/GenAIProacTrade && git log --oneline -- data/mvp/metis_brain_bundle_v2.json
git checkout <last-good-sha> -- data/mvp/metis_brain_bundle_v2.json
```

## 7. 재승격 후 검증

v2 를 다시 유효하게 복구했다면:

`터미널`:

```bash
cd /Users/hyunminkim/GenAIProacTrade && PYTHONPATH=src python3 src/main.py validate-metis-brain-bundle --repo-root .
```

그리고:

```bash
curl -sS http://127.0.0.1:8765/api/runtime/health | python3 -c "import sys, json; d=json.load(sys.stdin); print('status=', d.get('health_status'), 'tier=', d.get('mvp_brain_gate',{}).get('brain_bundle_tier'), 'reasons=', d.get('degraded_reasons'))"
```

기대:
- `status=ok`
- `tier=production`
- `reasons=[]` (또는 `v2_integrity_failed` 가 포함되지 않음).

UI chip 이 기본 tone "production" 으로 복귀.

## 8. 자주 묻는 질문 (FAQ)

**Q. fallback 상태에서 Today 가 멈추나요?**
A. 아니요. Patch 9 A1 의 의도는 "조용히 덮지 않되 서비스는 유지" 입니다. `brain_bundle_path()` 가 v0 로 fallback 하므로 사용자는 응답을 받고, 운영자만 chip/degraded_reasons 로 상태를 인지합니다.

**Q. `v2_integrity_failed` 가 떴는데 v0 도 동시에 fail 하면?**
A. 그 경우 `mvp_brain_gate.brain_bundle_ok == false` + `degraded_reasons` 에 추가 이유. v0 는 항상 git 으로 관리되는 시드이므로 실제로는 git 상태 자체가 오염된 것. `git checkout HEAD -- data/mvp/metis_brain_bundle_v0.json` 로 복구.

**Q. override env 로 다른 번들을 가리켜도 되나요?**
A. 개발/스테이징에선 ok. 라이브 production 에서는 **v2 rollback 목적** 외에는 쓰지 말 것 (원칙: "env override > validated v2 > validated v0").

**Q. graduation 이 실패하면 v2 파일이 남나요?**
A. `scripts/agh_v1_patch_8_production_bundle_graduation.py` 는 atomic write 라 integrity fail 시 **기존 v2 파일을 덮어쓰지 않고** 새 파일 생성도 하지 않습니다. 만약 중간에 프로세스가 죽었다면 §5 케이스 B.

## 9. Sign-off 체크리스트

- [ ] `/api/runtime/health.degraded_reasons` 에서 `v2_integrity_failed` 가 사라짐.
- [ ] `mvp_brain_gate.brain_bundle_tier == 'production'` (원한 경우) 또는 `'sample'` (의도적 rollback 경우).
- [ ] UI bundle-tier chip 이 fallback variant 에서 복귀.
- [ ] `validate-metis-brain-bundle` CLI 가 `ok:true`.
- [ ] `scripts/agh_v1_patch_9_production_graduation_runbook.py` 재실행시 S1+S2 flag green.

---

## 10. 참고

- 본 런북은 `docs/plan/METIS_Scale_Readiness_Note_Patch9_v1.md` 와 짝이다.
- 관련 구현:
  - `src/metis_brain/bundle.py::brain_bundle_path` / `brain_bundle_integrity_report_for_path` / `_quick_integrity_ok` / `_production_tier_integrity_checks`.
  - `src/phase51_runtime/cockpit_health_surface.py` (health 페이로드 + degraded reason 누적).
  - `src/phase47_runtime/static/app.js::hydrateBundleTierChip` (UI fallback variant).
- 테스트: `src/tests/test_agh_v1_patch9_production_surface.py` A1 + A2 블록 + D1 fallback chip 블록.
