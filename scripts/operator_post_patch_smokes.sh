#!/usr/bin/env bash
# 패치 후 공개 수리·반복 스택 테이블 도달 일괄 확인 (네트워크·Supabase 설정 필요).
# 사용: 프로젝트 루트에서 ./scripts/operator_post_patch_smokes.sh
# Phase 23+: 동일 스모크 체인은 `python3 src/main.py verify-db-phase-state` 및
# `run-post-patch-closeout --universe U` 안에 포함된다.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="${ROOT}/src"
MAIN=(python3 "${ROOT}/src/main.py")

run() {
  echo ""
  echo "=== $* ==="
  "${MAIN[@]}" "$@"
}

cd "$ROOT"
run smoke-phase17-public-depth
run smoke-phase18-public-buildout
run smoke-phase19-public-repair-campaign
run smoke-phase20-repair-iteration
run smoke-phase21-iteration-governance
run smoke-phase22-public-depth-iteration
echo ""
echo "OK: operator_post_patch_smokes (phase17–22) completed."
