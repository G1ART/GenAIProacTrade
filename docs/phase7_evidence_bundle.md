# Phase 7.1 — 실데이터 end-to-end 증거 번들

## 목적

최소 **3명의 실제 `state_change_candidates` 행**에 대해, 하네스 입력 → 메모 → 클레임 → 리뷰 큐 → Referee → **동일 입력 재실행 요약**까지 재현 가능한 스냅샷을 남긴다.

## 전제

1. Supabase에 `20250409100000_phase7_ai_harness_minimum.sql` 및 `20250410100000_phase71_harness_hardening.sql` 적용.
2. 해당 유니버스에 대해 `build-ai-harness-inputs`가 이미 돌아가 **동일 run**에 harness 입력이 존재.

## 생성 명령 (권장)

`STATE_CHANGE_RUN_UUID`는 `state_change_runs` 또는 `report-state-change-summary` 출력에서 복사.

```bash
cd ~/GenAIProacTrade && source .venv/bin/activate && export PYTHONPATH=src
python3 src/main.py export-phase7-evidence-bundle \
  --from-run STATE_CHANGE_RUN_UUID \
  --sample-n 3 \
  --out-dir docs/phase7_real_samples/latest
```

완료 후 `docs/phase7_real_samples/latest/manifest.json` 에 후보별 `candidate_id`, `memo_id`, `claims_count`, `referee_passed` 가 기록된다.

## 번들에 포함되는 것 (후보별 디렉터리)

| 파일 | 내용 |
|------|------|
| `state_change_candidate.json` | 후보 원본 행 |
| `ai_harness_input.json` | `ai_harness_candidate_inputs` 행 (payload 포함) |
| `investigation_memo.json` | 최신 `investigation_memos` |
| `investigation_memo_claims.json` | 해당 `memo_id`의 모든 클레임 |
| `operator_review_queue.json` | 큐 행 |
| `rerun_generate_summary.json` | 동일 후보에 대해 `generate-investigation-memos`를 **두 번** 호출한 카운트 요약(두 번째는 `memos_replaced_in_place` 기대) |

## 완료 보고 시 기입할 항목

- 사용한 **정확한 `candidate_id` 세트** (manifest에서 복사).
- `rerun_generate_summary.json` 안의 `first` / `second` 블록.

## 이 레포에 샘플 JSON을 커밋하지 않는 경우

민감도·용량 정책으로 JSON을 커밋하지 않으면, 위 명령과 **manifest의 ID 목록**만 커밋하고 JSON은 로컬/아티팩트 저장소에 둔다.
