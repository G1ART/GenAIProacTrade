# Phase 14 증거 — Research Engine Kernel

**범위**: 단일 프로그램·단일 지평(`next_quarter`)·공개 데이터만. 프리미엄 불필요. **제품 스코어링/워치리스트에 자동 연결 없음.**

## 잠금 연구 질문

`research_engine.constants`에 고정된 문장과 동일:

- 왜 유사해 보이는 결정적 state-change 신호가 일부 종목에서는 빠르게 가격에 반영되고, 다른 종목에서는 분기 내 지연·약한 반응·불일치가 나타나는가?

## 테이블

| 테이블 | 역할 |
|--------|------|
| `research_programs` | 프로그램 메타, `linked_quality_context_json`(Phase 13 품질 스냅샷), `premium_overlays_allowed=false` |
| `research_hypotheses` | 경제적 근거·메커니즘·특성 정의·실패 모드 JSON |
| `research_reviews` | 렌즈 `mechanism` / `pit_data` / `residual` / `compression`, 라운드 1–2 |
| `research_referee_decisions` | `kill` / `sandbox` / `candidate_recipe`, `disagreement_json` |
| `research_residual_links` | 잔차 버킷·미해결 이유·프리미엄 힌트(정보만) |

마이그레이션: `20250417100000_phase14_research_engine_kernel.sql`

## 운영자 플로우 (CLI)

저장소 루트에서 `PYTHONPATH=src`, `.env` 로드 후:

1. `smoke-phase14-research-engine`
2. `create-research-program --universe sp500_current` (선택 `--quality-run-id UUID`)
3. `generate-program-hypotheses --program-id UUID`
4. 각 가설에 `review-research-hypothesis --hypothesis-id UUID` (최대 2회)
5. `run-research-referee --hypothesis-id UUID`
6. `export-research-dossier --program-id UUID --out docs/research_engine/dossiers/latest.json`

## 심판 정책 요약

- `thin_input` 또는 `insufficient_data_fraction` ≥ 0.75 인 품질 맥락만으로는 **`candidate_recipe` 불가**(샌드박스 상한).
- `failed` / `degraded` 품질은 PIT 렌즈에서 `reject` → 심판 `kill` 경로.
- `strong` / `usable_with_gaps` 이고 필수 렌즈가 모두 `pass`이면 `candidate_recipe` 가능(여전히 연구 단계).

## 코드 위치

- `src/research_engine/` — 상수, 리뷰어, 심판, 서비스, dossier 조립
- `src/db/records.py` — CRUD 헬퍼
- `src/main.py` — 위 CLI

## 테스트

`src/tests/test_phase14.py` — 심판·라운드 상한·dossier·`state_change.runner` 비침투 등.
