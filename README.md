# GenAIProacTrade — Phase 0–6 + Universe Backfill (SEC + XBRL + 팩터 + 시장 + 연구 + 상태변화 + 오케스트레이션)

## Metis MVP 제품면 (현재 권위 문서와 위치)

이 저장소의 **MVP 제품 정의·실행 우선순위**는 아래 두 문서가 단일 권위입니다.

- `docs/plan/METIS_MVP_Unified_Product_Spec_KR_v1.md` — Today / Research / Replay, Bones·Heart·Brain·Skin, **Today 읽기 전용 입력 = Active Horizon Model Registry** 등.
- `docs/plan/METIS_MVP_Unified_Build_Plan_KR_v1.md` — Stage 0(Brain Lock) → Stage 6(Trust) 순서, **스킨보다 Brain 먼저** 명시.

**코드 기준 현재 위치 (요약).**

- **닫힌 것(계약·수직 슬라이스)**: `src/metis_brain`에 Artifact / Promotion Gate / Registry 스키마와 번들 검증(`validate_active_registry_integrity`), Phase 47 런타임에서 **Registry 우선 Today**·메시지 스냅샷·Replay lineage·워치 순서·헬스의 `mvp_brain_gate` 등 **제품 표면과 Brain JSON 계약**이 연결되어 있습니다.
- **아직 데모에 가까운 것(실질)**: `data/mvp/metis_brain_bundle_v0.json`은 시드 스펙트럼과 맞춘 **데모/스모크 번들**이며, `deterministic_kernel:v0`·`stub_feature_set` 등으로 **실제 검증 파이프라인이 자동 생산한 모델 패밀리**를 대체하지는 않습니다.
- **다음 P0 (로드맵과 감사 공통)**: `factor_validation_*` / `research_validation` 결과를 **ModelArtifactPacketV0 + metric 기반 PromotionGateRecordV0 + Registry entry**로 뽑아 내는 **빌더·승격 다리**를 코드로 닫는 것. 그 위에 Research Ask/Sandbox **acceptance 문장**을 스펙 수준으로 조이는 것. (쉘·커넥터 확장은 뒤로.)

런타임 스모크: `python3 src/main.py validate-metis-brain-bundle`, Today 스펙트럼은 `python3 src/phase47_runtime/app.py` 후 `/api/today/spectrum` 등. **스펙 §10 대비 자동 신호**는 `GET /api/runtime/health` JSON의 `mvp_product_spec_survey_v0`, 또는 `PYTHONPATH=src python3 src/main.py print-mvp-spec-survey --repo-root .`와 `docs/plan/METIS_MVP_PROGRESS_VS_SPEC_KR_v1.md`를 본다.

검증 → 게이트(JSON) 한 걸음(DB에 completed `factor_validation`이 있을 때):  
`python3 src/main.py export-metis-gates-from-factor-validation --factor accruals --universe sp500_current --horizon next_month --return-basis excess --artifact-id <번들의 artifact_id>`  
PIT은 `summary_json.pit_certified`가 true일 때만 통과로 표시됩니다. 미설정 시 운영자가 PIT 근거를 채운 뒤 번들에 병합합니다.

`PYTHONPATH=src python3 src/main.py merge-metis-gate-into-bundle --repo-root . --from-json <export.json> --dry-run`으로 스키마·active registry 무결성을 확인한 뒤, 통과하면 `--dry-run` 없이 저장(`--out`으로 다른 경로에 쓸 수 있음). DB run과 아티팩트를 맞출 때는 `--sync-artifact-validation-pointer`로 `validation_pointer`를 `factor_validation_run:<run_id>` 형태로 갱신할 수 있다.

**한 방 빌드(Slice A)**: `data/mvp/metis_bundle_from_validation_config.example.json`을 복사해 `gates[]`(팩터·유니버스·검증 지평·return_basis·번들의 `artifact_id`)를 채운 뒤, `PYTHONPATH=src python3 src/main.py build-metis-brain-bundle-from-factor-validation --repo-root . --config <your.json> --dry-run` → 무결성 통과 시 `--dry-run` 제거해 `output_bundle_path`에 저장. 실패 시 JSON `report.steps`·`errors`로 원인이 한 번에 나온다.

**스냅샷 스레드(Slice B)**: `GET /api/today/object` 응답 최상위 `message_snapshot_id`·`research.message_snapshot_id`가 `replay_lineage_join_v1`과 동일. `POST /api/conversation` 본문에 `message_snapshot_id`만 넘기면 저장된 스냅샷으로 copilot 컨텍스트가 채워져 Ask가 동일 메시지에 답한다. 샌드박스는 `message_snapshot_id`로 자산·헤드라인 맥락을 주입할 수 있다.

---

미국 SEC **공시 메타데이터**·**XBRL fact**·**분기 스냅샷**·**회계 팩터**에 이어, Phase 4에서 **시장 가격·선행 수익률·무위험 이자율**을 **provider 추상화**로 적재하고 **`factor_market_validation_panels`** 까지 조인합니다. **Phase 5**에서는 그 패널 위에 **결정적 기술 검증·분위 기술통계**를 쌓는 **`factor_validation_*` 연구 레이어**(백테스트·전략·실행 아님)를 추가합니다.

**Phase 4–6(아래 데이터·CLI 본문 기준)에서 원래 범위 밖인 것**: 팩터 **랭킹·알파 점수**, 포트폴리오·롱숏 바스켓, **백테스트 리포트**, **OpenAI/AI 하네스**, 알림·Slack·email, Railway·**스케줄러/cron**, “공식 S&P 편입 후보” 포장. (GDELT/FINRA 등 확장 API는 무위험 FRED 최소 수준만.) **Metis MVP 제품 셸(Today/Research/Replay 등)** 은 `src/phase47_runtime` 에서 별도로 제공되며, 위 Phase 4–6 문단은 **truth·검증 서브스트레이트** 설명에 가깝다.

**Phase 6 한 줄**: “좋은 팩터 연구”가 아니라, truth spine + Phase 5와 **분리된** **issuer–날짜 단위 상태변화 후보 스파인**(`state_change_*`). **매수·매도·전략 점수·추천 메시지 없음** — `investigate_*` 등 **조사 후보 분류**만.

## Phase 4 목표 (market validation layer)

- **Provider 추상화**: `src/market/providers/base.py`의 `MarketDataProvider`. 기본 구현 `yahoo_chart`(일봉 JSON + 위키 S&P 표, urllib) 및 테스트용 `stub`(`MARKET_DATA_PROVIDER=stub`).
- **유니버스**: `sp500_current`(구성종목, `membership_status=constituent`)와 **`sp500_proxy_candidates_v1`**(시드 `config/sp500_proxy_candidates_v1.json` 기반 **비공식 프록시 후보**, 공식 위원회 후보 아님).
- **가격 계층**: `raw_market_prices_daily`(원문) → `silver_market_prices_daily`(정규화, **조정종가 우선**, `daily_return`).
- **무위험**: `risk_free_rates_daily` — 기본 소스 **FRED DTB3** graph CSV (`src/market/risk_free_fred.py`): URL에 **cosd/coed**로 요청 구간을 한정해 CSV 부하·**504** 가능성을 줄이고, **httpx** + **5xx/429 재시도**, `source_name=fred_dtb3_graph_csv`. 여전히 504면 FRED 측 게이트웨이 이슈일 수 있으니 잠시 후 `ingest-risk-free`를 다시 실행하면 됩니다.
- **선행 수익률**: `forward_returns_daily_horizons`, `horizon_type` = `next_month`(약 21거래일) / `next_quarter`(약 63거래일). **raw**와 **excess** 모두 저장.
- **검증 패널**: `factor_market_validation_panels` — 팩터 패널 + 시그널일 + 선행수익률 + (있으면) 메타. **research/backtest 아님.**

### Phase 4: raw vs excess 정의

- **raw_forward_return**: `silver` 기준 가격(조정종가 우선)으로, 시그널일 이후 첫 거래일 종가 → 각 지평 종가까지의 총수익률.
- **excess_forward_return**: 동일 구간 거래일 수 `n`에 대해, 해당 기간 일별 무위험 **연율화(%) 평균**으로 `period_rf ≈ (1+r_avg/100)^(n/252)−1` 를 두고 `(1+raw)/(1+period_rf)−1` (단순화, `return_basis_json`에 메타).

### Phase 4: 시그널일·no-lookahead (보수적)

- `signal_available_date` = `issuer_quarter_snapshots`의 **`accepted_at`이 있으면 그 UTC 날짜의 다음 날부터 첫 평일**, 없으면 **`filed_at`** 동일. **접수 당일 종가는 사용하지 않음.** 캘린더는 MVP로 **주말만 제외**(NYSE 휴장일 전체 반영 아님 — `schema_notes` 동일).
- 가격·무위험·선행수익률·검증 패널 빌드는 `ingest_runs`에 각각 `universe_refresh`, `universe_candidate_build`, `market_prices_ingest`, `market_metadata_refresh`, `risk_free_ingest`, `forward_return_build`, `factor_market_validation_build` 로 남김.

## Phase 5 목표 (research validation layer — 실행·백테스트 아님)

- **입력**: `factor_market_validation_panels` + `issuer_quarter_factor_panels`(조인으로 팩터 값) + 유니버스 슬라이스(`universe_memberships` 최신 `as_of_date` 배치).
- **산출 테이블**: `factor_validation_runs`, `factor_validation_summaries`, `factor_quantile_results`, `factor_coverage_reports` — **기술 통계·상관·분위 기술요약**만. **p-value·과신적 해석·전략 수익·알파·포트폴리오** 없음.
- **검증 대상 팩터(6개)**: `src/research/validation_registry.py` — `accruals`, `gross_profitability`, `asset_growth`, `capex_intensity`, `rnd_intensity`, `financial_strength_score_v1`(DB 컬럼 `financial_strength_score`).
- **수익 기준**: 각 실행에서 **`raw`와 `excess`를 각각** 요약·분위 행으로 저장(`return_basis`).
- **유니버스 슬라이스**:
  - `sp500_current` — 최신 `as_of_date`의 S&P 구성 심볼.
  - `sp500_proxy_candidates_v1` — 최신 배치의 프록시 후보 심볼.
  - `combined_largecap_research_v1` — 위 둘의 **결정적 합집합**(대문자 정렬).
- **분위**: 기본 **5분위(quintile)**. 표본이 작으면 자동으로 분위 수 축소 또는 분위 스킵(`quantiles` 모듈).
- **표준화**: 검증용 **z-score**·선택적 **winsorize(1%/99%)** — truth 테이블의 팩터 컬럼은 변경하지 않음.
- **단순 OLS**(선택, `--ols`): `return ~ factor` 및 `return ~ zscore(factor)` 요약만 `summary_json`에 기록. **Robust SE, 패널 회귀, Fama–MacBeth 미구현**(README 명시).
- **상·하 분위 spread**: `factor_quantile_results`·`summary_json`에 **기술적** top/bottom 평균 수익 차이만 — **전략·백테스트·alpha 표현 금지**.

### Phase 5: SQL 적용 **이후** 액션 (잘게 쪼갠 복붙)

**전제**: Supabase SQL Editor에서 `20250406100000_phase5_factor_validation_research.sql` 실행 완료.  
**데이터 전제**: `factor_market_validation_panels`에 검증할 행이 있어야 함(없으면 Phase 4의 `build-forward-returns` → `build-validation-panel` 먼저).

아래에서 `/path/to/GenAIProacTrade` 를 본인 프로젝트 루트로 바꿉니다.

**0) (선택) Phase 4 패널이 비어 있을 때만** — 이미 채워져 있으면 건너뜀.

```bash
cd /path/to/GenAIProacTrade
source .venv/bin/activate
export PYTHONPATH=src

python3 src/main.py build-forward-returns --limit-panels 500
python3 src/main.py build-validation-panel --limit-panels 500
```

**1) 터미널 공통 준비** (매 세션 또는 스크립트 맨 위)

```bash
cd /path/to/GenAIProacTrade
source .venv/bin/activate
export PYTHONPATH=src
```

**2) Phase 5 테이블 스모크** (DB·`.env`·마이그레이션 확인)

```bash
python3 src/main.py smoke-research
```

**3) 검증 실행 — S&P 슬라이스·1개월 지평**

```bash
python3 src/main.py run-factor-validation --universe sp500_current --horizon next_month
```

**4) 검증 실행 — S&P 슬라이스·1분기 지평**

```bash
python3 src/main.py run-factor-validation --universe sp500_current --horizon next_quarter
```

**5) 검증 실행 — 프록시 후보만** (`build-candidate-universe` 후 멤버십이 있을 때)

```bash
python3 src/main.py run-factor-validation --universe sp500_proxy_candidates_v1 --horizon next_month
```

**6) 검증 실행 — 합집합 슬라이스** (`sp500_current` ∪ `sp500_proxy_candidates_v1`)

```bash
python3 src/main.py run-factor-validation --universe combined_largecap_research_v1 --horizon next_month
```

**7) (선택) OLS + winsorize 보조 요약까지**

```bash
python3 src/main.py run-factor-validation --universe sp500_current --horizon next_month --ols --winsorize
```

**8) 터미널 요약 보기 — raw 기준**

```bash
python3 src/main.py report-factor-summary --factor accruals --universe sp500_current --horizon next_month --return-basis raw
```

**9) 터미널 요약 보기 — excess 기준**

```bash
python3 src/main.py report-factor-summary --factor accruals --universe sp500_current --horizon next_month --return-basis excess
```

**10) 다른 팩터 요약** (`gross_profitability`, `asset_growth`, `capex_intensity`, `rnd_intensity`, `financial_strength_score_v1`)

```bash
python3 src/main.py report-factor-summary --factor gross_profitability --universe sp500_current --horizon next_month
```

**11) Git — 원격에 반영** (브랜치명은 저장소에 맞게 수정)

```bash
cd /path/to/GenAIProacTrade
git status
git pull --rebase origin main
git add -A
git commit -m "Phase 5: factor validation research layer and docs."
git push origin main
```

원격·브랜치가 없으면:

```bash
cd /path/to/GenAIProacTrade
git init
git add -A
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USER/YOUR_REPO.git
git branch -M main
git push -u origin main
```

### Phase 5에서 하지 않는 것

- 포트폴리오 구성, 롱/숏 바스켓 엔진, 백테스트, 퍼포먼스 티어시트, 알파·복합 매매 점수, AI 하네스, 알림, 자동매매, UI/대시보드, 과도한 계량경제 추론.

## Phase 6 목표 (state change engine v1 — 실행·선행라벨 입력 금지)

- **Phase 5와 차이**: Phase 5는 `factor_market_validation_panels` 위 **선행 수익률 라벨**로 기술 검증(상관·분위 등). Phase 6은 **그 라벨을 feature로 쓰지 않음** — 입력은 `issuer_quarter_factor_panels`, `issuer_quarter_snapshots`, `universe_memberships`, `market_symbol_registry`, `market_metadata_latest`, `risk_free_rates_daily` 및 **시점 합법적인** 맥락만. `factor_market_validation_panels`는 **검증/감사 참고용**일 뿐 state change의 SSOT가 아님.
- **산출 테이블**: `state_change_runs`, `issuer_state_change_components`, `issuer_state_change_scores`, `state_change_candidates`.
- **코드**: `src/state_change/` — `signal_registry.py`(방향·변환 규칙), `runner.py`, `scoring.py`(투명 가중 합성; 누락 축은 제외·`missing_component_count`·`normalized_weight_sum` 기록).
- **CLI**: `smoke-state-change`, `run-state-change`, `report-state-change-summary`.
- **하지 않는 것**: AI 하네스, 알림, 대시보드, 포트폴리오, 백테스트 확장, long/short·trade 추천 언어, Phase 5 결과를 실행 엔진처럼 포장.

### Phase 6: SQL 적용 **이후** 복붙 절차 (대표님용)

**전제**: Supabase SQL Editor에서 `20250407100000_phase6_state_change_engine.sql` 실행 완료.  
**데이터 전제**: 조사 대상 유니버스에 맞는 `issuer_quarter_factor_panels` 행이 있을 것(워치리스트만 있으면 `sp500_current` 슬라이스는 빈 결과일 수 있음).

`/path/to/GenAIProacTrade` 를 본인 루트로 바꿉니다.

```bash
cd /path/to/GenAIProacTrade
source .venv/bin/activate
export PYTHONPATH=src
```

**(1) migration 적용** — 위 SQL 파일을 SQL Editor에서 실행(로컬에만 있다면 동일 내용 붙여넣기).

**(2) smoke-state-change**

```bash
python3 src/main.py smoke-state-change
```

**(3) run-state-change 소규모 샘플** (`--dry-run` 으로 DB 미적재 확인 가능)

```bash
python3 src/main.py run-state-change --universe sp500_proxy_candidates_v1 --limit 15 --dry-run --output-json
python3 src/main.py run-state-change --universe sp500_proxy_candidates_v1 --limit 15 --output-json
```

`status=no_observations` 이고 `run_id`가 null이면, 해당 유니버스 CIK에 **`issuer_quarter_factor_panels` 행이 없는 것**이 흔한 원인입니다. 이 경우 DB에 `state_change_runs`가 만들어지지 않아 **`report-state-change-summary --universe`는 `no_completed_run_found`로 끝납니다.** 먼저 팩터 패널을 적재하세요. 예: **`python3 src/main.py compute-factors-watchlist`** 는 인자 없이 **`config/watchlist.json`** 을 씁니다. 다른 목록을 쓰려면 **`--watchlist`에 실제 존재하는 JSON 경로**를 넣거나 `WATCHLIST_PATH`를 설정하세요. 프록시 유니버스 티커만 필요하면 `compute-factors-single --ticker LCID` 처럼 티커별로 돌릴 수 있습니다.

**(4) report-state-change-summary** (`--universe` 로 해당 유니버스 최근 completed run)

```bash
python3 src/main.py report-state-change-summary --universe sp500_proxy_candidates_v1
python3 src/main.py report-state-change-summary --universe sp500_proxy_candidates_v1 --output-json
```

**(5) 결과 row count 확인 SQL** (Supabase SQL Editor)

```sql
select count(*) from issuer_state_change_components where run_id = '<RUN_UUID>';
select count(*) from issuer_state_change_scores where run_id = '<RUN_UUID>';
select count(*) from state_change_candidates where run_id = '<RUN_UUID>';
```

**(6) 상위 candidate 20개 확인 SQL**

```sql
select candidate_rank, candidate_class, cik, ticker, as_of_date, confidence_band
from state_change_candidates
where run_id = '<RUN_UUID>'
order by candidate_rank
limit 20;
```

**(7)–(10) git** (브랜치 `phase6-state-change-v1` 등 저장소에 맞게 조정)

```bash
git status
git checkout -b phase6-state-change-v1
git add -A
git commit -m "phase6: add deterministic state change engine v1"
git push -u origin phase6-state-change-v1
```

### Phase 6 CLI 예시 (요약)

```bash
export PYTHONPATH=src
python3 src/main.py smoke-state-change
python3 src/main.py run-state-change --universe combined_largecap_research_v1 --limit 50 --start-date 2022-01-01 --end-date 2024-12-31
python3 src/main.py report-state-change-summary --run-id <UUID>
```

## Phase 7 목표 (AI Harness Minimum / Message Layer Minimum)

- **역할**: `state_change_candidates` 등 **결정적 산출**을 바탕으로 **조사용 1p 메모**(thesis + **필수** 반론 + 합성)와 **운영자 리뷰 큐**를 제공. 진실 테이블(Phase 0–6)은 **읽기만** 하고 **AI가 점수를 덮어쓰지 않음**.
- **산출 테이블**: `ai_harness_candidate_inputs`, `investigation_memos`, `investigation_memo_claims`, `operator_review_queue`; 스텁 `hypothesis_registry`, `promotion_gate_events`.
- **코드**: `src/harness/` — `input_materializer.py`, `roles/deterministic_agents.py`, `referee/gate.py`, `memo_builder/pipeline.py`, `run_batch.py`; 라우팅 우선순위 문서 `harness/routing_policy_doc.py`; 미래 봉인 `docs/phase7_future_seams.md`, `src/research_lab/`.
- **CLI**: `smoke-harness`, `build-ai-harness-inputs`, `generate-investigation-memos`, `report-review-queue`, `set-review-queue-status`, `export-phase7-evidence-bundle`.
- **마이그레이션**: `20250409100000_phase7_ai_harness_minimum.sql` → `20250410100000_phase71_harness_hardening.sql` (순서대로 적용).
- **하지 않는 것**: 매매·포트폴리오·실행 자동화·알파 홍보·백테스트 실적 주장·LLM 수치 조작·선행수익을 **모델 피처**로 주입(Phase 6 금지 유지).

### Phase 7.1 (마감 / 하드닝)

- **클레임 행**: `investigation_memo_claims`에 `claim_id`, `claim_role`, `statement`, `support_summary`, `counter_evidence_summary`, `trace_refs`, `needs_verification`, `verdict`, `candidate_id` 등 — 메모 전체가 아니라 **주장 단위** 추적.
- **재실행**: 동일 `payload_hash` + 동일 `generation_mode`이면 **최신 메모 행 in-place 갱신** + 클레임 전량 삭제 후 재삽입; 입력이 바뀌면 `memo_version = max+1` 신규 행. `--force-new-memo-version`이면 항상 신규 버전.
- **리뷰 큐**: `reviewed` / `needs_followup` / `blocked_insufficient_data`는 메모 재생성 시 **상태 유지**(memo_id만 최신으로). 신규 행은 referee 실패 시 `needs_followup`, 성공 시 `pending`.
- **Referee**: 반론 차원 누락, 합성에서 이견 구조 미보존, 한계 서술 과소, thesis 내 허용되지 않은 수치 등 **구조 검사** 추가.
- **최상위 스펙 MD**: `docs/spec/*.md` (`scripts/docx_to_spec_md.py`로 `.docx` 재생성 가능).
- **실데이터 번들**: `docs/phase7_evidence_bundle.md` 참고 후 `export-phase7-evidence-bundle` 실행 → `docs/phase7_real_samples/latest/` 등에 JSON 스냅샷.

```bash
export PYTHONPATH=src
python3 src/main.py smoke-harness
python3 src/main.py build-ai-harness-inputs --universe sp500_current --limit 200
python3 src/main.py generate-investigation-memos --universe sp500_current --limit 200
python3 src/main.py generate-investigation-memos --universe sp500_current --candidate-ids <UUID>,<UUID>
python3 src/main.py report-review-queue --limit 50
python3 src/main.py set-review-queue-status --candidate-id <UUID> --status reviewed --reason "initial operator pass"
python3 src/main.py export-phase7-evidence-bundle --from-run <STATE_CHANGE_RUN_UUID> --sample-n 3 --out-dir docs/phase7_real_samples/latest
```

## Phase 8 목표 (Outlier Casebook + Daily Scanner)

- **역할**: 결정적 스파인·메모·검증 조인에서 **불일치/이상 패턴**을 `outlier_casebook_*`에 축적하고, **일일 저잡음 워치리스트**(`scanner_runs`, `daily_signal_snapshots`, `daily_watchlist_entries`)로 운영 우선순위를 만든다. **매매·포트폴리오·실행·대시보드 UI 아님.**
- **탐지**: `outlier_heuristic_v1` — 반응 갭(검증 패널/선행수익 조인), 메모/referee 긴장, 데이터 스트레스, 레짐/지속성 휴리스틱 등. **`is_heuristic=true`** 명시.
- **메시지 계약**: 각 케이스/워치 행에 `message_short_title`, `message_why_matters`, `message_what_could_wrong`, `message_unknown`, `message_plain_language` + 구조 필드 유지.
- **오버레이 스텁**: `overlay_future_seams_json` — 뉴스/지분/포지션/거시는 `not_available_yet` (가짜 데이터 없음).
- **코드**: `src/casebook/`, `src/scanner/`, `src/message_contract/`.
- **CLI**: `smoke-phase8`, `build-outlier-casebook`, `build-daily-signal-snapshot`, `report-daily-watchlist`, `export-casebook-samples`.
- **마이그레이션**: `20250411100000_phase8_casebook_scanner.sql` (Phase 7.1 이후).
- **증거 절차**: `docs/phase8_evidence.md`, 샘플 출력 `docs/phase8_samples/` (로컬 DB에서 생성).

```bash
export PYTHONPATH=src
python3 src/main.py smoke-phase8
python3 src/main.py build-outlier-casebook --universe sp500_current --candidate-limit 600
python3 src/main.py export-casebook-samples --state-change-run-id <STATE_CHANGE_RUN_UUID> --limit 20 --out-dir docs/phase8_samples/latest
python3 src/main.py build-daily-signal-snapshot --universe sp500_current --top-n 15 --min-priority-score 20
python3 src/main.py report-daily-watchlist
```

## Phase 9 목표 (운영 가시성 · 실패 추적 · 연구 레지스트리)

- **역할**: 실행 단위로 **쿼리 가능한** 감사(`operational_runs` / `operational_failures`), 연구 가설의 **등록·승격 거버넌스**(`hypothesis_registry`, `promotion_gate_events`), Phase 8 파이프라인과 동일 CLI에 **관측 로그 연동**. 코크핏/UI·실행·포트폴리오·자동 연구 승격 **아님**.
- **상태 구분**: `success`, `warning`, `failed`, **`empty_valid`**(의도적 0출력 vs 깨짐 구분).
- **코드**: `src/observability/`, `src/research_registry/`, `src/db/records.py`(operational·registry 헬퍼).
- **CLI**: `smoke-phase9-observability`, `report-run-health`, `report-failures`, `report-research-registry`, `seed-phase9-research-samples`.
- **마이그레이션**: `20250412100000_phase9_observability_research_registry.sql` (Phase 8 이후). 미적용 원격 DB에서는 스모크가 `operational_runs` 부재로 실패할 수 있음.
- **증거**: `docs/phase9_evidence.md`, 샘플 디렉터리 `docs/phase9_samples/`.
- **진실성**: `src/message_contract/__init__.py` 의 `MESSAGE_LAYER_TRUTH_GUARDS` — 휴리스틱·결손·오버레이 `not_available_yet` 원칙 유지.

```bash
export PYTHONPATH=src
python3 src/main.py smoke-phase9-observability
python3 src/main.py seed-phase9-research-samples
python3 src/main.py build-outlier-casebook --universe sp500_current --candidate-limit 600
python3 src/main.py build-daily-signal-snapshot --universe sp500_current
python3 src/main.py report-daily-watchlist
python3 src/main.py report-run-health --limit 50
python3 src/main.py report-failures --limit 50
python3 src/main.py report-research-registry --limit 50
```

## Phase 10 목표 (프리미엄 오버레이 seam · 소스 권리 · 계보)

- **역할**: 공개 데이터 **결정적 스파인을 유지**한 채, 향후 선택적 프리미엄/독점/파트너 레이어를 **거짓 데이터 없이** 붙일 수 있는 **소스 레지스트리 + 어댑터 계약 + ROI 갭 보고**. 대규모 벤더 연동·코크핏·실행·가짜 프리미엄 데이터 **아님**.
- **저장소**: `data_source_registry`, `source_access_profiles`, `source_entitlements`, `source_coverage_profiles`, `source_rights_notes`, `source_overlay_availability`, `source_overlay_gap_reports` 등 (`20250413100000_phase10_source_registry_overlays.sql`).
- **코드**: `src/sources/` — `contracts`, `transcripts_adapter`, `estimates_adapter`, `price_quality_adapter`, `provenance`, `reporting`, `registry`.
- **다운스트림**: 케이스북·일일 워치리스트 행에 `overlay_awareness_json` 스냅샷; `PREMIUM_OVERLAY_SEAMS_DEFAULT`로 프리미엄 키 결손 명시.
- **CLI**: `seed-source-registry`, `report-source-registry`, `report-overlay-gap` (`--persist` 선택), `smoke-source-adapters`, `export-source-roi-matrix`.
- **증거**: `docs/phase10_evidence.md`.

```bash
export PYTHONPATH=src
python3 src/main.py smoke-source-adapters
python3 src/main.py export-source-roi-matrix
python3 src/main.py seed-source-registry
python3 src/main.py report-source-registry
python3 src/main.py report-overlay-gap
```

## Phase 11 목표 (단일 벤더 트랜스크립트 PoC — FMP)

- **역할**: Phase 10 오버레이 seam에 **실제 1경로**(Financial Modeling Prep `earning_call_transcript` v3)만 연결. `FMP_API_KEY` 없으면 **가짜 성공 없이** `not_configured` / `configuration_error` 감사. 공개 SEC/XBRL 스파인·점수 로직 **비변경**.
- **저장소**: `20250414100000_phase11_transcripts_fmp_poc.sql` + **11.1** `20250415100000_phase111_transcript_audit_pit.sql` (`raw_transcript_payloads_fmp_history`).
- **코드**: `src/sources/fmp_transcript_client.py`, `transcripts_provider_binding.py`, `transcripts_normalizer.py`, `transcripts_ingest.py`; 스캐너 `transcript_enrichment.py`(PIT-safe) + `daily_build`.
- **CLI**: `probe-transcripts-provider`, `ingest-transcripts-sample`, `report-transcripts-overlay-status`, (선택) `export-transcript-normalization-sample`.
- **증거**: `docs/phase11_evidence.md`.

```bash
export PYTHONPATH=src
# .env 에 FMP_API_KEY 설정 후 (없으면 exit≠0 및 operational_failures 에 사유)
python3 src/main.py probe-transcripts-provider
python3 src/main.py ingest-transcripts-sample --symbol AAPL --year 2020 --quarter 3
python3 src/main.py report-transcripts-overlay-status
python3 src/main.py export-transcript-normalization-sample --ticker AAPL
```

## Phase 12 목표 (공개 코어 full-cycle)

- **역할**: 프리미엄 없이 **state change → harness → memo → casebook → watchlist** 를 한 CLI로 실행하고 `docs/public_core_cycle/latest/` 에 요약 번들 기록. 빈 워치리스트는 실패로 취급하지 않음.
- **코드**: `src/public_core/cycle.py`
- **CLI**: `run-public-core-cycle`, `report-public-core-cycle`
- **증거**: `docs/phase12_evidence.md`

```bash
export PYTHONPATH=src
python3 src/main.py run-public-core-cycle --universe sp500_current
python3 src/main.py report-public-core-cycle
```

## Phase 13 목표 (공개 코어 품질 게이트 · 잔차 트리이지)

- **역할**: 사이클마다 **임계값 기반** 품질 등급(`strong` … `failed`), DB 증거(`public_core_cycle_quality_runs`), 케이스북 **잔차 버킷** + 프리미엄 ROI 힌트, 운영자 패킷에 **실행 성공 vs 실질 얇음** 구분.
- **코드**: `src/public_core/quality.py`, `src/casebook/residual_triage.py`, `src/public_core/cycle.py`
- **CLI**: `report-public-core-quality`, `export-public-core-quality-sample` (품질 행 조회·보내기)
- **증거**: `docs/phase13_evidence.md` · 마이그레이션 `20250416100000_phase13_public_core_quality.sql`

```bash
export PYTHONPATH=src
python3 src/main.py report-public-core-quality --limit 15
python3 src/main.py export-public-core-quality-sample --limit 10 --out docs/public_core_quality/samples/latest.json
```

## Phase 14 목표 (Research Engine Kernel)

- **역할**: 단일 프로그램·`next_quarter`·공개 데이터만으로 **가설 → 렌즈 리뷰(최대 2라운드) → 심판(kill/sandbox/candidate_recipe) → dossier**를 DB에 남김. Phase 13 품질·잔차를 소비하되 **스코어/워치리스트 비침투**.
- **코드**: `src/research_engine/`, `src/db/records.py`(Phase 14 CRUD)
- **CLI**: `smoke-phase14-research-engine`, `create-research-program`, `list-research-programs`, `generate-program-hypotheses`, `review-research-hypothesis`, `run-research-referee`, `report-research-program`, `export-research-dossier`
- **증거**: `docs/phase14_evidence.md` · 마이그레이션 `20250417100000_phase14_research_engine_kernel.sql`

```bash
export PYTHONPATH=src
python3 src/main.py smoke-phase14-research-engine
python3 src/main.py create-research-program --universe sp500_current
# YOUR_* 는 아래 list / report 출력의 실제 UUID 문자열로 교체. < > 꺾쇠는 쉘 리다이렉션이라 붙이지 말 것.
python3 src/main.py list-research-programs --limit 10
python3 src/main.py report-research-program --program-id PASTE_PROGRAM_UUID_HERE
python3 src/main.py generate-program-hypotheses --program-id PASTE_PROGRAM_UUID_HERE
python3 src/main.py review-research-hypothesis --hypothesis-id PASTE_HYPOTHESIS_UUID_HERE
python3 src/main.py run-research-referee --hypothesis-id PASTE_HYPOTHESIS_UUID_HERE
python3 src/main.py export-research-dossier --program-id PASTE_PROGRAM_UUID_HERE --out docs/research_engine/dossiers/latest.json
```

## Phase 15 목표 (Recipe Validation Lab)

- **역할**: Phase 14 `candidate_recipe`·`sandboxed` 가설을 **리뷰가 있는 경우에만** 공개 데이터(`factor_market_validation_panels`×`issuer_state_change_scores`, `next_quarter` excess)로 검증. 명시 베이스라인 3종(state_change / naive null / cap 역순위 프록시), 코호트·연도 슬라이스, **생존 판정**·**실패 사례**·스코어카드(JSON+Markdown). **프로덕션 스코어·워치리스트 비침투**(`state_change.runner`는 `research_validation` 미참조).
- **코드**: `src/research_validation/`, `src/db/records.py`(Phase 15 CRUD)
- **CLI**: `smoke-phase15-recipe-validation`, `run-recipe-validation`, `report-recipe-validation`, `compare-recipe-baselines`, `report-recipe-survivors`, `export-recipe-scorecard`
- **증거**: `docs/phase15_evidence.md` · 마이그레이션 `20250418100000_phase15_recipe_validation_lab.sql`

```bash
export PYTHONPATH=src
python3 src/main.py smoke-phase15-recipe-validation
# UUID는 Phase 14 절의 list / report 출력에서 복사. < > 사용 금지.
python3 src/main.py run-recipe-validation --hypothesis-id PASTE_HYPOTHESIS_UUID_HERE
python3 src/main.py report-recipe-validation --validation-run-id PASTE_VALIDATION_RUN_UUID_HERE
python3 src/main.py compare-recipe-baselines --hypothesis-id PASTE_HYPOTHESIS_UUID_HERE
python3 src/main.py report-recipe-survivors --limit 20
python3 src/main.py export-recipe-scorecard --hypothesis-id PASTE_HYPOTHESIS_UUID_HERE --out docs/research_validation/scorecards/latest.json
```

## Phase 16 목표 (Validation Campaign Orchestrator)

- **역할**: 한 연구 프로그램에 대해 **자격 있는 가설**만 모아 Phase 15 검증을 **재사용(`join_policy_version`·베이스라인·코호트 설정 일치)** 하거나 `reuse_or_run`/`force_rerun`으로 실행하고, 생존·실패·프리미엄 힌트를 **캠페인 단위로 집계**한 뒤 **단일 전략 권고**(`public_data_depth_first` \| `targeted_premium_seam_first` \| `insufficient_evidence_repeat_campaign`)를 DB·브리프(JSON+Markdown)로 남긴다. **제품 스코어 경로 비침투**(`state_change.runner`는 `validation_campaign` 미참조).
- **코드**: `src/validation_campaign/`, `src/db/records.py`(Phase 16 CRUD), Phase 15 `recipe_validation_runs.join_policy_version`·`quality_filter_json.join_policy_version` 호환 필드.
- **CLI**: `smoke-phase16-validation-campaign`, `list-eligible-validation-hypotheses`, `run-validation-campaign`, `report-validation-campaign`, `report-program-survival-distribution`, `export-validation-decision-brief`
- **증거**: `docs/phase16_evidence.md` · 마이그레이션 `20250419100000_phase16_validation_campaign.sql`

```bash
export PYTHONPATH=src
python3 src/main.py smoke-phase16-validation-campaign
python3 src/main.py list-eligible-validation-hypotheses --program-id PASTE_PROGRAM_UUID_HERE
python3 src/main.py run-validation-campaign --program-id PASTE_PROGRAM_UUID_HERE --run-mode reuse_or_run
python3 src/main.py report-validation-campaign --campaign-run-id PASTE_CAMPAIGN_RUN_UUID_HERE
python3 src/main.py report-program-survival-distribution --program-id PASTE_PROGRAM_UUID_HERE
python3 src/main.py export-validation-decision-brief --campaign-run-id PASTE_CAMPAIGN_RUN_UUID_HERE --out docs/validation_campaign/briefs/latest.json
```

## Phase 17 목표 (Public Substrate Depth & Quality Lift)

- **역할**: Phase 16 권고 `public_data_depth_first`에 맞춰 **공개 기판 두께·조인 가능성·품질 쉐어**를 유니버스 단위로 **결정적으로 측정**하고, 선택적 **전역 상한 빌드**(검증 패널·선행수익·유니버스 CIK factor) 후 **before/after·uplift**를 DB에 남긴다. **제품 스코어 경로 비침투**(`state_change.runner`는 `public_depth` 미참조).
- **코드**: `src/public_depth/`, `src/db/records.py`(Phase 17 CRUD).
- **CLI**: `list-universe-names`, `smoke-phase17-public-depth`, `run-public-depth-expansion`, `report-public-depth-coverage`, `report-quality-uplift`, `report-research-readiness`, `export-public-depth-brief`
- **증거**: `docs/phase17_evidence.md` · 마이그레이션 `20250420100000_phase17_public_depth.sql`

**`--universe` 값**: `YOUR_UNIVERSE_NAME` 은 예시 문구일 뿐 DB 키가 아닙니다. 표준 토큰은 `sp500_current`, `sp500_proxy_candidates_v1`, `combined_largecap_research_v1` 이며, **실제 멤버십이 있는 이름**은 `list-universe-names` 출력의 `use_for_phase17_cli`를 따르세요. `combined_largecap_research_v1`은 `universe_memberships`에 행이 없을 수 있어 Phase 17에서는 보통 `sp500_current`를 씁니다.

| 문자열 | 의미 |
|--------|------|
| `sp500_current` | `refresh-universe`로 채우는 S&P 500 현재 구성 |
| `sp500_proxy_candidates_v1` | `build-candidate-universe`로 채우는 비공식 후보군 |
| `combined_largecap_research_v1` | 검증용 합집합 슬라이스명(멤버십에 없을 수 있음) |

```bash
export PYTHONPATH=src
python3 src/main.py list-universe-names
python3 src/main.py smoke-phase17-public-depth
python3 src/main.py report-public-depth-coverage --universe sp500_current
python3 src/main.py run-public-depth-expansion --universe sp500_current --run-validation-panels --validation-panel-limit 2000
python3 src/main.py report-quality-uplift --before-report-id <UUID> --after-report-id <UUID>
python3 src/main.py report-research-readiness --program-id PASTE_PROGRAM_UUID_HERE
python3 src/main.py export-public-depth-brief --universe sp500_current --out docs/public_depth/briefs/latest.json
```

## Phase 18 목표 (Targeted Public Substrate Build-Out)

- **역할**: Phase 17 커버리지의 **우세 제외 사유**에 맞춰 **상한 있는** 수리(검증 패널·선행수익·유니버스 factor·state change)를 오케스트레이션하고, 액션 스냅샷·런·개선 리포트를 DB에 남긴다. **제품 스코어 경로 비침투**(`state_change.runner`는 `public_buildout` 미참조).
- **코드**: `src/public_buildout/`, `src/public_depth/diagnostics.py`(심볼 큐), `src/db/records.py`(Phase 18 CRUD).
- **CLI**: `smoke-phase18-public-buildout`, `report-public-exclusion-actions`, `run-targeted-public-buildout`, `report-buildout-improvement`, `report-revalidation-trigger`, `export-buildout-brief`
- **증거**: `docs/phase18_evidence.md` · **완료·클로징**: `docs/phase18_completion_report.md` · 마이그레이션 `20250421100000_phase18_public_buildout.sql`

```bash
export PYTHONPATH=src
python3 src/main.py smoke-phase18-public-buildout
python3 src/main.py report-public-exclusion-actions --universe sp500_current
python3 src/main.py run-targeted-public-buildout --universe sp500_current --dry-run
python3 src/main.py report-buildout-improvement --universe sp500_current --from-latest-pair --persist
python3 src/main.py report-buildout-improvement --before-report-id <UUID> --after-report-id <UUID>
python3 src/main.py report-revalidation-trigger --program-id PASTE_PROGRAM_UUID_HERE
python3 src/main.py export-buildout-brief --universe sp500_current --out docs/public_depth/briefs/buildout_latest.json
```

## Phase 19 목표 (Public Repair Campaign & Revalidation Loop)

- **역할**: Phase 17/18 진단·수리 이후 **재검증 게이트를 통과하면** Phase 16 캠페인을 `force_rerun`으로 돌리고, 전후 **생존 분포·캠페인 권고**를 비교한 뒤 **단일 최종 분기**(`continue_public_depth` \| `consider_targeted_premium_seam` \| `repair_insufficient_repeat_buildout`)를 DB에 남긴다. **제품 스코어 경로 비침투**(`state_change.runner`는 `public_repair_campaign` 미참조).
- **코드**: `src/public_repair_campaign/`, `src/db/records.py`(Phase 19 CRUD).
- **CLI**: `smoke-phase19-public-repair-campaign`, `run-public-repair-campaign`, `report-public-repair-campaign`, `compare-repair-revalidation-outcomes`, `export-public-repair-decision-brief`, `list-repair-campaigns`
- **증거**: `docs/phase19_evidence.md` · **완료·클로징**: `docs/phase19_completion_report.md` · 마이그레이션 `20250422100000_phase19_public_repair_campaign.sql`

```bash
export PYTHONPATH=src
python3 src/main.py smoke-phase19-public-repair-campaign
python3 src/main.py run-public-repair-campaign --program-id PASTE_PROGRAM_UUID_HERE --dry-run-buildout
python3 src/main.py list-repair-campaigns --program-id PASTE_PROGRAM_UUID_HERE
python3 src/main.py report-public-repair-campaign --repair-campaign-id PASTE_REPAIR_RUN_UUID_HERE
python3 src/main.py compare-repair-revalidation-outcomes --repair-campaign-id PASTE_REPAIR_RUN_UUID_HERE
python3 src/main.py export-public-repair-decision-brief --repair-campaign-id PASTE_REPAIR_RUN_UUID_HERE --out docs/public_repair/briefs/latest.json
```

## Phase 20 목표 (Repair Iteration Manager & Escalation Gate)

- **역할**: Phase 19 런을 **시리즈·멤버·트렌드 스냅샷**으로 누적하고, 결정적 플래토 로직으로 **`continue_public_depth` / `hold_and_repeat_public_repair` / `open_targeted_premium_discovery`** 중 하나를 내린다(프리미엄 **발견** 궤도만; 라이브 통합 아님). **`--program-id latest`**, **`--repair-campaign-id latest`** 등으로 골든 패스에서 UUID 추적을 줄인다. **제품 스코어 경로 비침투**(`public_repair_iteration` 미참조).
- **코드**: `src/public_repair_iteration/`, `src/db/records.py`(Phase 20 CRUD, `list_research_programs_for_universe`).
- **CLI**: `smoke-phase20-repair-iteration`, `run-public-repair-iteration`, `report-public-repair-iteration-history`, `report-public-repair-plateau`, `export-public-repair-escalation-brief`, `list-public-repair-series`, `report-latest-repair-state`, `report-premium-discovery-readiness`
- **증거**: `docs/phase20_evidence.md` · 마이그레이션 `20250423100000_phase20_repair_iteration.sql`
- **완료 보고(운영 클로징·검증 표)**: `docs/phase20_completion_report.md`

```bash
export PYTHONPATH=src
python3 src/main.py smoke-phase20-repair-iteration
python3 src/main.py run-public-repair-iteration --program-id latest --universe sp500_current
python3 src/main.py report-public-repair-plateau --program-id latest --universe sp500_current
python3 src/main.py export-public-repair-escalation-brief --program-id latest --universe sp500_current --out docs/public_repair/escalation_latest.json
```

## Phase 21 목표 (Iteration governance & selector completion)

- **역할**: 수리 루프 **선택자 완성**, 시리즈 **pause/resume/close**, 플래토 **인프라 실패 격리**(기본), **`advance-public-repair-series`** 골든 패스, 에스컬레이션 **브리프 v2**. 제품 스코어 경로 비침투 유지.
- **코드**: `src/public_repair_iteration/`(`infra_noise.py`, 확장 `resolver.py`·`service.py`), `src/db/records.py`, `src/main.py`(Phase 21 CLI).
- **CLI**: `smoke-phase21-iteration-governance`, `pause-public-repair-series`, `resume-public-repair-series`, `close-public-repair-series`, `advance-public-repair-series`, `resolve-repair-campaign-pair`; Phase 19 보고에 `latest-success` / `latest-compatible` / `latest-for-program` 등; `report-public-repair-plateau --include-infra-failed-runs`(옵션).
- **마이그레이션**: `20250424100000_phase21_iteration_governance.sql`
- **보고**: `docs/phase21_patch_report.md` · **핸드오프**: `HANDOFF.md`(상단 Phase 21)

```bash
export PYTHONPATH=src
python3 src/main.py smoke-phase21-iteration-governance
python3 src/main.py advance-public-repair-series --program-id latest --universe sp500_current --out docs/public_repair/advance_latest
```

## Full Universe Backfill — SQL 적용 이후 복붙 절차 (대표님용)

**목적**: 시장 가격만 넓고 SEC/XBRL/스냅샷/팩터/검증 스파인이 샘플 수준일 때, **수동 INSERT 없이** 기존 파이프라인을 순서대로 묶어 `issuer_master` → `factor_market_validation_panels` 까지 채움. **백테스트·포트폴리오·AI harness·UI 확장 아님.**

**전제**: Supabase에 `20250408100000_backfill_orchestration.sql` 적용. `universe_memberships`·`risk_free_rates_daily`·(가격) `silver_market_prices_daily` 등 선행 데이터는 기존 README 절차대로.

**모듈**: `src/backfill/` — `backfill_runner`, `universe_resolver`, `join_diagnostics`, `coverage_report`, `status_report`, `config/backfill_pilot_tickers_v1.json`(pilot 30종).

**CLI**: `smoke-backfill`, `backfill-universe`, `report-backfill-status`.

### (1) 현재 row count 확인 SQL (SQL Editor)

```sql
select 'issuer_master' as table_name, count(*) as rows from issuer_master
union all select 'filing_index', count(*) from filing_index
union all select 'raw_xbrl_facts', count(*) from raw_xbrl_facts
union all select 'silver_xbrl_facts', count(*) from silver_xbrl_facts
union all select 'issuer_quarter_snapshots', count(*) from issuer_quarter_snapshots
union all select 'issuer_quarter_factor_panels', count(*) from issuer_quarter_factor_panels
union all select 'forward_returns_daily_horizons', count(*) from forward_returns_daily_horizons
union all select 'factor_market_validation_panels', count(*) from factor_market_validation_panels
union all select 'state_change_candidates', count(*) from state_change_candidates;
```

```sql
select 'issuer_quarter_factor_panels' as table_name, count(distinct cik) as distinct_cik
from issuer_quarter_factor_panels
union all select 'factor_market_validation_panels', count(distinct cik) from factor_market_validation_panels
union all select 'state_change_candidates', count(distinct cik) from state_change_candidates;
```

### (2) smoke-backfill

```bash
cd ~/GenAIProacTrade
source .venv/bin/activate
export PYTHONPATH=src
python3 src/main.py smoke-backfill
```

### (3) pilot backfill (30종 근처, 유니버스와 교집합)

```bash
export PYTHONPATH=src
python3 src/main.py backfill-universe --mode pilot --universe sp500_current --dry-run
python3 src/main.py backfill-universe --mode pilot --universe sp500_current
```

### (4) pilot coverage report

```bash
python3 src/main.py report-backfill-status --mode pilot --universe sp500_current --output-json
python3 src/main.py report-backfill-status --mode pilot --universe sp500_current --write-diagnostics /tmp/join_diag.json
```

### (5) full backfill (캡 없이 유니버스 전체는 시간·SEC rate limit 큼; 먼저 `--symbol-limit` 권장)

```bash
python3 src/main.py backfill-universe --mode full --universe sp500_current --symbol-limit 120
# 멤버십 최신화 후:
python3 src/main.py refresh-universe --universe sp500_current
python3 src/main.py backfill-universe --mode full --universe sp500_current
```

### (6) validation panel row count 확인

```sql
select count(*) from factor_market_validation_panels;
```

### (7) thin coverage issuer (SQL 예시)

```sql
select cik, count(*) as factor_rows
from issuer_quarter_factor_panels
group by 1
having count(*) < 4
order by factor_rows asc
limit 100;
```

### (8) rerun Phase 5

```bash
python3 src/main.py run-factor-validation --universe sp500_current --horizon next_month
python3 src/main.py run-factor-validation --universe sp500_current --horizon next_quarter
```

### (9) rerun Phase 6

```bash
python3 src/main.py run-state-change --universe sp500_current --limit 500 --output-json
```

### (10) candidate / report 확인

```bash
python3 src/main.py report-state-change-summary --universe sp500_current
```

### (11)–(14) git

```bash
git status
git add -A
git commit -m "chore: add deterministic universe backfill orchestration"
git push origin main
```

### 한 번에 선행·검증까지 (옵션)

```bash
export PYTHONPATH=src
python3 src/main.py backfill-universe --mode pilot --universe sp500_current --rerun-phase5 --rerun-phase6
```

### 실패 티커만 재시도

이전 실행 `summary_json.retry_tickers_all` 에 티커가 있을 때:

```bash
python3 src/main.py backfill-universe --mode pilot --universe sp500_current \
  --retry-failed-only --from-orchestration-run-id <ORCH_UUID> \
  --start-stage sec --end-stage factors
```

### 스테이지 범위·dry-run

- `--start-stage` / `--end-stage`: `resolve` · `sec` · `xbrl` · `snapshots` · `factors` · `market_prices` · `forward_returns` · `validation_panel` · `phase5` · `phase6`
- `--dry-run`: resolve 메타만 DB에 남기고 이후 스테이지는 기록만 `skipped_dry_run`
- `phase5` / `phase6` 는 각각 `--rerun-phase5` / `--rerun-phase6` 가 있을 때만 실행
- **`--coverage-stage`**: `stage_a` · `stage_b` · `full` — 유니버스 심볼을 **티커 오름차순**으로 앞에서부터 고정 코호트(무작위 없음). 기본 목표: `stage_a`→150, `stage_b`→300, `full`→전체. `sp500_current`가 부족하면 `combined_largecap_research_v1`로 보강. 지정 시 SEC/스냅/팩터 한도는 **full**과 동일(`--mode full` 권장).
- `--issuer-target`: `coverage-stage`와 함께 목표 issuer 수.
- `--write-coverage-checkpoint PATH`: 백필 성공 시 커버리지 스냅샷 JSON 저장.

### 리스크

- **full** 모드는 SEC/네트워크·시간·Rate limit 부담이 큼. pilot·`--symbol-limit` 로 먼저 검증.
- `forward_returns` / `validation_panel` 은 DB에 있는 **모든** 팩터 패널(상한 `limit_panels`)을 순회; `fetch_factor_panels_all` 은 페이지네이션으로 대량 로드.

## Staged Coverage Expansion — SQL 적용 이후 복붙 절차 (대표님용)

**전제**: `20250408100000_backfill_orchestration.sql` RPC `backfill_coverage_counts` 적용. **수동 INSERT/CSV/placeholder 금지.** Phase 7·백테스트·대시보드 착수 아님.

**성공 기준(참고)** — Stage A: issuer≥150, 팩터 distinct CIK≥100, 검증 distinct≥80, state change scores≥250 등. Stage B: issuer≥300, 팩터 distinct≥200, 검증 distinct≥150, scores≥800 등.

### (1) 현재 row count 확인 SQL

```sql
select 'issuer_master' as table_name, count(*) as rows from issuer_master
union all
select 'issuer_quarter_snapshots', count(*) from issuer_quarter_snapshots
union all
select 'issuer_quarter_factor_panels', count(*) from issuer_quarter_factor_panels
union all
select 'forward_returns_daily_horizons', count(*) from forward_returns_daily_horizons
union all
select 'factor_market_validation_panels', count(*) from factor_market_validation_panels
union all
select 'issuer_state_change_scores', count(*) from issuer_state_change_scores
union all
select 'state_change_candidates', count(*) from state_change_candidates;
```

### (2) distinct issuer coverage

```sql
select 'issuer_quarter_factor_panels' as table_name, count(distinct cik) as distinct_cik from issuer_quarter_factor_panels
union all
select 'factor_market_validation_panels', count(distinct cik) from factor_market_validation_panels
union all
select 'issuer_state_change_scores', count(distinct cik) from issuer_state_change_scores;
```

### (3) thin coverage issuer (팩터 행 < 4)

```sql
select p.cik, m.ticker, count(*) as factor_rows
from issuer_quarter_factor_panels p
left join issuer_master m on m.cik = p.cik
group by p.cik, m.ticker
having count(*) < 4
order by factor_rows asc, m.ticker asc nulls last
limit 100;
```

### (4) 상위 state change 후보

`state_change_candidates`에는 합성 점수 컬럼이 없습니다. 점수는 `issuer_state_change_scores`를 보세요.

```sql
select ticker, as_of_date, candidate_class, confidence_band, candidate_rank
from state_change_candidates
order by as_of_date desc, candidate_rank asc
limit 50;
```

```sql
select ticker, as_of_date, state_change_score_v1, confidence_band, state_change_direction
from issuer_state_change_scores
order by as_of_date desc
limit 50;
```

### (5) Stage A 실행 (30 → ~150 issuer)

```bash
cd ~/GenAIProacTrade
source .venv/bin/activate
export PYTHONPATH=src
python3 src/main.py backfill-universe --mode full --universe sp500_current \
  --coverage-stage stage_a \
  --rerun-phase5 --rerun-phase6 \
  --write-coverage-checkpoint /tmp/coverage_checkpoint_stage_a.json
```

### (6) Stage A coverage report 확인

```bash
export PYTHONPATH=src
python3 src/main.py report-backfill-status --mode full --universe sp500_current \
  --coverage-stage stage_a \
  --include-coverage-checkpoint
```

### (7) thin issuer / join 진단 파일 저장

```bash
export PYTHONPATH=src
python3 src/main.py report-backfill-status --mode full --universe sp500_current \
  --coverage-stage stage_a \
  --include-sparse-diagnostics \
  --write-sparse-diagnostics /tmp/sparse_stage_a.json \
  --write-diagnostics /tmp/join_diag_stage_a.json
```

### (8) Stage B 실행 (~300 issuer)

```bash
export PYTHONPATH=src
python3 src/main.py backfill-universe --mode full --universe sp500_current \
  --coverage-stage stage_b \
  --rerun-phase5 --rerun-phase6 \
  --write-coverage-checkpoint /tmp/coverage_checkpoint_stage_b.json
```

### (9) Stage B coverage report 확인

```bash
export PYTHONPATH=src
python3 src/main.py report-backfill-status --mode full --universe sp500_current \
  --coverage-stage stage_b \
  --include-coverage-checkpoint \
  --include-sparse-diagnostics
```

### (10) Phase 5 / 6 단독 재실행 (백필에 이미 포함했으면 생략 가능)

```bash
export PYTHONPATH=src
python3 src/main.py run-factor-validation --universe sp500_current --horizon next_month
python3 src/main.py run-factor-validation --universe sp500_current --horizon next_quarter
python3 src/main.py run-state-change --universe sp500_current --limit 2000 --output-json
```

### (11) 요약 리포트

```bash
export PYTHONPATH=src
python3 src/main.py report-factor-summary
python3 src/main.py report-state-change-summary --universe sp500_current
```

### (12)–(14) git

```bash
git status
git add -A
git commit -m "chore: expand coverage from 30 to 300+ issuers"
git push origin main
```

**실패 티커만 재시도** (`retry_tickers_all`가 있을 때):

```bash
export PYTHONPATH=src
python3 src/main.py backfill-universe --mode full --universe sp500_current \
  --coverage-stage stage_b \
  --retry-failed-only --from-orchestration-run-id <ORCH_UUID> \
  --start-stage sec --end-stage factors
```

## Phase 3 목표

- **팩터 truth layer**: `issuer_quarter_snapshots` → `issuer_quarter_factor_panels` (가격 데이터 전 단계).
- **정의 고정**: `src/factors/definitions.py` 레지스트리 v1 (자동 팩터 생성기 없음).
- **공식 고정**: `src/factors/formulas.py` — README·`schema_notes`·코드 일치.
- **Prior 분기**: `src/factors/prior_period.py` — 동일 CIK·회계 분기 체인만 (거래일 정렬 없음).
- **설명 가능한 null**: `coverage_json` / `quality_flags_json`에 누락 필드·분모 0·prior 없음 등 기록.
- **감사**: `ingest_runs.run_type` = `sec_factor_panel_build`.

## Phase 3 팩터 공식 (v1)

| 팩터 | 공식 |
|------|------|
| `accruals` | `(net_income - operating_cash_flow) / average_total_assets` |
| `gross_profitability` | `gross_profit / average_total_assets` |
| `asset_growth` | `(total_assets_t - total_assets_t-1) / total_assets_t-1` (직전 **회계** 분기) |
| `capex_intensity` | `capex / average_total_assets` (**고정**. revenue 분모 미사용) |
| `rnd_intensity` | `research_and_development / revenue` (revenue 없으면 null, 대체 분모 없음) |
| `financial_strength_score` (컬럼) | `financial_strength_score_v1`: 이진 합산. 구성요소: `NI>0`, `OCF>0`, `OCF>=NI`, `gross_profitability>0`, `total_liabilities/total_assets` prior 대비 개선. 사용 가능한 항목만 `max_score_available`에 포함 (Piotroski 전체 아님). |

**average_total_assets** = `(total_assets_current + total_assets_prior) / 2`. prior 스냅샷 또는 prior `total_assets` 없으면 null.

## Prior period matching 정책

- `fiscal_period`를 대문자로 정규화한 뒤 **`Q1`–`Q4`, `FY`만** 직전 분기 링크를 지원한다 (`Q1` → 전년 `Q4`, …, `FY` → 전년 `FY`).
- `UNSPECIFIED` / `UNKNOWN` 등은 fiscal prior 없음 → prior 의존 팩터는 null + 플래그.
- 동일 `(fiscal_year, fiscal_period)`에 accession이 여러 개면 **`filed_at` 최신**을 대표 스냅샷으로 쓴다.

## Phase 2 목표

- **XBRL facts**: EdgarTools로 10-Q/10-K 등에서 fact 추출 → raw 보존 → silver 정규화(`canonical_concept`).
- **분기 스냅샷**: `issuer_quarter_snapshots`에 revenue / net_income / total_assets 등 **사실값만** 집계 (팩터 계산 없음).
- **매핑 v1**: `src/sec/facts/concept_map.py` — 대형 기술주에 흔한 us-gaap 태그 위주; 미매핑은 silver에 안 올라가고 `snapshot_json.missing_canonicals`에 기록.
- **감사**: `ingest_runs.run_type`으로 메타 ingest / facts 추출 / 스냅샷 빌드 구분.
- **Arelle**: 검증 **보조 경로**만 (`validate_xbrl_fact_presence` 등). 미설치 시 graceful skip.

## Phase 1 요약 (유지)

- Issuer·filing identity, 워치리스트 메타 ingest, 공시 raw/silver 멱등.

## 데이터 계층

| 계층 | 테이블 | 설명 |
|------|--------|------|
| Issuer identity | `issuer_master` | CIK 유니크, 티커는 관측값 |
| Filing identity | `filing_index` | `(cik, accession_no)` 유니크 |
| Raw filing meta | `raw_sec_filings` | 공시 메타 JSON, **불변** |
| Silver filing meta | `silver_sec_filings` | 정규화 요약, `revision_no` |
| Raw XBRL facts | `raw_xbrl_facts` | fact 원형, `(cik, accession, dedupe_key)` 유니크 |
| Silver XBRL facts | `silver_xbrl_facts` | canonical + `fact_period_key` + `revision_no` |
| Quarter snapshot | `issuer_quarter_snapshots` | `(cik, fiscal_year, fiscal_period, accession_no)` 유니크 |
| Factor panel | `issuer_quarter_factor_panels` | 스냅샷 기반 회계 팩터, `(cik, fy, fp, accession, factor_version)` 유니크 |
| Universe | `universe_memberships` | `sp500_current` / `sp500_proxy_candidates_v1` 등 |
| Symbol registry | `market_symbol_registry` | 심볼·CIK·거래소 메타 |
| Raw/Silver market | `raw_market_prices_daily`, `silver_market_prices_daily` | 시세 원문·정규화 |
| Market meta | `market_metadata_latest` | 시총·거래량 등(프로바이더가 줄 때만) |
| Risk-free | `risk_free_rates_daily` | 일별 연율화 무위험(%) |
| Forward returns | `forward_returns_daily_horizons` | 시그널일 기준 선행 raw/excess |
| Validation panel | `factor_market_validation_panels` | 팩터+시장 조인(검증용) |
| Validation research | `factor_validation_runs`, `factor_validation_summaries`, `factor_quantile_results`, `factor_coverage_reports` | Phase 5 기술 검증·분위·커버리지(전략 아님) |
| State change (Phase 6) | `state_change_runs`, `issuer_state_change_components`, `issuer_state_change_scores`, `state_change_candidates` | 조사 후보 스파인(실행 신호·선행라벨 feature 아님) |
| Backfill orchestration | `backfill_orchestration_runs`, `backfill_stage_events` | 유니버스 단위 파이프라인 오케스트레이션(수동 DB 입력 아님) |
| Audit | `ingest_runs` | 메타 / facts / 스냅샷 / factor_panel / **시장·검증** 등 |

상세 idempotency·run_type은 [`src/db/schema_notes.md`](src/db/schema_notes.md) 참고.

## Idempotency 정책 (한 줄 요약)

- **raw_sec_filings**: 동일 `(cik, accession_no)` 이미 있으면 insert 안 함.
- **filing_index**: 동일 키 upsert.
- **silver_sec_filings**: `(cik, accession, revision_no)` 동일하면 insert 안 함.
- **raw_xbrl_facts**: 동일 `dedupe_key`면 insert 안 함 (불변).
- **silver_xbrl_facts**: `(cik, accession, canonical, revision_no, fact_period_key)` 동일하면 insert 안 함.
- **issuer_quarter_snapshots**: 스냅샷 키 동일 시 upsert(갱신).
- **issuer_quarter_factor_panels**: 동일 `(cik, fiscal_year, fiscal_period, accession_no, factor_version)` 이면 **insert 생략** (행 UPDATE 없음, 멱등).
- **issuer_master**: CIK upsert.

## Coverage / quality flags (Phase 3)

- **`coverage_json`**: 팩터별 `formula_used`, `missing_fields`, `prior_snapshot_found`, 평균자산 세부 등.
- **`quality_flags_json`**: `flags` 전역 목록 + `by_factor` (예: `no_prior_snapshot`, `partial_inputs`, `zero_denominator`).
- **`factor_json`**: 팩터별 값·`financial_strength_score_v1`의 `components`·`max_score_available` 등 해석 메타.

## 사전 요구사항

- Python **3.9+**
- Supabase 프로젝트 + **service_role** 키
- `EDGAR_IDENTITY` (SEC 정책)

## 로컬 설정

```bash
cd /path/to/GenAIProacTrade
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
cp .env.example .env
```

`.env`에 실제 키를 넣고 **Git에 커밋하지 마세요.**

### hishel / `FileStorage` 오류

`requirements.txt`의 `hishel>=0.1.3,<1` 을 유지한 뒤 `python3 -m pip install -r requirements.txt` 로 맞춥니다.

## Supabase 마이그레이션 적용 순서

SQL Editor에서 아래를 **순서대로** 실행합니다.

1. `supabase/migrations/20250401000000_phase0_raw_silver_sec_filings.sql`
2. `supabase/migrations/20250402120000_phase1_issuer_filing_ingest_runs.sql`
3. `supabase/migrations/20250403100000_phase2_xbrl_facts_snapshots.sql`
4. `supabase/migrations/20250404100000_phase3_factor_panels.sql`
5. `supabase/migrations/20250405100000_phase4_market_validation.sql`
6. `supabase/migrations/20250406100000_phase5_factor_validation_research.sql`

## CLI (복붙용)

프로젝트 루트에서, 가상환경 활성화 후:

```bash
cd /path/to/GenAIProacTrade
source .venv/bin/activate
export PYTHONPATH=src
```

### 단일 티커 ingest

```bash
python3 src/main.py ingest-single --ticker NVDA
```

### 워치리스트 배치 ingest

기본 파일: `config/watchlist.json` (`tickers`, `filings_per_issuer`).

```bash
python3 src/main.py ingest-watchlist
```

다른 파일:

```bash
python3 src/main.py ingest-watchlist --watchlist /path/to/watchlist.json
```

환경변수 `WATCHLIST_PATH`로 기본 경로를 바꿀 수 있습니다. 티커 간 대기는 `--sleep` 또는 `INGEST_TICKER_SLEEP_SEC`.

`ingest_runs.run_type`은 **`sec_watchlist_metadata_ingest`** 로 기록됩니다.

### 스모크

```bash
python3 src/main.py smoke-sec
python3 src/main.py smoke-db
```

- `smoke-sec`: SEC에 접속 (네트워크 필요).
- `smoke-db`: Supabase `issuer_master`에 대한 단순 select.
- `smoke-facts`: `raw_xbrl_facts` 테이블 도달 + AAPL 등으로 XBRL fact 로드 프로브 (네트워크).
- `smoke-factors`: `issuer_quarter_factor_panels` 테이블 도달 + accruals 공식 sanity (DB·`.env` 필요, SEC 호출 없음).
- `smoke-market`: Phase 4 시장 테이블 도달 + 스텁 프로바이더 형태 (DB·`.env` 필요, 외부 호출 없음).
- `smoke-validation`: `factor_market_validation_panels` 테이블 도달 (DB·`.env`).
- `smoke-research`: Phase 5 `factor_validation_runs` 테이블 도달 (DB·마이그레이션·`.env`).

### Phase 4 시장·검증 (복붙 순서 예시)

**전제**: Phase 4 마이그레이션 적용, `.env` 설정, `export PYTHONPATH=src`.

```bash
cd /path/to/GenAIProacTrade
source .venv/bin/activate
export PYTHONPATH=src
```

**1) 스모크 (네트워크 없음, DB 필요)**

```bash
python3 src/main.py smoke-market
python3 src/main.py smoke-validation
```

**2) S&P 500 유니버스 갱신 (네트워크: 위키 + Yahoo 등)**

```bash
python3 src/main.py refresh-universe --universe sp500_current
```

**3) 프록시 후보 유니버스 (시드; 공식 후보 아님)**

```bash
python3 src/main.py build-candidate-universe
```

`build-candidate-universe` 는 **어디에 가입하는 것이 아니라**, `config/sp500_proxy_candidates_v1.json` 시드에서 **당시 `sp500_current` 에 이미 들어 있는 티커를 뺀 뒤** 남은 심볼만 `universe_memberships` 에 `candidate` 로 넣는다. 시드가 전부 S&P 구성이면 `candidate_count: 0` 이 되고 실패로 끝나니, JSON 심볼을 **지금 인덱스에 없는 티커**로 바꾸면 된다.

**4) 무위험 이자율 (FRED, 네트워크)**

다운로드는 **httpx**(긴 read 타임아웃) + **재시도**(`--fred-retries`, 기본 3). 행이 0이면 **`status: failed`**·exit code 1 (이전에는 completed 로 헷갈릴 수 있었음).

```bash
python3 src/main.py ingest-risk-free --lookback-years 3
```

느리거나 끊기면:

```bash
python3 src/main.py ingest-risk-free --lookback-years 1 --fred-timeout 600 --fred-retries 5
```

**7)·8) 전 보강 (복붙)** — `risk_free_rates_daily` 비어 있음 / `next_quarter` 실패 / 팩터 패널이 한 티커뿐일 때:

```bash
cd /path/to/GenAIProacTrade
source .venv/bin/activate
export PYTHONPATH=src
```

**액션 A — 무위험 적재(FRED)**

```bash
python3 src/main.py ingest-risk-free --lookback-years 1 --fred-timeout 600 --fred-retries 5
```

Supabase `risk_free_rates_daily` 행 수 확인. 회사 방화벽이 `fred.stlouisfed.org` 를 막으면 다른 네트워크/VPN에서 동일 명령.

**액션 B — 1분기(63거래일) 선행수익에 일봉 부족**

시그널일 이후 거래일이 충분히 쌓이도록 S&P 일봉 lookback 을 키운 뒤 선행·패널 재빌드:

```bash
python3 src/main.py ingest-market-prices --universe sp500_current --lookback-days 400
python3 src/main.py build-forward-returns --limit-panels 500
python3 src/main.py build-validation-panel --limit-panels 500
```

**액션 C — 팩터 패널 종목 수 늘리기 (Phase 3)**

워치리스트에 티커를 넣고 스냅샷·팩터까지 돌린 뒤 7)·8) 재실행:

```bash
python3 src/main.py compute-factors-watchlist
python3 src/main.py build-forward-returns --limit-panels 500
python3 src/main.py build-validation-panel --limit-panels 500
```

**5) 일봉 수집 (심볼 수 많음·시간 소요; 개발 시 `--start`/`--end` 또는 `MARKET_PRICE_LOOKBACK_DAYS`로 구간 축소)**

`sp500_proxy_candidates_v1` 은 **반드시 위 3) `build-candidate-universe` 를 먼저** 돌려 `universe_memberships` 에 행이 있어야 한다. (`refresh-universe` 만으로는 후보 유니버스가 생기지 않는다.)

```bash
python3 src/main.py ingest-market-prices --universe sp500_current --lookback-days 120
python3 src/main.py ingest-market-prices --universe sp500_proxy_candidates_v1 --lookback-days 120
```

**6) (선택) 메타 — Yahoo chart 전용 구현은 보통 빈 결과; 다른 프로바이더 붙이면 채워짐**

```bash
python3 src/main.py refresh-market-metadata --universe sp500_current
```

**7) 선행 수익률 → 검증 패널 (팩터 패널·스냅샷·가격·무위험이 갖춰져 있어야 함)**

```bash
python3 src/main.py build-forward-returns --limit-panels 500
python3 src/main.py build-validation-panel --limit-panels 500
```

**macOS에서 `refresh-universe`가 `SSL: CERTIFICATE_VERIFY_FAILED` 로 실패할 때**: `python3 -m pip install -r requirements.txt` 로 **`certifi`** 를 확보한 뒤 다시 실행한다(코드가 urllib TLS에 `certifi` 번들을 사용). 그래도 실패하면 python.org 설치본의 **Install Certificates.command** 실행을 고려.

**로컬/CI에서 외부 API 끄기**: `export MARKET_DATA_PROVIDER=stub` (유니버스 refresh는 스텁 목록만 적재).

### 회계 팩터 패널 (Phase 3)

`issuer_master`에 티커가 있고 `issuer_quarter_snapshots`에 행이 있어야 합니다.

#### Phase 3 실DB 확인 (액션별 복붙)

**전제**: Phase 3 마이그레이션 적용, 루트 `.env`에 Supabase 키, 해당 티커 CIK로 `issuer_quarter_snapshots`에 행이 있음.

**액션 1 — 프로젝트·가상환경·PYTHONPATH**

```bash
cd /Users/hyunminkim/GenAIProacTrade
source .venv/bin/activate
export PYTHONPATH=src
```

**액션 2 — `issuer_quarter_factor_panels` 테이블 도달 + accruals 공식 sanity (`smoke-factors`, SEC 호출 없음)**

```bash
python3 src/main.py smoke-factors
```

**액션 3 — 단일 티커로 패널 적재 (`compute-factors-single`, DB 쓰기)**

```bash
python3 src/main.py compute-factors-single --ticker AAPL
```

**액션 4 — (선택) 방금 적재된 패널 JSON으로 확인**

```bash
python3 src/main.py show-factor-panel --ticker AAPL --limit 5
```

한 줄로 2→3만 이어서:

```bash
cd /Users/hyunminkim/GenAIProacTrade && source .venv/bin/activate && export PYTHONPATH=src && python3 src/main.py smoke-factors && python3 src/main.py compute-factors-single --ticker AAPL
```

```bash
python3 src/main.py compute-factors-watchlist
python3 src/main.py compute-factors-watchlist --sleep 1.0
```

팩터 공식 버전 (기본 `v1`, 환경변수 `FACTOR_VERSION` 또는 `--factor-version`):

```bash
python3 src/main.py compute-factors-single --ticker AAPL --factor-version v1
```

최근 패널 조회:

```bash
python3 src/main.py show-factor-panel --ticker NVDA --limit 5
```

단일 티커·워치리스트 배치는 `ingest_runs.run_type` = **`sec_factor_panel_build`** 로 남습니다.

### XBRL facts 추출 (단일 티커)

최근 **10-Q → 10-K** 순으로 XBRL이 있는 첫 공시를 고른 뒤 fact 적재 + 분기 스냅샷 upsert.

```bash
python3 src/main.py extract-facts-single --ticker NVDA
```

form 우선순만 바꾸려면:

```bash
python3 src/main.py extract-facts-single --ticker AAPL --forms 10-Q
```

### XBRL facts 워치리스트 배치

```bash
python3 src/main.py extract-facts-watchlist
python3 src/main.py extract-facts-watchlist --sleep 1.0
```

### 분기 스냅샷 재계산 (DB silver 기준)

이미 적재된 `silver_xbrl_facts`로 `issuer_quarter_snapshots`만 다시 채웁니다.

```bash
python3 src/main.py build-quarter-snapshots
python3 src/main.py build-quarter-snapshots --ticker NVDA --limit 5
```

- **고유 공시 수집**: 한 accession의 silver 행이 매우 많아서, 예전 구현은 API 첫 페이지만 읽으면 **서로 다른 공시가 1건으로만 잡히는** 경우가 있었다. 지금은 페이지를 넘기며 `--limit`개의 **서로 다른 (cik, accession)** 까지 모은 뒤 스냅샷을 만든다.

## Canonical mapping v1 (지원 범위)

- 모듈: [`src/sec/facts/concept_map.py`](src/sec/facts/concept_map.py)
- 지원 canonical: `revenue`, `net_income`, `operating_cash_flow`, `total_assets`, `total_liabilities`, `cash_and_equivalents`, `research_and_development`, `capex`, `gross_profit`, `shares_outstanding`.
- us-gaap(및 일부 dei) 태그 문자열 **정확 일치** 매핑. extension taxonomy·별칭은 이번 단계에서 광범위 지원하지 않음.
- **한계**: 동일 태그·다른 context/차원이 압축되면 `dedupe_key`로 구분되나, 스냅샷은 DEI fiscal focus에 맞는 행을 우선 선택한다.

## Quarter snapshot 생성 방식

1. `dei:DocumentFiscalYearFocus` / `dei:DocumentFiscalPeriodFocus`로 primary 분기 결정 (없으면 revenue 등에서 fallback).
2. `silver_xbrl_facts` 중 primary에 맞는 duration/instant 행을 canonical별로 하나씩 선택.
3. `snapshot_json`에 `filled_canonicals` / `missing_canonicals` 기록.

## 로컬에서 실제 워치리스트 ingest 1회 + DB 확인 (복붙 절차)

**전제**: Supabase SQL Editor에서 Phase 0 → Phase 1 → Phase 2 → **Phase 3** 마이그레이션을 실행했고, 루트 `.env`에 `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `EDGAR_IDENTITY`가 채워져 있어야 합니다.

### 1) 터미널에서 한 번에 (macOS / zsh)

아래에서 첫 줄 `cd`만 본인 프로젝트 경로로 바꿉니다.

```bash
cd /Users/hyunminkim/GenAIProacTrade
source .venv/bin/activate
export PYTHONPATH=src
```

### 2) 연결 확인 (순서 권장)

```bash
python3 src/main.py smoke-sec
python3 src/main.py smoke-db
```

- `smoke-sec` 실패: 네트워크·`EDGAR_IDENTITY` 확인.
- `smoke-db` 실패: `.env`의 Supabase URL/키·마이그레이션(테이블 존재) 확인.

### 3) 워치리스트 ingest 1회 (실제 SEC 호출 + DB 적재)

```bash
python3 src/main.py ingest-watchlist
```

티커 사이에 더 쉬고 싶으면 (초 단위):

```bash
python3 src/main.py ingest-watchlist --sleep 1.0
```

종료 시 터미널에 JSON 요약이 출력됩니다. `ingest_runs`에 이번 run이 남고, 티커별로 issuer / filing_index / raw / silver가 쌓입니다.

### 4) Supabase에서 행 확인

**방법 A — Table Editor**: Dashboard → **Table Editor** → `ingest_runs`, `issuer_master`, `filing_index`, `raw_sec_filings`, `silver_sec_filings` 순으로 열어 최근 행 확인.

**방법 B — SQL Editor**에서 아래를 붙여넣어 실행:

```sql
-- 최근 ingest run
select id, run_type, status, target_count, success_count, failure_count, started_at, completed_at
from ingest_runs
order by started_at desc
limit 5;

-- 건수 요약
select (select count(*) from issuer_master) as issuer_master_rows,
       (select count(*) from filing_index) as filing_index_rows,
       (select count(*) from raw_sec_filings) as raw_rows,
       (select count(*) from silver_sec_filings) as silver_rows;
```

Phase 2·3 테이블 건수 확인 예:

```sql
select (select count(*) from raw_xbrl_facts) as raw_xbrl,
       (select count(*) from silver_xbrl_facts) as silver_xbrl,
       (select count(*) from issuer_quarter_snapshots) as quarter_snapshots,
       (select count(*) from issuer_quarter_factor_panels) as factor_panels;
```

같은 명령을 다시 실행해도 **멱등** 정책상 raw/silver가 무한히 늘지 않고, issuer·filing_index는 upsert·갱신 위주입니다. 상세는 [`src/db/schema_notes.md`](src/db/schema_notes.md) 참고.

## 워치리스트 파일 형식

`config/watchlist.json` 예:

```json
{
  "tickers": ["NVDA", "MSFT", "AAPL"],
  "filings_per_issuer": 1
}
```

## Optional Arelle 검증 경로 (validation assist)

- 모듈: [`src/sec/validation/arelle_check.py`](src/sec/validation/arelle_check.py)
- 미설치 시 `validate_filing_identity`, `validate_xbrl_fact_presence`, `compare_statement_concept_presence` 등은 `status: skipped`.
- 설치되어 있어도 Phase 2는 **전체 인스턴스 대조·문장 단위 parity까지는 구현하지 않음** (`arelle_assist_pending` 등).

## 테스트

```bash
cd /path/to/GenAIProacTrade
source .venv/bin/activate
pytest
```

외부 네트워크 없이 mock 위주입니다.

## 환경변수

| 변수 | 필수 | 설명 |
|------|------|------|
| `SUPABASE_URL` | 예 | 프로젝트 URL |
| `SUPABASE_SERVICE_ROLE_KEY` | 예 | service role |
| `EDGAR_IDENTITY` | 예 | SEC 식별 |
| `WATCHLIST_PATH` | 아니오 | 워치리스트 JSON 경로 |
| `INGEST_TICKER_SLEEP_SEC` | 아니오 | 배치 티커 간 sleep (초) |
| `FACTOR_VERSION` | 아니오 | 팩터 패널 공식 버전 (기본 `v1`) |
| `OPENAI_API_KEY` | 아니오 | 예약 |
| `SENTRY_DSN` | 아니오 | 예약 |

## 프로젝트 구조 (요약)

```
config/watchlist.json
supabase/migrations/
src/
  main.py              # CLI 서브커맨드
  config.py
  watchlist_config.py
  db/
  factors/            # definitions, formulas, prior_period, panel_build
  sec/
    facts/              # concept_map, extract, normalize, pipeline
    ingest_pipeline.py
    ingest_company_sample.py
    watchlist_ingest.py
    facts_watchlist.py
    snapshot_build_run.py
    validation/arelle_check.py
  models/
  tests/
```

## 운영 문서

제품 스펙 → Cursor Agent Protocol → Plan Mode Roadmap → Phase Work Order 순으로 상위 문서를 우선합니다.
