# 패치 후 운영 (Phase 23 — 정상 경로)

골든 경로에서는 **시리즈 UUID를 찾거나 붙여넣지 않는다.** 내부 ID는 로그·`latest_closeout_summary.md`·JSON 산출물에만 남는다.

## 1) 한 줄 클로즈아웃

```bash
export PYTHONPATH=src
python3 src/main.py run-post-patch-closeout --universe YOUR_UNIVERSE
```

프리셋(유니버스·출력 stem)을 쓰려면 프로젝트 루트에 `.operator_closeout_preset.json`을 두고:

```bash
python3 src/main.py run-post-patch-closeout --use-default-preset
```

예시 형식: `docs/operator_closeout_preset.example.json`

이 명령은 **마이그레이션 리포트**(가능하면 `schema_migrations` 대비) → **phase17–22 스모크** → **활성 시리즈 자동 해석/생성** → **결정적 다음 단계**(수리 전진 / 공개 깊이 전진 / 플래토 홀드 / 검증만) → **브리프 export** → **`docs/operator_closeout/latest_closeout_summary.md`** 를 수행한다.

검증만(전진 없이 브리프·스모크): `--verify-only`

성공적으로 끝나면 **추가 필수 액션은 없다.** `schema_migrations` API가 `PGRST106` 등으로 막혀 있어도, 스모크가 통과한 한 스키마는 클로즈아웃 관점에서 정상이다. 운영 실측·후속 선택 사항은 `docs/phase23_evidence.md` 참고.

## 2) 마이그레이션 프리플라이트(선택·수동 적용 전)

```bash
python3 src/main.py report-required-migrations
# 누락분 SQL 번들:
python3 src/main.py report-required-migrations --write-bundle
```

`schema_migrations` 테이블이 PostgREST에 안 보이면 JSON에 `applied_probe_ok: false` 로 표시되고, **스키마 진실은 `verify-db-phase-state` 스모크**가 담당한다.

## 3) 스모크만 단독 확인

```bash
python3 src/main.py verify-db-phase-state
# 또는 기존 셸 일괄
./scripts/operator_post_patch_smokes.sh
```

---

## 부록 A — 브리프·전진(명시 UUID는 디버그 전용)

운영 모드(`--program-id` + `--universe`, `--series-id` 생략):

```bash
python3 src/main.py export-public-depth-series-brief \
  --program-id latest --universe YOUR_UNIVERSE \
  --out docs/public_depth/series_brief_latest
```

`advance-public-repair-series` / `advance-public-depth-iteration` 은 기존처럼 시리즈 생략 시 **latest-active-series** 해석을 쓴다.

## 부록 B — 로컬 테스트

```bash
PYTHONPATH=src pytest src/tests -q
```

## 부록 C — Phase 23 구현 메모

- 결정 함수: `operator_closeout.next_step.choose_post_patch_next_action` / `choose_post_patch_next_action_from_signals`
- 클로즈아웃 오케스트레이션: `operator_closeout.closeout.run_post_patch_closeout`
- 시리즈 해석(무 UUID): `public_repair_iteration.depth_iteration.resolve_iteration_series_for_operator`

상세 보고: `docs/phase23_patch_report.md` · 핸드오프: `HANDOFF.md` (Phase 23 절).

## 부록 D — Phase 24 (경험층·교대)

반복 주기의 **집계·판독**:

```bash
python3 src/main.py report-public-first-branch-census --program-id latest --universe YOUR_UNIVERSE
python3 src/main.py export-public-first-plateau-review-brief --program-id latest --universe YOUR_UNIVERSE
python3 src/main.py advance-public-first-cycle --universe YOUR_UNIVERSE
```

- `latest_public_first_review.md` — 지배 브랜치·개선·권장 다음 명령.
- 프리미엄: `premium_discovery_review_preparable` 은 **리뷰 준비** 표식일 뿐, **자동 라이브 통합 없음**.

보고: `docs/phase24_patch_report.md` · 핸드오프: `HANDOFF.md` (Phase 24 절).
