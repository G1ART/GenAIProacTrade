# Phase 47 evidence — founder cockpit runtime

## 확인 체크리스트

- `PYTHONPATH=src python3 src/phase47_runtime/app.py` → stdout에 `listening` JSON, 브라우저에서 UI 로드
- `GET /api/meta` → `phase46_generated_utc`, `bundle_stale`, 레저 경로
- 알림 패널: `GET /api/notifications` (런타임 프로세스 내 이벤트)
- `pytest src/tests/test_phase47_founder_cockpit_runtime.py -q`
- 거버넌스: 대화 응답 JSON에 Phase 43 레거시 금지 토큰 **부재**

## 산출물

| 산출물 | 경로 |
|--------|------|
| 런타임 메타 번들 | `docs/operator_closeout/phase47_founder_cockpit_runtime_bundle.json` |
| 리뷰 | `docs/operator_closeout/phase47_founder_cockpit_runtime_review.md` |
| 배포 노트 | `docs/operator_closeout/phase47_runtime_deploy_notes.md` |

## 저장소 기록 (예시)

| 필드 | 값 |
|------|-----|
| `generated_utc` | `2026-04-12T22:02:36.869500+00:00` |
| 입력 Phase 46 | `phase46_founder_decision_cockpit_bundle.json` |
| `phase48.phase48_recommendation` | `external_notification_connectors_and_runtime_audit_log_v1` |

## 번들 필수 필드 (요지)

`ok`, `phase`, `generated_utc`, `input_phase46_bundle_path`, `runtime_entrypoint`, `runtime_views`, `governed_conversation_contract`, `alert_actions_supported`, `decision_actions_supported`, `reload_model`, `deploy_target`, `phase48`

## Related

`docs/phase47_patch_report.md`, `docs/phase46_evidence.md`, **`docs/operator_closeout/phase48_closeout.md`** (Phase 48 종료·Phase 49 연계), **`docs/operator_closeout/phase50_closeout.md`** (Phase 50 제어 평면·스모크), `HANDOFF.md`, `docs/research_engine_constitution.md`
