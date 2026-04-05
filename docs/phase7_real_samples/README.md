# Phase 7 실데이터 증거 샘플 (출력 디렉터리)

이 폴더는 **기본적으로 비어 있거나** `export-phase7-evidence-bundle` 실행 결과만 둡니다.

운영 DB에서 최소 3개 후보에 대해 번들을 만들려면:

```bash
cd ~/GenAIProacTrade && source .venv/bin/activate && export PYTHONPATH=src
python3 src/main.py export-phase7-evidence-bundle \
  --from-run <STATE_CHANGE_RUN_UUID> \
  --sample-n 3 \
  --out-dir docs/phase7_real_samples/latest
```

또는 알려진 `candidate_id` 세 개를 지정:

```bash
python3 src/main.py export-phase7-evidence-bundle \
  --candidate-ids <UUID1>,<UUID2>,<UUID3> \
  --out-dir docs/phase7_real_samples/latest
```

각 후보 하위 폴더에는 `ai_harness_input.json`, `investigation_memo.json`, `investigation_memo_claims.json`, `operator_review_queue.json`, `rerun_generate_summary.json` 등이 생성됩니다. **가짜 ID로 수동 작성하지 말 것** — 워크오더 금지 사항.
