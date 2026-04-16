# Slice A — 터미널만으로 끝내기 (복붙용)

## 지금 터미널에 나온 에러가 의미하는 것

`no passing promotion gate for artifact 'art_short_demo_v0'` 는 **DB에서 만든 promotion_gate가 세 칸 모두 false**라서, 제품 규칙상 **active 레지스트리에 올릴 수 없다**는 뜻입니다.  
당신 로그의 `valid_factor_count: 0`, `factor_quantile_rows: 0` 이 그 원인입니다(팩터 값이 거의 없거나 패널/조인이 비어 있음).

이건 CLI 버그가 아니라 **데이터/검증 run 상태** 문제입니다. 먼저 검증을 다시 쌓거나, 요약이 살아 있는 팩터·유니버스로 바꿔야 합니다.

---

## 1) 설정 JSON을 “에디터 없이” 만드는 방법 (복붙)

터미널에 아래 **한 블록**을 그대로 붙여넣으면 `my_metis_bundle_build.json` 이 생성됩니다.

```bash
cd /Users/hyunminkim/GenAIProacTrade
cat <<'EOF' > data/mvp/my_metis_bundle_build.json
{
  "schema_version": 1,
  "contract": "METIS_BUNDLE_FROM_VALIDATION_CONFIG_V0",
  "template_bundle_path": "data/mvp/metis_brain_bundle_v0.json",
  "output_bundle_path": "data/mvp/metis_brain_bundle_from_db_v0.json",
  "sync_artifact_validation_pointer": true,
  "gates": [
    {
      "factor_name": "accruals",
      "universe_name": "sp500_current",
      "horizon_type": "next_month",
      "return_basis": "raw",
      "artifact_id": "art_short_demo_v0"
    }
  ]
}
EOF
```

### 각 줄이 하는 일 (한 줄씩만 기억)

| 키 | 의미 |
|----|------|
| `template_bundle_path` | **손대지 않을 원본** 번들 (보통 저장소의 `metis_brain_bundle_v0.json`). |
| `output_bundle_path` | **결과를 새로 쓸 파일**. 템플릿과 **다른 경로**로 두는 것이 안전합니다. |
| `sync_artifact_validation_pointer` | `true`면 병합 후 해당 `artifact_id`의 `validation_pointer`를 DB run id로 맞춤. |
| `gates[]` 한 개 | “이 DB 조합으로 뽑은 게이트를 **이 artifact_id**에 붙인다”는 뜻. `artifact_id`는 **템플릿 번들 안에 있는** `artifacts[].artifact_id`와 같아야 합니다. |

`gates`에 **여러 줄**을 넣고 싶으면 JSON 배열 안에 객체를 `}, {` 로 이어 붙이면 됩니다(형식은 예시 파일 `data/mvp/metis_bundle_from_validation_config.example.json` 과 동일).

---

## 2) 공통 프리픽스 (매번 위에 붙이기)

```bash
cd /Users/hyunminkim/GenAIProacTrade
export PYTHONPATH=src
```

---

## 3) DB 요약이 살아 있는지 먼저 확인 (같은 조건으로)

```bash
cd /Users/hyunminkim/GenAIProacTrade
export PYTHONPATH=src
python3 src/main.py report-factor-summary --factor accruals --universe sp500_current --horizon next_month --return-basis raw
```

여기서 표본·상관이 비어 있으면, 아래 4)로 검증을 다시 돌리는 쪽이 먼저입니다.

---

## 4) 검증 run 다시 쌓기 (패널·팩터가 있을 때)

```bash
cd /Users/hyunminkim/GenAIProacTrade
export PYTHONPATH=src
python3 src/main.py run-factor-validation --universe sp500_current --horizon next_month --panel-limit 8000 --winsorize --ols
```

(시간이 걸릴 수 있습니다. 끝난 뒤 3)을 다시 실행해 보세요.)

---

## 5) 게이트 JSON만 단독으로 뽑아서 눈으로 확인

```bash
cd /Users/hyunminkim/GenAIProacTrade
export PYTHONPATH=src
python3 src/main.py export-metis-gates-from-factor-validation \
  --factor accruals \
  --universe sp500_current \
  --horizon next_month \
  --return-basis raw \
  --artifact-id art_short_demo_v0 \
| tee /Users/hyunminkim/GenAIProacTrade/data/mvp/last_gate_export.json
```

`promotion_gate` 안에 `pit_pass` / `coverage_pass` / `monotonicity_pass` 가 **전부 true**가 아니면, **6) 빌드는 의도적으로 실패**합니다.

---

## 6) Slice A 빌드 (드라이런 → 통과 시 본 실행)

드라이런:

```bash
cd /Users/hyunminkim/GenAIProacTrade
export PYTHONPATH=src
python3 src/main.py build-metis-brain-bundle-from-factor-validation \
  --repo-root /Users/hyunminkim/GenAIProacTrade \
  --config /Users/hyunminkim/GenAIProacTrade/data/mvp/my_metis_bundle_build.json \
  --dry-run
```

마지막 JSON에 `"ok": true` 일 때만 디스크에 쓰기:

```bash
cd /Users/hyunminkim/GenAIProacTrade
export PYTHONPATH=src
python3 src/main.py build-metis-brain-bundle-from-factor-validation \
  --repo-root /Users/hyunminkim/GenAIProacTrade \
  --config /Users/hyunminkim/GenAIProacTrade/data/mvp/my_metis_bundle_build.json
```

---

## 7) Today가 새 번들을 쓰게 하려면 (선택)

기본 경로는 `data/mvp/metis_brain_bundle_v0.json` 입니다. 빌드 결과를 그 이름으로 쓰고 싶지 않으면:

```bash
export METIS_BRAIN_BUNDLE=/Users/hyunminkim/GenAIProacTrade/data/mvp/metis_brain_bundle_from_db_v0.json
```

런타임/다음 `validate-metis-brain-bundle` 전에 이 환경 변수를 켠 터미널에서 실행하면 됩니다.
