# Phase 47 runtime — 배포 노트

## 로컬 실행 (필수 경로)

저장소 루트에서:

```bash
export PYTHONPATH=src
python3 src/phase47_runtime/app.py
```

기본값:

- 바인딩: `127.0.0.1:8765`
- Phase 46 번들: `docs/operator_closeout/phase46_founder_decision_cockpit_bundle.json`
- 레저: 번들의 `alert_ledger_path` / `decision_trace_ledger_path` (없으면 `data/product_surface/*.json`)

브라우저: `http://127.0.0.1:8765`

## 환경 변수

| 변수 | 의미 |
|------|------|
| `PHASE47_HOST` | 기본 `127.0.0.1` |
| `PHASE47_PORT` | 기본 `8765` |
| `PHASE47_PHASE46_BUNDLE` | Phase 46 번들 경로 |
| `PHASE47_REPO_ROOT` | 레포 루트 (기본: `src/`의 부모) |

## 정적 자산

- `src/phase47_runtime/static/index.html`
- `src/phase47_runtime/static/app.js`

`app.py`가 동일 프로세스에서 서빙한다. 별도 프론트 빌드 없음.

## 내부 URL 배포 (권장 형태)

1. **호스트**에서 venv + 위 명령을 **systemd** 또는 **supervisor**로 상시 실행.
2. **nginx** 등 리버스 프록시에서 `https://cockpit.internal.example/` → `127.0.0.1:8765` 프록시.
3. MVP는 **인증 없음** — VPN·사설망 뒤에만 두거나, 향후 audit·auth 지시(예: 메타 번들의 외부 커넥터·감사 로그 스텁)를 따른다. 선행 연구 단일 사이클 **Phase 48** 은 **클로즈**(`docs/operator_closeout/phase48_closeout.md`); 스케줄 반복은 **Phase 49** CLI 참고.

## Fly.io / Render 등 (예시)

- **단일 프로세스 웹** 컨테이너에 동일 엔트리포인트 사용.
- `PHASE47_HOST=0.0.0.0` 로 수신 (플랫폼이 포트 노출).
- 영속 디스크 또는 볼륨에 `data/product_surface/` 와 `docs/operator_closeout/phase46_*.json` 을 마운트하지 않으면 레저·번들이 컨테이너 로컬에만 남는다. **운영 시 볼륨 권장.**

## 레저 쓰기

UI 및 API는 다음 파일에 **추가/갱신**한다.

- `alert_ledger_v1.json` — 상태: `acknowledge` / `resolve` / `supersede` / `dismiss`
- `decision_trace_ledger_v1.json` — `append_decision` (hold, watch, defer, reopen_request, buy, sell, dismiss_alert)

## 번들 갱신

Phase 46 번들을 재생성한 뒤 런타임 상단 **Reload bundle** 또는 `POST /api/reload` 로 메모리 상태를 갱신한다. `GET /api/meta` 의 `bundle_stale` 로 디스크에 더 새 파일이 있는지 표시한다.
