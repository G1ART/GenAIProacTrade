"""CLI: ingest, facts extract, quarter snapshots, smoke."""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any

from config import ensure_edgar_local_cache, load_settings
from logging_utils import configure_logging

ensure_edgar_local_cache()

_UUID_HINT_KO = (
    "README의 YOUR_*_UUID 는 예시입니다. list-research-programs 출력의 실제 id로 바꾸세요. "
    "쉘에서 < 또는 > 는 리다이렉션이므로 '<UUID>' 같은 꺾쇠 문구를 붙여넣지 마세요."
)


def _exit_unless_uuid(
    field: str,
    value: str | None,
    *,
    optional: bool = False,
) -> int | None:
    """
    PostgREST에 잘못된 UUID가 넘어가며 터지는 것을 막는다.
    반환: None 이면 통과, int 이면 그 exit code 로 종료해야 함.
    """
    if optional and (value is None or str(value).strip() == ""):
        return None
    raw = str(value).strip() if value is not None else ""
    if not raw:
        print(
            json.dumps(
                {"ok": False, "error": "empty_uuid_field", "field": field},
                indent=2,
                ensure_ascii=False,
            )
        )
        return 1
    try:
        uuid.UUID(raw)
    except ValueError:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "invalid_uuid",
                    "field": field,
                    "value_preview": raw[:96],
                    "hint": _UUID_HINT_KO,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 1
    return None


def _resolve_program_id_cli(client: Any, args: argparse.Namespace) -> tuple[str | None, int | None]:
    """`--program-id latest` 또는 명시 UUID. 실패 시 (None, exit_code)."""
    import json as json_lib

    from public_repair_iteration.resolver import resolve_program_id

    raw = str(getattr(args, "program_id", "") or "").strip()
    uni = getattr(args, "universe", None)
    out = resolve_program_id(client, raw, universe_name=uni if uni else None)
    if not out.get("ok"):
        print(json_lib.dumps(out, indent=2, ensure_ascii=False))
        return None, 1
    return str(out["program_id"]), None


def _resolve_repair_campaign_id_cli(
    client: Any,
    args: argparse.Namespace,
    *,
    latest_success: bool = False,
    series_row: dict[str, Any] | None = None,
) -> tuple[str | None, int | None]:
    import json as json_lib
    import uuid as uuid_lib

    from public_repair_iteration.constants import SELECTOR_FROM_LATEST_PAIR
    from public_repair_iteration.resolver import (
        repair_campaign_selector_token,
        resolve_repair_campaign_run_id,
    )

    rid_raw = str(getattr(args, "repair_campaign_id", "") or "").strip()
    try:
        uuid_lib.UUID(rid_raw)
        bad = _exit_unless_uuid("repair_campaign_id", rid_raw)
        if bad is not None:
            return None, bad
        return rid_raw, None
    except ValueError:
        pass

    tok = repair_campaign_selector_token(rid_raw)
    if tok is None:
        print(
            json_lib.dumps(
                {
                    "ok": False,
                    "error": "invalid_repair_campaign_id_or_selector",
                    "value_preview": rid_raw[:96],
                    "hint": "UUID 또는 latest, latest-success, latest-compatible, latest-for-program 등",
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return None, 1
    if tok == SELECTOR_FROM_LATEST_PAIR:
        print(
            json_lib.dumps(
                {
                    "ok": False,
                    "error": "from_latest_pair_is_not_a_single_run_selector",
                    "hint": "API: resolve_repair_campaign_latest_pair() 또는 전용 CLI를 사용하세요.",
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return None, 1
    if not getattr(args, "program_id", None):
        print(
            json_lib.dumps(
                {
                    "ok": False,
                    "error": "program_id_required_with_repair_campaign_selector",
                    "selector": tok,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return None, 1
    pid, err = _resolve_program_id_cli(client, args)
    if err is not None:
        return None, err
    ser = series_row
    if tok == "latest-compatible" and ser is None:
        from public_repair_iteration.service import resolve_active_series_for_program

        aser = resolve_active_series_for_program(client, program_id=str(pid))
        if not aser.get("ok"):
            print(json_lib.dumps(aser, indent=2, ensure_ascii=False))
            return None, 1
        ser = aser.get("series")
    rc = resolve_repair_campaign_run_id(
        client,
        rid_raw,
        program_id=str(pid),
        latest_success=latest_success,
        series=ser,
    )
    if not rc.get("ok"):
        print(json_lib.dumps(rc, indent=2, ensure_ascii=False))
        return None, 1
    return str(rc["repair_campaign_run_id"]), None


def _cmd_ingest_single(args: argparse.Namespace) -> int:
    from sec.ingest_company_sample import run_sample_ingest

    settings = load_settings()
    configure_logging()
    result = run_sample_ingest(args.ticker, settings)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def _cmd_ingest_watchlist(args: argparse.Namespace) -> int:
    from sec.watchlist_ingest import run_watchlist_ingest

    settings = load_settings()
    configure_logging()
    path: Path | None = None
    if args.watchlist:
        path = Path(args.watchlist).expanduser()
    elif os.getenv("WATCHLIST_PATH"):
        path = Path(os.environ["WATCHLIST_PATH"]).expanduser()
    result = run_watchlist_ingest(
        settings,
        watchlist_path=path,
        sleep_seconds=args.sleep,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("status") != "failed" else 1


def _cmd_smoke_sec(_args: argparse.Namespace) -> int:
    """SEC에 최소 1회 접속 가능한지 확인 (네트워크 필요)."""
    import sec.ingest_company_sample  # noqa: F401 — 모듈 로드 시 edgar 캐시 부트스트랩

    from edgar import Company, set_identity

    settings = load_settings()
    configure_logging()
    set_identity(settings.edgar_identity)
    c = Company("AAPL")
    out = {"ok": True, "sample_cik": str(getattr(c, "cik", ""))}
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


def _cmd_smoke_db(_args: argparse.Namespace) -> int:
    from db.client import get_supabase_client
    from db.records import smoke_db_select_one

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    smoke_db_select_one(client)
    print(json.dumps({"ok": True, "supabase": "reachable"}, indent=2, ensure_ascii=False))
    return 0


def _cmd_extract_facts_single(args: argparse.Namespace) -> int:
    from db.client import get_supabase_client
    from sec.facts.facts_pipeline import run_facts_extract_for_ticker

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    forms = tuple(args.forms.split(",")) if args.forms else ("10-Q", "10-K")
    out = run_facts_extract_for_ticker(
        client,
        settings,
        args.ticker,
        forms=forms,
        run_validation_hook=True,
    )
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0 if out.get("ok") else 1


def _cmd_extract_facts_watchlist(args: argparse.Namespace) -> int:
    from sec.facts_watchlist import run_facts_watchlist

    settings = load_settings()
    configure_logging()
    path: Path | None = None
    if args.watchlist:
        path = Path(args.watchlist).expanduser()
    elif os.getenv("WATCHLIST_PATH"):
        path = Path(os.environ["WATCHLIST_PATH"]).expanduser()
    forms = tuple(args.forms.split(",")) if args.forms else ("10-Q", "10-K")
    out = run_facts_watchlist(
        settings,
        watchlist_path=path,
        sleep_seconds=args.sleep,
        forms=forms,
    )
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0 if out.get("status") != "failed" else 1


def _cmd_build_quarter_snapshots(args: argparse.Namespace) -> int:
    from sec.snapshot_build_run import run_quarter_snapshot_build

    settings = load_settings()
    configure_logging()
    out = run_quarter_snapshot_build(
        settings,
        ticker=args.ticker,
        limit=args.limit,
    )
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0 if out.get("status") != "failed" else 1


def _cmd_compute_factors_single(args: argparse.Namespace) -> int:
    from factors.panel_build import run_factor_panels_for_ticker

    settings = load_settings()
    configure_logging()
    fv = args.factor_version or os.environ.get("FACTOR_VERSION", "v1")
    out = run_factor_panels_for_ticker(settings, args.ticker, factor_version=fv)
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0 if out.get("ok") else 1


def _cmd_compute_factors_watchlist(args: argparse.Namespace) -> int:
    from pathlib import Path

    from factors.panel_build import run_factor_panels_watchlist
    from watchlist_config import default_watchlist_path, load_watchlist

    settings = load_settings()
    configure_logging()
    path: Path | None = None
    if args.watchlist:
        path = Path(args.watchlist).expanduser()
    elif os.getenv("WATCHLIST_PATH"):
        path = Path(os.environ["WATCHLIST_PATH"]).expanduser()
    tickers, _ = load_watchlist(path)
    fv = args.factor_version or os.environ.get("FACTOR_VERSION", "v1")
    out = run_factor_panels_watchlist(
        settings,
        tickers=tickers,
        sleep_seconds=args.sleep,
        factor_version=fv,
    )
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0 if out.get("status") != "failed" else 1


def _cmd_smoke_factors_phase3(_args: argparse.Namespace) -> int:
    """factor_panels 테이블 + 공식 sanity (네트워크 없음)."""
    from db.client import get_supabase_client
    from db.records import smoke_factor_panels_db
    from factors.formulas import compute_accruals

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    smoke_factor_panels_db(client)
    cur = {"net_income": 100.0, "operating_cash_flow": 40.0, "total_assets": 200.0}
    prior = {"total_assets": 100.0}
    val, _cov, _qf = compute_accruals(cur, prior)
    out = {
        "db_factor_panels_table": "ok",
        "formula_sanity_accruals": val,
        "expected_accruals_rough": (100 - 40) / ((200 + 100) / 2),
    }
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0


def _cmd_show_factor_panel(args: argparse.Namespace) -> int:
    from db.client import get_supabase_client
    from db.records import fetch_cik_for_ticker, fetch_factor_panels_for_cik

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    cik = fetch_cik_for_ticker(client, ticker=args.ticker.upper().strip())
    if not cik:
        print(json.dumps({"error": "issuer_not_found"}, indent=2))
        return 1
    rows = fetch_factor_panels_for_cik(client, cik=cik, limit=args.limit)
    print(json.dumps({"cik": cik, "ticker": args.ticker.upper().strip(), "panels": rows}, indent=2, ensure_ascii=False, default=str))
    return 0


def _cmd_refresh_universe(args: argparse.Namespace) -> int:
    from market.run_types import UNIVERSE_SP500_CURRENT
    from market.universe_refresh import run_universe_refresh_sp500

    settings = load_settings()
    configure_logging()
    u = (args.universe or UNIVERSE_SP500_CURRENT).strip()
    if u != UNIVERSE_SP500_CURRENT:
        print(json.dumps({"error": "unsupported_universe", "universe": u}, indent=2))
        return 1
    out = run_universe_refresh_sp500(settings)
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0 if out.get("status") == "completed" else 1


def _cmd_build_candidate_universe(args: argparse.Namespace) -> int:
    from pathlib import Path

    from market.candidate_universe_build import run_build_candidate_universe

    settings = load_settings()
    configure_logging()
    seed = Path(args.seed).expanduser() if args.seed else None
    out = run_build_candidate_universe(settings, seed_path=seed)
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0 if out.get("status") == "completed" else 1


def _cmd_ingest_market_prices(args: argparse.Namespace) -> int:
    from datetime import date

    from market.price_ingest import run_market_prices_ingest

    settings = load_settings()
    configure_logging()
    start = date.fromisoformat(args.start) if args.start else None
    end = date.fromisoformat(args.end) if args.end else None
    out = run_market_prices_ingest(
        settings,
        universe_name=args.universe.strip(),
        start_date=start,
        end_date=end,
        lookback_days=int(args.lookback_days),
    )
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0 if out.get("status") == "completed" else 1


def _cmd_refresh_market_metadata(args: argparse.Namespace) -> int:
    from market.price_ingest import run_market_metadata_refresh

    settings = load_settings()
    configure_logging()
    out = run_market_metadata_refresh(settings, universe_name=args.universe.strip())
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0 if out.get("status") == "completed" else 1


def _cmd_ingest_risk_free(args: argparse.Namespace) -> int:
    from datetime import date

    from market.risk_free_ingest import run_risk_free_ingest

    settings = load_settings()
    configure_logging()
    start = date.fromisoformat(args.start) if args.start else None
    end = date.fromisoformat(args.end) if args.end else None
    out = run_risk_free_ingest(
        settings,
        start_date=start,
        end_date=end,
        lookback_years=int(args.lookback_years),
        fred_http_timeout_sec=int(args.fred_timeout),
        fred_retries=int(args.fred_retries),
    )
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0 if out.get("status") == "completed" else 1


def _cmd_build_forward_returns(args: argparse.Namespace) -> int:
    from market.forward_returns_run import run_forward_returns_build

    settings = load_settings()
    configure_logging()
    out = run_forward_returns_build(
        settings,
        limit_panels=int(args.limit_panels),
        price_lookahead_days=int(args.price_lookahead_days),
    )
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0 if out.get("status") == "completed" else 1


def _cmd_build_validation_panel(args: argparse.Namespace) -> int:
    from market.validation_panel_run import run_validation_panel_build

    settings = load_settings()
    configure_logging()
    out = run_validation_panel_build(settings, limit_panels=int(args.limit_panels))
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0 if out.get("status") == "completed" else 1


def _cmd_smoke_market(_args: argparse.Namespace) -> int:
    from db.client import get_supabase_client
    from market.smoke_market import run_smoke_market

    settings = load_settings()
    configure_logging()
    out = run_smoke_market(settings)
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0


def _cmd_smoke_validation(_args: argparse.Namespace) -> int:
    from market.smoke_market import run_smoke_validation

    settings = load_settings()
    configure_logging()
    out = run_smoke_validation(settings)
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0


def _cmd_run_factor_validation(args: argparse.Namespace) -> int:
    from db.client import get_supabase_client
    from research.validation_runner import run_factor_validation_research

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    out = run_factor_validation_research(
        client,
        universe_name=str(args.universe),
        horizon_type=str(args.horizon),
        factor_version=str(args.factor_version or "v1"),
        panel_limit=int(args.panel_limit),
        include_ols=bool(args.ols),
        apply_winsorize=bool(args.winsorize),
        n_quantiles=int(args.n_quantiles),
    )
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0 if out.get("status") == "completed" else 1


def _cmd_report_factor_summary(args: argparse.Namespace) -> int:
    from db.client import get_supabase_client
    from research.cli_report import print_factor_summary_cli

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    return print_factor_summary_cli(
        client,
        factor_name=str(args.factor),
        universe_name=str(args.universe),
        horizon_type=str(args.horizon),
        return_basis=str(args.return_basis or "raw"),
    )


def _cmd_smoke_research(_args: argparse.Namespace) -> int:
    from db.client import get_supabase_client
    from db.records import smoke_research_tables

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    smoke_research_tables(client)
    print(json.dumps({"db_factor_validation_research": "ok"}, indent=2, ensure_ascii=False))
    return 0


def _cmd_run_state_change(args: argparse.Namespace) -> int:
    from db.client import get_supabase_client
    from observability.run_logger import OperationalRunSession
    from state_change.runner import run_state_change

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    fv = args.factor_version or os.getenv("FACTOR_VERSION") or "v1"
    with OperationalRunSession(
        client,
        run_type="state_change",
        component="state_change_engine_v1",
        metadata_json={
            "universe": str(args.universe),
            "factor_version": str(fv),
            "dry_run": bool(args.dry_run),
        },
    ) as op:
        out = run_state_change(
            client,
            universe_name=str(args.universe),
            factor_version=str(fv),
            as_of_date=args.as_of_date,
            start_date=args.start_date,
            end_date=args.end_date,
            limit=int(args.limit),
            dry_run=bool(args.dry_run),
            include_nullable_overlays=bool(args.include_nullable_overlays),
        )
        st = str(out.get("status") or "")
        if st == "no_observations":
            op.finish_failed(
                error_class="pipeline",
                error_code="no_observations",
                message=str(out.get("hint") or out.get("message") or "no_observations"),
                failure_category="source_data_missing",
            )
        elif st == "dry_run":
            op.finish_success(
                rows_read=int(out.get("scores") or 0),
                rows_written=0,
                warnings_count=int(out.get("warnings") or 0),
                trace_json={
                    "dry_run": True,
                    "components": out.get("components"),
                    "scores": out.get("scores"),
                    "candidates": out.get("candidates"),
                },
            )
        elif st == "completed":
            op.finish_success(
                rows_read=int(out.get("scores_written") or 0),
                rows_written=int(out.get("components_written") or 0)
                + int(out.get("scores_written") or 0)
                + int(out.get("candidates_written") or 0),
                warnings_count=int(out.get("warnings") or 0),
                trace_json={"state_change_run_id": out.get("run_id")},
            )
        else:
            op.finish_warning(
                rows_read=None,
                rows_written=None,
                message=f"unexpected_status={st}",
                trace_json={"out": out},
            )
    if args.output_json:
        print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    else:
        print(
            "status={} run_id={} components={} scores={} candidates={} warnings={}".format(
                out.get("status"),
                out.get("run_id"),
                out.get("components_written", out.get("components", "?")),
                out.get("scores_written", out.get("scores", "?")),
                out.get("candidates_written", out.get("candidates", "?")),
                out.get("warnings"),
            )
        )
        if out.get("hint"):
            print("hint:", out.get("hint"), file=sys.stderr)
    st = str(out.get("status") or "")
    if st == "failed":
        return 1
    return 0


def _cmd_report_state_change_summary(args: argparse.Namespace) -> int:
    from db.client import get_supabase_client
    from state_change.cli_report import emit_state_change_summary
    from state_change.reports import build_state_change_run_report, resolve_report_run_id

    if not args.run_id and not args.universe:
        print("오류: --run-id 또는 --universe 중 하나를 지정하세요.", file=sys.stderr)
        return 1
    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    rid = resolve_report_run_id(
        client, universe_name=args.universe, run_id=args.run_id
    )
    if not rid:
        payload = {
            "ok": False,
            "error": "no_completed_run_found",
            "hint": (
                "해당 universe에 status=completed 인 state_change_runs 가 없습니다. "
                "run-state-change 가 observations=0 으로 끝나면 run 행이 생기지 않습니다. "
                "issuer_quarter_factor_panels 를 채운 뒤 run-state-change 를 다시 실행하거나, "
                "이미 있는 run 이 있다면 --run-id 로 지정하세요."
            ),
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        print(payload["hint"], file=sys.stderr)
        return 1
    payload = build_state_change_run_report(
        client,
        run_id=rid,
        scores_limit=int(args.scores_limit),
        candidates_limit=int(args.candidates_limit),
    )
    emit_state_change_summary(payload, output_json=bool(args.output_json))
    return 0 if payload.get("ok") else 1


def _cmd_smoke_state_change(_args: argparse.Namespace) -> int:
    from db.client import get_supabase_client
    from db.records import smoke_state_change_tables

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    smoke_state_change_tables(client)
    print(json.dumps({"db_state_change_phase6": "ok"}, indent=2, ensure_ascii=False))
    return 0


def _cmd_smoke_backfill(_args: argparse.Namespace) -> int:
    from db.client import get_supabase_client
    from db.records import smoke_backfill_tables

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    smoke_backfill_tables(client)
    print(json.dumps({"db_backfill_orchestration": "ok"}, indent=2, ensure_ascii=False))
    return 0


def _cmd_backfill_universe(args: argparse.Namespace) -> int:
    from db.client import get_supabase_client
    from backfill.backfill_runner import run_backfill_universe

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    fv = args.factor_version or os.environ.get("FACTOR_VERSION", "v1")
    out = run_backfill_universe(
        settings,
        client,
        mode=str(args.mode),
        universe_name=str(args.universe),
        symbol_limit=args.symbol_limit,
        start_stage=args.start_stage,
        end_stage=args.end_stage,
        dry_run=bool(args.dry_run),
        retry_failed_only=bool(args.retry_failed_only),
        from_orchestration_run_id=args.from_orchestration_run_id,
        rerun_phase5=bool(args.rerun_phase5),
        rerun_phase6=bool(args.rerun_phase6),
        sleep_sec=float(args.sleep),
        factor_version=str(fv),
        market_lookback_days=int(args.market_lookback_days),
        coverage_stage=args.coverage_stage,
        issuer_target=args.issuer_target,
        write_coverage_checkpoint=args.write_coverage_checkpoint,
    )
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0 if out.get("status") == "completed" else 1


def _cmd_report_backfill_status(args: argparse.Namespace) -> int:
    from pathlib import Path

    from backfill.cli_report import emit_backfill_report
    from backfill.status_report import build_backfill_status_payload
    from db.client import get_supabase_client

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    include_sparse = bool(args.include_sparse_diagnostics) or bool(
        args.write_sparse_diagnostics
    )
    payload = build_backfill_status_payload(
        client,
        mode=str(args.mode),
        universe_name=str(args.universe),
        symbol_limit=args.symbol_limit,
        include_diagnostics=not args.no_diagnostics,
        thin_threshold=int(args.thin_threshold),
        orchestration_run_id=args.orchestration_run_id,
        coverage_stage=args.coverage_stage,
        issuer_target=args.issuer_target,
        include_coverage_checkpoint=bool(args.include_coverage_checkpoint),
        include_sparse_diagnostics=include_sparse,
    )
    if args.write_diagnostics:
        p = Path(args.write_diagnostics).expanduser()
        diag = payload.get("join_diagnostics") or {}
        p.write_text(
            json.dumps(diag, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
    if args.write_sparse_diagnostics:
        p2 = Path(args.write_sparse_diagnostics).expanduser()
        sp = payload.get("sparse_issuer_diagnostics") or {}
        p2.write_text(
            json.dumps(sp, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
    emit_backfill_report(payload, output_json=bool(args.output_json))
    return 0


def _cmd_smoke_harness(_args: argparse.Namespace) -> int:
    from db.client import get_supabase_client
    from db.records import smoke_harness_tables

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    smoke_harness_tables(client)
    print(json.dumps({"phase7_harness_tables": "ok"}, indent=2, ensure_ascii=False))
    return 0


def _cmd_build_ai_harness_inputs(args: argparse.Namespace) -> int:
    from db.client import get_supabase_client
    from db import records as dbrec
    from harness.input_materializer import materialize_inputs_for_run

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    rid = args.run_id or dbrec.fetch_latest_state_change_run_id(
        client, universe_name=args.universe
    )
    if not rid:
        print(
            json.dumps(
                {"error": "no_completed_state_change_run", "universe": args.universe},
                ensure_ascii=False,
            )
        )
        return 1
    out = materialize_inputs_for_run(client, run_id=rid, limit=int(args.limit))
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0


def _cmd_generate_investigation_memos(args: argparse.Namespace) -> int:
    from db.client import get_supabase_client
    from db import records as dbrec
    from harness.run_batch import generate_memos_for_run
    from observability.run_logger import OperationalRunSession

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    rid = args.run_id or dbrec.fetch_latest_state_change_run_id(
        client, universe_name=args.universe
    )
    if not rid:
        print(
            json.dumps(
                {"error": "no_completed_state_change_run", "universe": args.universe},
                ensure_ascii=False,
            )
        )
        return 1
    cfilter: set[str] | None = None
    if getattr(args, "candidate_ids", None):
        cfilter = {x.strip() for x in str(args.candidate_ids).split(",") if x.strip()}
    with OperationalRunSession(
        client,
        run_type="ai_harness",
        component="investigation_memo_batch",
        metadata_json={"state_change_run_id": rid, "universe": args.universe},
        linked_external_id=rid,
    ) as op:
        out = generate_memos_for_run(
            client,
            run_id=rid,
            limit=int(args.limit),
            force_new_memo_version=bool(args.force_new_memo_version),
            candidate_ids=cfilter,
        )
        ins = int(out.get("memos_inserted_new_version") or 0)
        rep = int(out.get("memos_replaced_in_place") or 0)
        errs = out.get("errors") or []
        n_err = len(errs)
        if n_err and ins + rep == 0:
            op.finish_failed(
                error_class="memo_pipeline",
                error_code="all_candidates_failed",
                message=str(errs[0].get("error") if errs else "errors")[:2000],
                failure_category="execution_error",
            )
        elif n_err:
            op.finish_warning(
                rows_read=ins + rep + n_err,
                rows_written=ins + rep,
                message=f"{n_err} memo candidate errors (see trace)",
                trace_json={"errors_sample": errs[:5], **out},
            )
        elif ins + rep == 0:
            op.finish_empty_valid(
                rows_read=0,
                trace_json={**out, "note": "no_inputs_or_all_filtered"},
            )
        else:
            op.finish_success(
                rows_read=ins + rep,
                rows_written=ins + rep,
                warnings_count=0,
                trace_json=out,
            )
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    ins2 = int(out.get("memos_inserted_new_version") or 0)
    rep2 = int(out.get("memos_replaced_in_place") or 0)
    if out.get("errors") and ins2 + rep2 == 0:
        return 1
    return 0


def _cmd_set_review_queue_status(args: argparse.Namespace) -> int:
    from db.client import get_supabase_client
    from db import records as dbrec
    from harness.rerun_policy import assert_valid_queue_transition

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    cid = str(args.candidate_id)
    existing = dbrec.fetch_operator_review_queue_row(client, candidate_id=cid)
    assert_valid_queue_transition(
        existing.get("status") if existing else None, str(args.status)
    )
    dbrec.update_operator_review_queue_status(
        client,
        candidate_id=cid,
        status=str(args.status),
        status_reason=args.reason,
    )
    row = dbrec.fetch_operator_review_queue_row(client, candidate_id=cid)
    print(json.dumps({"ok": True, "row": row}, indent=2, ensure_ascii=False, default=str))
    return 0


def _cmd_export_phase7_evidence_bundle(args: argparse.Namespace) -> int:
    from pathlib import Path

    from db.client import get_supabase_client
    from db import records as dbrec
    from harness.run_batch import generate_memos_for_run

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)

    ids: list[str] = []
    if args.candidate_ids:
        ids = [x.strip() for x in args.candidate_ids.split(",") if x.strip()]
    elif args.from_run:
        r = (
            client.table("state_change_candidates")
            .select("id")
            .eq("run_id", str(args.from_run))
            .limit(int(args.sample_n))
            .execute()
        )
        ids = [str(x["id"]) for x in (r.data or [])]
    if len(ids) < 1:
        if args.from_run and not args.candidate_ids:
            print(
                json.dumps(
                    {
                        "error": "from_run_returned_zero_candidates",
                        "run_id_used": str(args.from_run),
                        "hint": "This UUID must be state_change_runs.id (not a git SHA). "
                        "Confirm rows: select count(*) from state_change_candidates "
                        "where run_id = '<id>';",
                    },
                    ensure_ascii=False,
                )
            )
        else:
            print(
                json.dumps(
                    {
                        "error": "no_candidate_ids",
                        "hint": "Pass --candidate-ids uuid,uuid or --from-run <state_change_runs.id>",
                    },
                    ensure_ascii=False,
                )
            )
        return 1

    out_dir = Path(args.out_dir).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest: list[dict[str, object]] = []

    for cid in ids:
        cand = dbrec.fetch_state_change_candidate(client, candidate_id=cid)
        if not cand:
            manifest.append({"candidate_id": cid, "error": "candidate_not_found"})
            continue
        run_id = str(cand["run_id"])
        sub = out_dir / cid
        sub.mkdir(parents=True, exist_ok=True)
        inp = dbrec.fetch_ai_harness_input_for_candidate(
            client, candidate_id=cid, contract_version="ai_harness_input_v1"
        )
        (sub / "state_change_candidate.json").write_text(
            json.dumps(cand, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        (sub / "ai_harness_input.json").write_text(
            json.dumps(inp or {}, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )

        g1 = generate_memos_for_run(
            client,
            run_id=run_id,
            limit=2000,
            candidate_ids={cid},
            force_new_memo_version=False,
        )
        g2 = generate_memos_for_run(
            client,
            run_id=run_id,
            limit=2000,
            candidate_ids={cid},
            force_new_memo_version=False,
        )
        (sub / "rerun_generate_summary.json").write_text(
            json.dumps({"first": g1, "second": g2}, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )

        memo = dbrec.fetch_latest_memo_for_candidate(client, candidate_id=cid)
        qrow = dbrec.fetch_operator_review_queue_row(client, candidate_id=cid)
        claims: list[dict[str, object]] = []
        if memo:
            claims = dbrec.fetch_investigation_memo_claims(
                client, memo_id=str(memo["id"])
            )
        (sub / "investigation_memo.json").write_text(
            json.dumps(memo or {}, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        (sub / "investigation_memo_claims.json").write_text(
            json.dumps(claims, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        (sub / "operator_review_queue.json").write_text(
            json.dumps(qrow or {}, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        pj = (inp or {}).get("payload_json") if isinstance(inp, dict) else None
        ticker_hint = pj.get("ticker") if isinstance(pj, dict) else None
        manifest.append(
            {
                "candidate_id": cid,
                "run_id": run_id,
                "ticker_hint": ticker_hint,
                "memo_id": (memo or {}).get("id"),
                "referee_passed": (memo or {}).get("referee_passed"),
                "claims_count": len(claims),
            }
        )

    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    print(json.dumps({"out_dir": str(out_dir), "manifest": manifest}, indent=2, ensure_ascii=False, default=str))
    return 0


def _cmd_report_review_queue(args: argparse.Namespace) -> int:
    from db.client import get_supabase_client
    from db.records import fetch_operator_review_queue

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    rows = fetch_operator_review_queue(
        client, status=args.status, limit=int(args.limit)
    )
    print(json.dumps({"count": len(rows), "items": rows}, indent=2, ensure_ascii=False, default=str))
    return 0


def _cmd_smoke_phase8(_args: argparse.Namespace) -> int:
    from db.client import get_supabase_client
    from db.records import smoke_phase8_tables

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    smoke_phase8_tables(client)
    print(json.dumps({"phase8_tables": "ok"}, indent=2, ensure_ascii=False))
    return 0


def _cmd_build_outlier_casebook(args: argparse.Namespace) -> int:
    from db.client import get_supabase_client
    from db import records as dbrec
    from casebook.build_run import run_outlier_casebook_build
    from observability.run_logger import OperationalRunSession

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    rid = args.run_id or dbrec.fetch_latest_state_change_run_id(
        client, universe_name=args.universe
    )
    if not rid:
        print(
            json.dumps(
                {"error": "no_completed_state_change_run", "universe": args.universe},
                ensure_ascii=False,
            )
        )
        return 1
    with OperationalRunSession(
        client,
        run_type="outlier_casebook",
        component="casebook_build_v1",
        metadata_json={
            "universe": args.universe,
            "state_change_run_id": rid,
            "candidate_limit": int(args.candidate_limit),
        },
        linked_external_id=rid,
    ) as op:
        out = run_outlier_casebook_build(
            client,
            state_change_run_id=rid,
            universe_name=args.universe,
            candidate_limit=int(args.candidate_limit),
        )
        if out.get("error") == "state_change_run_not_found":
            op.finish_failed(
                error_class="input",
                error_code="state_change_run_not_found",
                message=str(out.get("run_id") or ""),
                failure_category="configuration_error",
            )
        else:
            ec = int(out.get("entries_created") or 0)
            scanned = int(out.get("candidates_scanned") or 0)
            errs = out.get("errors") or []
            crid = str(out.get("casebook_run_id") or "")
            trace = {**out, "heuristic_marked_in_entries": True}
            if ec == 0 and not errs:
                op.finish_empty_valid(rows_read=scanned, trace_json=trace)
            elif errs and ec == 0:
                op.finish_failed(
                    error_class="casebook",
                    error_code="all_candidates_errored",
                    message=str(errs[0])[:2000],
                    failure_category="execution_error",
                )
            elif errs:
                op.finish_warning(
                    rows_read=scanned,
                    rows_written=ec,
                    message=f"{len(errs)} candidate errors during casebook scan",
                    trace_json=trace,
                )
            else:
                op.finish_success(
                    rows_read=scanned,
                    rows_written=ec,
                    warnings_count=0,
                    trace_json=trace,
                )
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    if out.get("error"):
        return 1
    errs = out.get("errors") or []
    if errs and int(out.get("entries_created") or 0) == 0:
        return 1
    return 0


def _cmd_build_daily_signal_snapshot(args: argparse.Namespace) -> int:
    from db.client import get_supabase_client
    from db import records as dbrec
    from observability.run_logger import OperationalRunSession
    from scanner.daily_build import run_daily_scanner_build

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    rid = args.run_id or dbrec.fetch_latest_state_change_run_id(
        client, universe_name=args.universe
    )
    if not rid:
        print(
            json.dumps(
                {"error": "no_completed_state_change_run", "universe": args.universe},
                ensure_ascii=False,
            )
        )
        return 1
    with OperationalRunSession(
        client,
        run_type="daily_scanner",
        component="scanner_daily_build_v1",
        metadata_json={
            "universe": args.universe,
            "state_change_run_id": rid,
            "as_of_calendar_date": args.as_of_date,
        },
        linked_external_id=rid,
    ) as op:
        out = run_daily_scanner_build(
            client,
            state_change_run_id=rid,
            universe_name=args.universe,
            as_of_calendar_date=args.as_of_date,
            candidate_scan_limit=int(args.candidate_limit),
            top_n=int(args.top_n),
            min_priority_score=float(args.min_priority_score),
            max_candidate_rank=int(args.max_candidate_rank),
        )
        wl = int(out.get("watchlist_entries") or 0)
        stats = out.get("stats") or {}
        scanned = int(stats.get("candidates_scanned") or 0)
        sid = str(out.get("scanner_run_id") or "")
        trace = {
            **out,
            "watchlist_empty_allowed": True,
            "message_layer_heuristic": True,
        }
        if wl == 0:
            op.finish_empty_valid(
                rows_read=scanned,
                trace_json=trace,
            )
        else:
            op.finish_success(
                rows_read=scanned,
                rows_written=wl + 1,
                trace_json=trace,
            )
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0


def _cmd_report_daily_watchlist(args: argparse.Namespace) -> int:
    from db.client import get_supabase_client
    from db import records as dbrec

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    sid = args.scanner_run_id
    if not sid:
        latest = dbrec.fetch_latest_scanner_run(
            client, universe_name=args.universe or None
        )
        if not latest:
            print(json.dumps({"error": "no_scanner_runs"}, ensure_ascii=False))
            return 1
        sid = str(latest["id"])
    run_row = dbrec.fetch_scanner_run(client, scanner_run_id=sid)
    snap = dbrec.fetch_daily_snapshot_for_scanner(client, scanner_run_id=sid)
    wl = dbrec.fetch_watchlist_for_scanner(client, scanner_run_id=sid, limit=200)
    print(
        json.dumps(
            {
                "scanner_run_id": sid,
                "scanner_run": run_row,
                "daily_signal_snapshot": snap,
                "watchlist": wl,
            },
            indent=2,
            ensure_ascii=False,
            default=str,
        )
    )
    return 0


def _cmd_export_casebook_samples(args: argparse.Namespace) -> int:
    from pathlib import Path

    from db.client import get_supabase_client
    from db import records as dbrec

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    crid = args.casebook_run_id
    state_change_run_id = args.state_change_run_id
    if not crid and not state_change_run_id and getattr(args, "universe", None):
        state_change_run_id = dbrec.fetch_latest_state_change_run_id(
            client, universe_name=str(args.universe)
        )
    if not crid and state_change_run_id:
        r = (
            client.table("outlier_casebook_runs")
            .select("id")
            .eq("state_change_run_id", str(state_change_run_id))
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if r.data:
            crid = str(r.data[0]["id"])
    if not crid:
        print(
            json.dumps(
                {
                    "error": "no_casebook_run",
                    "hint": (
                        "--casebook-run-id or --state-change-run-id or "
                        "--universe (최신 completed state_change → 최신 casebook)"
                    ),
                },
                ensure_ascii=False,
            )
        )
        return 1
    rows = dbrec.fetch_outlier_casebook_entries_for_run(
        client, casebook_run_id=crid, limit=int(args.limit)
    )
    out_dir = Path(args.out_dir).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "casebook_run_id.txt").write_text(crid, encoding="utf-8")
    (out_dir / "entries.json").write_text(
        json.dumps(rows, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    manifest = [
        {
            "entry_id": x.get("id"),
            "candidate_id": x.get("candidate_id"),
            "outlier_type": x.get("outlier_type"),
            "ticker": x.get("ticker"),
        }
        for x in rows[: int(args.limit)]
    ]
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    print(json.dumps({"out_dir": str(out_dir), "count": len(rows), "manifest": manifest}, indent=2, ensure_ascii=False, default=str))
    return 0


def _cmd_smoke_phase9_observability(_args: argparse.Namespace) -> int:
    from db.client import get_supabase_client
    from db.records import smoke_phase9_observability_tables

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    smoke_phase9_observability_tables(client)
    print(
        json.dumps(
            {"phase9_observability_tables": "ok", "operational_runs": "reachable"},
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


def _cmd_report_run_health(args: argparse.Namespace) -> int:
    from db.client import get_supabase_client
    from observability.reporting import build_run_health_payload

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    payload = build_run_health_payload(client, limit=int(args.limit))
    print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
    return 0


def _cmd_report_failures(args: argparse.Namespace) -> int:
    from db.client import get_supabase_client
    from observability.reporting import build_failures_payload

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    payload = build_failures_payload(client, limit=int(args.limit))
    print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
    return 0


def _cmd_report_research_registry(args: argparse.Namespace) -> int:
    from db.client import get_supabase_client
    from research_registry.reporting import format_registry_report

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    payload = format_registry_report(client, limit=int(args.limit))
    print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
    return 0


def _cmd_seed_phase9_research_samples(_args: argparse.Namespace) -> int:
    from db.client import get_supabase_client
    from research_registry.registry import ensure_sample_hypotheses

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    out = ensure_sample_hypotheses(client)
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0


def _cmd_seed_source_registry(_args: argparse.Namespace) -> int:
    from db.client import get_supabase_client
    from sources.registry import seed_registry_from_constants

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    out = seed_registry_from_constants(client)
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0


def _cmd_report_source_registry(_args: argparse.Namespace) -> int:
    from db.client import get_supabase_client
    from sources.reporting import build_source_registry_report

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    payload = build_source_registry_report(client)
    print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
    return 0


def _cmd_report_overlay_gap(args: argparse.Namespace) -> int:
    from db.client import get_supabase_client
    from db import records as dbrec
    from sources.reporting import build_overlay_gap_report

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    payload = build_overlay_gap_report(client)
    if getattr(args, "persist", False):
        rid = dbrec.insert_source_overlay_gap_report(client, payload_json=payload)
        payload = {**payload, "persisted_gap_report_id": rid}
    print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
    return 0


def _cmd_smoke_source_adapters(_args: argparse.Namespace) -> int:
    from sources.contracts import validate_probe_result
    from sources.estimates_adapter import EstimatesAdapter
    from sources.price_quality_adapter import PriceQualityAdapter
    from sources.transcripts_adapter import TranscriptsAdapter

    probes = [
        TranscriptsAdapter().probe(),
        EstimatesAdapter().probe(),
        PriceQualityAdapter().probe(),
    ]
    for p in probes:
        validate_probe_result(p)
    out = {
        "adapter_smoke": "ok",
        "probes": [
            {
                "adapter_name": p.adapter_name,
                "availability": p.availability,
                "normalization_schema_version": p.normalization_schema_version,
                "failure_behavior": p.failure_behavior,
                "rights_source_id": p.rights.source_id if p.rights else None,
            }
            for p in probes
        ],
    }
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0


def _cmd_export_source_roi_matrix(_args: argparse.Namespace) -> int:
    from sources.reporting import OVERLAY_ROI_RANKED

    print(json.dumps(OVERLAY_ROI_RANKED, indent=2, ensure_ascii=False, default=str))
    return 0


def _cmd_probe_transcripts_provider(_args: argparse.Namespace) -> int:
    from db.client import get_supabase_client
    from observability.run_logger import OperationalRunSession
    from sources import transcripts_provider_binding as bind
    from sources.transcripts_ingest import run_fmp_probe_and_update_overlay

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    with OperationalRunSession(
        client,
        run_type="transcript_overlay",
        component="fmp_transcript_probe",
        metadata_json={"cli": "probe-transcripts-provider"},
    ) as op:
        try:
            out = run_fmp_probe_and_update_overlay(
                client, settings, operational_run_id=op.operational_run_id
            )
        except Exception as e:
            op.finish_failed(
                error_class="execution_error",
                error_code="probe_exception",
                message=str(e),
                failure_category="execution_error",
            )
            print(json.dumps({"ok": False, "error": str(e), "probe": None}, indent=2))
            return 1
        ps = out.get("probe_status")
        if ps == bind.NOT_CONFIGURED:
            op.finish_failed(
                error_class="configuration_error",
                error_code=str(out.get("detail") or "not_configured"),
                message="Transcript provider not configured for FMP probe",
                failure_category="configuration_error",
            )
            print(json.dumps({"ok": True, "truthful_blocked": True, "probe": out}, indent=2))
            return 1
        if ps == bind.FAILED_RIGHTS_OR_AUTH:
            op.finish_failed(
                error_class="auth_or_rights",
                error_code="fmp_http_auth_or_subscription",
                message="FMP returned auth/subscription/rights failure",
                failure_category="other",
            )
            print(json.dumps({"ok": False, "probe": out}, indent=2))
            return 1
        if ps == bind.FAILED_NETWORK:
            op.finish_failed(
                error_class="network_error",
                error_code="fmp_network",
                message=str(out.get("detail") or "network"),
                failure_category="other",
            )
            print(json.dumps({"ok": False, "probe": out}, indent=2))
            return 1
        if ps == bind.CONFIGURED_BUT_UNVERIFIED:
            op.finish_warning(
                rows_read=1,
                rows_written=1,
                message="unexpected_response_shape",
                trace_json={"probe": out},
            )
            print(json.dumps({"ok": True, "probe": out}, indent=2))
            return 0
        if ps == bind.PARTIAL:
            op.finish_warning(
                rows_read=1,
                rows_written=1,
                message="partial_transcript_probe",
                trace_json={"probe": out},
            )
            print(json.dumps({"ok": True, "probe": out}, indent=2))
            return 0
        op.finish_success(
            rows_read=1,
            rows_written=1,
            trace_json={"probe": out},
        )
        print(json.dumps({"ok": True, "probe": out}, indent=2))
        return 0


def _cmd_ingest_transcripts_sample(args: argparse.Namespace) -> int:
    from db.client import get_supabase_client
    from observability.run_logger import OperationalRunSession
    from sources import transcripts_provider_binding as bind
    from sources.transcripts_ingest import run_fmp_sample_ingest

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    with OperationalRunSession(
        client,
        run_type="transcript_overlay",
        component="fmp_transcript_ingest_sample",
        metadata_json={
            "cli": "ingest-transcripts-sample",
            "symbol": args.symbol,
            "year": args.year,
            "quarter": args.quarter,
        },
    ) as op:
        if not bind.fmp_api_key_present(settings):
            op.finish_failed(
                error_class="configuration_error",
                error_code="FMP_API_KEY_missing",
                message="ingest blocked: FMP_API_KEY not configured",
                failure_category="configuration_error",
            )
            print(
                json.dumps(
                    {
                        "ok": True,
                        "truthful_blocked": True,
                        "error": "FMP_API_KEY_not_configured",
                        "operational_run_id": op.operational_run_id,
                    },
                    indent=2,
                )
            )
            return 1
        try:
            out = run_fmp_sample_ingest(
                client,
                settings,
                symbol=args.symbol,
                year=int(args.year),
                quarter=int(args.quarter),
                operational_run_id=op.operational_run_id,
            )
        except Exception as e:
            op.finish_failed(
                error_class="execution_error",
                error_code="ingest_exception",
                message=str(e),
                failure_category="execution_error",
            )
            print(json.dumps({"ok": False, "error": str(e)}, indent=2))
            return 1
        if out.get("classify") == bind.FAILED_RIGHTS_OR_AUTH:
            op.finish_failed(
                error_class="auth_or_rights",
                error_code="fmp_ingest_auth",
                message="ingest_http_auth_or_rights",
                failure_category="other",
            )
            print(json.dumps({"ok": False, "ingest": out}, indent=2))
            return 1
        if out.get("overlay_availability") == "available" and out.get(
            "normalization_status"
        ) == "ok":
            op.finish_success(rows_read=1, rows_written=2, trace_json={"ingest": out})
        else:
            op.finish_warning(
                rows_read=1,
                rows_written=2,
                message="partial_or_empty_transcript_ingest",
                trace_json={"ingest": out},
            )
        print(json.dumps({"ok": True, "ingest": out}, indent=2))
        return 0


def _cmd_report_transcripts_overlay_status(_args: argparse.Namespace) -> int:
    from db.client import get_supabase_client
    from sources.transcripts_ingest import report_transcripts_overlay_status

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    print(json.dumps(report_transcripts_overlay_status(client), indent=2, default=str))
    return 0


def _cmd_export_transcript_normalization_sample(args: argparse.Namespace) -> int:
    from db.client import get_supabase_client
    from db import records as dbrec

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    t = args.ticker.upper().strip()
    row = dbrec.fetch_latest_normalized_transcript_for_ticker(client, ticker=t)
    if not row:
        print(json.dumps({"ok": False, "error": "no_row", "ticker": t}, indent=2))
        return 1
    redacted = {k: v for k, v in row.items() if k != "transcript_text"}
    redacted["transcript_text_len"] = len(str(row.get("transcript_text") or ""))
    redacted["transcript_text_prefix_120"] = str(row.get("transcript_text") or "")[:120]
    print(json.dumps({"ok": True, "row": redacted}, indent=2, default=str))
    return 0


def _cmd_run_public_core_cycle(args: argparse.Namespace) -> int:
    from pathlib import Path

    from db.client import get_supabase_client
    from observability.run_logger import OperationalRunSession
    from public_core.cycle import default_cycle_out_dir, run_public_core_cycle

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    out = Path(args.out_dir).expanduser() if args.out_dir else None
    with OperationalRunSession(
        client,
        run_type="public_core_cycle",
        component="run_public_core_cycle_v1",
        metadata_json={
            "cli": "run-public-core-cycle",
            "universe": args.universe,
            "ensure_state_change": bool(args.ensure_state_change),
        },
    ) as op:
        try:
            payload = run_public_core_cycle(
                client,
                settings,
                universe=str(args.universe),
                state_change_run_id=args.state_change_run_id,
                ensure_state_change=bool(args.ensure_state_change),
                factor_version=str(args.factor_version or "v1"),
                state_change_limit=int(args.state_change_limit),
                harness_limit=int(args.harness_limit),
                memo_limit=int(args.memo_limit),
                casebook_candidate_limit=int(args.casebook_candidate_limit),
                scanner_candidate_limit=int(args.scanner_candidate_limit),
                scanner_top_n=int(args.scanner_top_n),
                min_priority_score=float(args.min_priority_score),
                max_candidate_rank=int(args.max_candidate_rank),
                as_of_calendar_date=args.as_of_date,
                out_dir=out,
            )
        except Exception as e:
            op.finish_failed(
                error_class="execution_error",
                error_code="public_core_cycle_exception",
                message=str(e),
                failure_category="execution_error",
            )
            print(json.dumps({"ok": False, "error": str(e)}, indent=2))
            return 1
        if not payload.get("ok"):
            op.finish_failed(
                error_class="pipeline",
                error_code=str(payload.get("error") or "cycle_not_ok"),
                message=str(payload.get("hint") or payload.get("error") or "")[:2000],
                failure_category="configuration_error",
            )
        else:
            n_warn = len(payload.get("warnings") or [])
            wl = 0
            for s in payload.get("stages") or []:
                if s.get("name") == "scanner_watchlist" and isinstance(s.get("out"), dict):
                    wl = int((s["out"] or {}).get("watchlist_entries") or 0)
            op.finish_success(
                rows_read=len(payload.get("stages") or []),
                rows_written=max(1, wl + 1),
                warnings_count=n_warn,
                trace_json={
                    "state_change_run_id": payload.get("state_change_run_id"),
                    "out_dir": str(out or default_cycle_out_dir()),
                    "public_core_cycle_quality_run_id": payload.get(
                        "public_core_cycle_quality_run_id"
                    ),
                    "cycle_quality_class": payload.get("cycle_quality_class"),
                },
            )
    print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
    return 0 if payload.get("ok") else 1


def _cmd_report_public_core_quality(args: argparse.Namespace) -> int:
    from db.client import get_supabase_client
    from db import records as dbrec

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    rows = dbrec.fetch_public_core_cycle_quality_runs_recent(client, limit=int(args.limit))
    print(json.dumps({"ok": True, "runs": rows}, indent=2, ensure_ascii=False, default=str))
    return 0


def _cmd_export_public_core_quality_sample(args: argparse.Namespace) -> int:
    import json as json_lib
    from pathlib import Path

    from db.client import get_supabase_client
    from db import records as dbrec

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    rows = dbrec.fetch_public_core_cycle_quality_runs_recent(client, limit=int(args.limit))
    dest = Path(args.out).expanduser()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        json_lib.dumps({"runs": rows}, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    print(json.dumps({"ok": True, "wrote": str(dest), "n": len(rows)}, indent=2))
    return 0


def _cmd_smoke_phase14_research_engine(_args: argparse.Namespace) -> int:
    from db.client import get_supabase_client
    from db.records import smoke_phase14_research_engine_tables

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    smoke_phase14_research_engine_tables(client)
    print(json.dumps({"ok": True, "research_engine_tables": "reachable"}, indent=2))
    return 0


def _cmd_create_research_program(args: argparse.Namespace) -> int:
    from db.client import get_supabase_client
    from research_engine.service import create_program

    bad_q = _exit_unless_uuid("quality_run_id", args.quality_run_id, optional=True)
    if bad_q is not None:
        return bad_q

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    out = create_program(
        client,
        universe_name=str(args.universe),
        title=args.title,
        quality_run_id=args.quality_run_id,
        owner_actor=str(args.owner_actor or "operator"),
    )
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0 if out.get("ok") else 1


def _cmd_list_research_programs(args: argparse.Namespace) -> int:
    from db.client import get_supabase_client
    from db import records as dbrec

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    rows = dbrec.fetch_research_programs_recent(client, limit=int(args.limit))
    print(json.dumps({"ok": True, "programs": rows}, indent=2, ensure_ascii=False, default=str))
    return 0


def _cmd_generate_program_hypotheses(args: argparse.Namespace) -> int:
    from db.client import get_supabase_client
    from research_engine.service import generate_hypotheses

    bad = _exit_unless_uuid("program_id", args.program_id)
    if bad is not None:
        return bad

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    out = generate_hypotheses(client, program_id=str(args.program_id))
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0 if out.get("ok") else 1


def _cmd_review_research_hypothesis(args: argparse.Namespace) -> int:
    from db.client import get_supabase_client
    from research_engine.service import run_review_round

    bad = _exit_unless_uuid("hypothesis_id", args.hypothesis_id)
    if bad is not None:
        return bad

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    out = run_review_round(client, hypothesis_id=str(args.hypothesis_id))
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0 if out.get("ok") else 1


def _cmd_run_research_referee(args: argparse.Namespace) -> int:
    from db.client import get_supabase_client
    from research_engine.service import run_referee

    bad = _exit_unless_uuid("hypothesis_id", args.hypothesis_id)
    if bad is not None:
        return bad

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    out = run_referee(client, hypothesis_id=str(args.hypothesis_id))
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0 if out.get("ok") else 1


def _cmd_report_research_program(args: argparse.Namespace) -> int:
    from db.client import get_supabase_client
    from db import records as dbrec

    bad = _exit_unless_uuid("program_id", args.program_id)
    if bad is not None:
        return bad

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    prog = dbrec.fetch_research_program(client, program_id=str(args.program_id))
    if not prog:
        print(json.dumps({"ok": False, "error": "program_not_found"}, indent=2))
        return 1
    hyps = dbrec.fetch_research_hypotheses_for_program(client, program_id=str(args.program_id))
    print(
        json.dumps(
            {"ok": True, "program": prog, "hypotheses": hyps},
            indent=2,
            ensure_ascii=False,
            default=str,
        )
    )
    return 0


def _cmd_export_research_dossier(args: argparse.Namespace) -> int:
    import json as json_lib
    from pathlib import Path

    from db.client import get_supabase_client
    from research_engine.service import export_dossier_for_program

    bad = _exit_unless_uuid("program_id", args.program_id)
    if bad is not None:
        return bad

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    out = export_dossier_for_program(client, program_id=str(args.program_id))
    if not out.get("ok"):
        print(json.dumps(out, indent=2))
        return 1
    dest = Path(args.out).expanduser()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        json_lib.dumps(out["dossier"], indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    print(json.dumps({"ok": True, "wrote": str(dest)}, indent=2))
    return 0


def _cmd_smoke_phase15_recipe_validation(_args: argparse.Namespace) -> int:
    from db.client import get_supabase_client
    from db.records import smoke_phase15_recipe_validation_tables

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    smoke_phase15_recipe_validation_tables(client)
    print(json.dumps({"ok": True, "recipe_validation_tables": "reachable"}, indent=2))
    return 0


def _cmd_run_recipe_validation(args: argparse.Namespace) -> int:
    import json as json_lib

    from db.client import get_supabase_client
    from research_validation.service import run_recipe_validation

    bad = _exit_unless_uuid("hypothesis_id", args.hypothesis_id)
    if bad is not None:
        return bad

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    out = run_recipe_validation(
        client, hypothesis_id=str(args.hypothesis_id), panel_limit=int(args.panel_limit)
    )
    print(json_lib.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0 if out.get("ok") else 1


def _cmd_report_recipe_validation(args: argparse.Namespace) -> int:
    import json as json_lib

    from db.client import get_supabase_client
    from research_validation.service import report_validation_run_bundle

    bad = _exit_unless_uuid("validation_run_id", args.validation_run_id)
    if bad is not None:
        return bad

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    out = report_validation_run_bundle(
        client, validation_run_id=str(args.validation_run_id)
    )
    print(json_lib.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0 if out.get("ok") else 1


def _cmd_compare_recipe_baselines(args: argparse.Namespace) -> int:
    import json as json_lib

    from db.client import get_supabase_client
    from research_validation.service import compare_baselines_for_hypothesis

    bad = _exit_unless_uuid("hypothesis_id", args.hypothesis_id)
    if bad is not None:
        return bad

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    out = compare_baselines_for_hypothesis(client, hypothesis_id=str(args.hypothesis_id))
    print(json_lib.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0 if out.get("ok") else 1


def _cmd_report_recipe_survivors(args: argparse.Namespace) -> int:
    import json as json_lib

    from db.client import get_supabase_client
    from db import records as dbrec

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    rows = dbrec.fetch_recipe_survivors_recent(client, limit=int(args.limit))
    print(json_lib.dumps({"ok": True, "survivors": rows}, indent=2, ensure_ascii=False, default=str))
    return 0


def _cmd_export_recipe_scorecard(args: argparse.Namespace) -> int:
    import json as json_lib
    from pathlib import Path

    from db.client import get_supabase_client
    from research_validation.service import export_scorecard_for_hypothesis

    bad = _exit_unless_uuid("hypothesis_id", args.hypothesis_id)
    if bad is not None:
        return bad
    bad = _exit_unless_uuid("validation_run_id", args.validation_run_id, optional=True)
    if bad is not None:
        return bad

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    out = export_scorecard_for_hypothesis(
        client,
        hypothesis_id=str(args.hypothesis_id),
        validation_run_id=args.validation_run_id,
    )
    if not out.get("ok"):
        print(json_lib.dumps(out, indent=2))
        return 1
    dest = Path(args.out).expanduser()
    dest.parent.mkdir(parents=True, exist_ok=True)
    card = out["scorecard"]
    md_path = dest.with_suffix(".md") if dest.suffix != ".md" else dest
    json_path = dest if dest.suffix == ".json" else dest.with_suffix(".json")
    json_path.write_text(
        json_lib.dumps(card, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    md_path.write_text(str(out.get("markdown") or ""), encoding="utf-8")
    print(
        json_lib.dumps(
            {"ok": True, "json": str(json_path), "markdown": str(md_path)},
            indent=2,
        )
    )
    return 0


def _cmd_smoke_phase16_validation_campaign(_args: argparse.Namespace) -> int:
    from db.client import get_supabase_client
    from db.records import smoke_phase16_validation_campaign_tables

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    smoke_phase16_validation_campaign_tables(client)
    print(json.dumps({"ok": True, "validation_campaign_tables": "reachable"}, indent=2))
    return 0


def _cmd_run_validation_campaign(args: argparse.Namespace) -> int:
    import json as json_lib

    from db.client import get_supabase_client
    from validation_campaign.service import run_validation_campaign

    bad = _exit_unless_uuid("program_id", args.program_id)
    if bad is not None:
        return bad

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    out = run_validation_campaign(
        client,
        program_id=str(args.program_id),
        run_mode=str(args.run_mode),
        panel_limit=int(args.panel_limit),
    )
    print(json_lib.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0 if out.get("ok") else 1


def _cmd_report_validation_campaign(args: argparse.Namespace) -> int:
    import json as json_lib

    from db.client import get_supabase_client
    from validation_campaign.service import report_validation_campaign

    bad = _exit_unless_uuid("campaign_run_id", args.campaign_run_id)
    if bad is not None:
        return bad

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    out = report_validation_campaign(
        client, campaign_run_id=str(args.campaign_run_id)
    )
    print(json_lib.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0 if out.get("ok") else 1


def _cmd_report_program_survival_distribution(args: argparse.Namespace) -> int:
    import json as json_lib

    from db.client import get_supabase_client
    from validation_campaign.service import report_program_survival_distribution

    bad = _exit_unless_uuid("program_id", args.program_id)
    if bad is not None:
        return bad

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    out = report_program_survival_distribution(
        client, program_id=str(args.program_id)
    )
    print(json_lib.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0 if out.get("ok") else 1


def _cmd_export_validation_decision_brief(args: argparse.Namespace) -> int:
    import json as json_lib
    from pathlib import Path

    from db.client import get_supabase_client
    from validation_campaign.service import (
        build_decision_brief,
        render_decision_brief_markdown,
    )

    bad = _exit_unless_uuid("campaign_run_id", args.campaign_run_id)
    if bad is not None:
        return bad

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    out = build_decision_brief(client, campaign_run_id=str(args.campaign_run_id))
    if not out.get("ok"):
        print(json_lib.dumps(out, indent=2))
        return 1
    dest = Path(args.out).expanduser()
    dest.parent.mkdir(parents=True, exist_ok=True)
    brief = out["brief"]
    md_path = dest.with_suffix(".md") if dest.suffix != ".md" else dest
    json_path = dest if dest.suffix == ".json" else dest.with_suffix(".json")
    json_path.write_text(
        json_lib.dumps(brief, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    md_path.write_text(render_decision_brief_markdown(brief), encoding="utf-8")
    print(
        json_lib.dumps(
            {"ok": True, "json": str(json_path), "markdown": str(md_path)},
            indent=2,
        )
    )
    return 0


def _cmd_list_eligible_validation_hypotheses(args: argparse.Namespace) -> int:
    import json as json_lib

    from db.client import get_supabase_client
    from validation_campaign.service import list_eligible_hypotheses_for_campaign

    bad = _exit_unless_uuid("program_id", args.program_id)
    if bad is not None:
        return bad

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    out = list_eligible_hypotheses_for_campaign(
        client, program_id=str(args.program_id)
    )
    print(json_lib.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0 if out.get("ok") else 1


def _cmd_list_universe_names(_args: argparse.Namespace) -> int:
    import json as json_lib

    from db.client import get_supabase_client
    from db.records import fetch_universe_catalog_for_operators
    from research.universe_slices import ALL_RESEARCH_SLICES

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    catalog = fetch_universe_catalog_for_operators(client)
    usable = [r["universe_name"] for r in catalog if r.get("has_membership_rows")]
    print(
        json_lib.dumps(
            {
                "ok": True,
                "instructions_ko": (
                    "`use_for_phase17_cli`에 나온 문자열을 **그대로** `--universe`에 넣으세요. "
                    "README의 YOUR_UNIVERSE_NAME 은 자리 표시자일 뿐 실제 DB 키가 아닙니다. "
                    "`combined_largecap_research_v1`은 멤버십 테이블에 행이 없을 수 있으며, "
                    "그때는 보통 `sp500_current`를 씁니다."
                ),
                "canonical_strings_in_codebase": list(ALL_RESEARCH_SLICES),
                "use_for_phase17_cli": usable,
                "catalog": catalog,
            },
            indent=2,
            ensure_ascii=False,
            default=str,
        )
    )
    return 0


def _cmd_smoke_phase17_public_depth(_args: argparse.Namespace) -> int:
    from db.client import get_supabase_client
    from db.records import smoke_phase17_public_depth_tables

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    smoke_phase17_public_depth_tables(client)
    print(json.dumps({"ok": True, "public_depth_tables": "reachable"}, indent=2))
    return 0


def _cmd_run_public_depth_expansion(args: argparse.Namespace) -> int:
    import json as json_lib

    from public_depth.expansion import run_public_depth_expansion

    settings = load_settings()
    configure_logging()
    out = run_public_depth_expansion(
        settings,
        universe_name=str(args.universe),
        panel_limit=int(args.panel_limit),
        run_validation_panels=bool(args.run_validation_panels),
        run_forward_returns=bool(args.run_forward_returns),
        validation_panel_limit=int(args.validation_panel_limit),
        forward_panel_limit=int(args.forward_panel_limit),
        max_universe_factor_builds=int(args.max_universe_factor_builds),
    )
    print(json_lib.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0 if out.get("ok") else 1


def _cmd_report_public_depth_coverage(args: argparse.Namespace) -> int:
    import json as json_lib

    from db.client import get_supabase_client
    from db import records as dbrec
    from public_depth.constants import POLICY_VERSION
    from public_depth.diagnostics import compute_substrate_coverage

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    metrics, excl = compute_substrate_coverage(
        client,
        universe_name=str(args.universe),
        panel_limit=int(args.panel_limit),
    )
    result: dict = {"ok": True, "metrics": metrics, "exclusion_distribution": excl}
    if getattr(args, "persist", False):
        rid = dbrec.insert_public_depth_coverage_report(
            client,
            {
                "public_depth_run_id": None,
                "universe_name": str(args.universe),
                "snapshot_label": "standalone",
                "metrics_json": metrics,
                "exclusion_distribution_json": excl,
            },
        )
        result["persisted_report_id"] = rid
        result["policy_version_note"] = POLICY_VERSION
    print(json_lib.dumps(result, indent=2, ensure_ascii=False, default=str))
    return 0


def _cmd_report_quality_uplift(args: argparse.Namespace) -> int:
    import json as json_lib

    from db.client import get_supabase_client
    from db import records as dbrec
    from public_depth.uplift import compute_uplift_metrics

    bad = _exit_unless_uuid("before_report_id", args.before_report_id)
    if bad is not None:
        return bad
    bad = _exit_unless_uuid("after_report_id", args.after_report_id)
    if bad is not None:
        return bad

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    br = dbrec.fetch_public_depth_coverage_report(
        client, report_id=str(args.before_report_id)
    )
    ar = dbrec.fetch_public_depth_coverage_report(
        client, report_id=str(args.after_report_id)
    )
    if not br or not ar:
        print(
            json_lib.dumps(
                {
                    "ok": False,
                    "error": "coverage_report_not_found",
                    "before_found": bool(br),
                    "after_found": bool(ar),
                },
                indent=2,
            )
        )
        return 1
    bm = br.get("metrics_json") if isinstance(br.get("metrics_json"), dict) else {}
    am = ar.get("metrics_json") if isinstance(ar.get("metrics_json"), dict) else {}
    uplift = compute_uplift_metrics(bm, am)
    out: dict = {"ok": True, "uplift": uplift}
    if getattr(args, "persist", False):
        uid = dbrec.insert_public_depth_uplift_report(
            client,
            {
                "before_report_id": str(args.before_report_id),
                "after_report_id": str(args.after_report_id),
                "uplift_metrics_json": uplift,
            },
        )
        out["persisted_uplift_id"] = uid
    print(json_lib.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0


def _cmd_report_research_readiness(args: argparse.Namespace) -> int:
    import json as json_lib

    from db.client import get_supabase_client
    from public_depth.readiness import build_research_readiness_summary

    bad = _exit_unless_uuid("program_id", args.program_id)
    if bad is not None:
        return bad

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    out = build_research_readiness_summary(client, program_id=str(args.program_id))
    print(json_lib.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0 if out.get("ok") else 1


def _cmd_export_public_depth_brief(args: argparse.Namespace) -> int:
    import json as json_lib
    from pathlib import Path

    from db.client import get_supabase_client
    from public_depth.diagnostics import compute_substrate_coverage
    from public_depth.readiness import build_research_readiness_summary

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    if getattr(args, "program_id", None):
        bad = _exit_unless_uuid("program_id", args.program_id)
        if bad is not None:
            return bad
        payload = build_research_readiness_summary(
            client, program_id=str(args.program_id)
        )
    elif getattr(args, "universe", None):
        m, ex = compute_substrate_coverage(
            client, universe_name=str(args.universe), panel_limit=int(args.panel_limit)
        )
        payload = {
            "ok": True,
            "universe_name": str(args.universe),
            "metrics": m,
            "exclusion_distribution": ex,
        }
    else:
        print(
            json_lib.dumps(
                {
                    "ok": False,
                    "error": "need_program_id_or_universe",
                },
                indent=2,
            )
        )
        return 1

    dest = Path(args.out).expanduser()
    dest.parent.mkdir(parents=True, exist_ok=True)
    json_path = dest if dest.suffix == ".json" else dest.with_suffix(".json")
    md_path = dest if dest.suffix == ".md" else dest.with_suffix(".md")
    json_path.write_text(
        json_lib.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    md_lines = [
        "# Public depth brief",
        "",
        "```json",
        json_lib.dumps(payload, indent=2, ensure_ascii=False, default=str),
        "```",
        "",
    ]
    md_path.write_text("\n".join(md_lines), encoding="utf-8")
    print(
        json_lib.dumps(
            {"ok": True, "json": str(json_path), "markdown": str(md_path)},
            indent=2,
        )
    )
    return 0 if payload.get("ok", True) else 1


def _cmd_smoke_phase18_public_buildout(_args: argparse.Namespace) -> int:
    import json as json_lib

    from db.client import get_supabase_client
    from db.records import smoke_phase18_public_buildout_tables

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    smoke_phase18_public_buildout_tables(client)
    print(
        json_lib.dumps({"db_phase18_public_buildout": "ok"}, indent=2, ensure_ascii=False)
    )
    return 0


def _cmd_report_public_exclusion_actions(args: argparse.Namespace) -> int:
    import json as json_lib

    from db.client import get_supabase_client
    from db import records as dbrec
    from public_buildout.constants import POLICY_VERSION
    from public_buildout.orchestrator import build_public_exclusion_actions_payload

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    out = build_public_exclusion_actions_payload(
        client,
        universe_name=str(args.universe),
        panel_limit=int(args.panel_limit),
    )
    if getattr(args, "persist", False) and out.get("ok"):
        rid = dbrec.insert_public_exclusion_action_report(
            client,
            {
                "universe_name": str(args.universe),
                "policy_version": POLICY_VERSION,
                "metrics_json": out.get("metrics") or {},
                "exclusion_distribution_json": out.get("exclusion_distribution") or {},
                "action_queue_json": out.get("action_queue") or [],
            },
        )
        out["persisted_report_id"] = rid
    print(json_lib.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0 if out.get("ok") else 1


def _cmd_run_targeted_public_buildout(args: argparse.Namespace) -> int:
    import json as json_lib

    from public_buildout.orchestrator import run_targeted_public_buildout

    settings = load_settings()
    configure_logging()
    out = run_targeted_public_buildout(
        settings,
        universe_name=str(args.universe),
        panel_limit=int(args.panel_limit),
        max_symbols_factor=int(args.max_symbols_factor),
        validation_panel_limit=int(args.validation_panel_limit),
        forward_panel_limit=int(args.forward_panel_limit),
        state_change_limit=int(args.state_change_limit),
        attack_validation=not bool(args.no_attack_validation),
        attack_state_change=not bool(args.no_attack_state_change),
        attack_forward_returns=not bool(args.no_attack_forward_returns),
        dry_run=bool(args.dry_run),
    )
    print(json_lib.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0 if out.get("ok") else 1


def _cmd_report_buildout_improvement(args: argparse.Namespace) -> int:
    import json as json_lib

    from db.client import get_supabase_client
    from db import records as dbrec
    from public_buildout.orchestrator import report_buildout_improvement_from_coverage_ids

    before_id: str | None = getattr(args, "before_report_id", None)
    after_id: str | None = getattr(args, "after_report_id", None)

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)

    if getattr(args, "from_latest_pair", False):
        uni = getattr(args, "universe", None)
        if not uni or not str(uni).strip():
            print(
                json_lib.dumps(
                    {
                        "ok": False,
                        "error": "universe_required_with_from_latest_pair",
                    },
                    indent=2,
                )
            )
            return 1
        rows = dbrec.list_public_depth_coverage_reports_for_universe(
            client, universe_name=str(uni).strip(), limit=2
        )
        if len(rows) < 2:
            print(
                json_lib.dumps(
                    {
                        "ok": False,
                        "error": "need_at_least_two_persisted_coverage_reports",
                        "universe_name": str(uni).strip(),
                        "found_count": len(rows),
                        "hint": "같은 유니버스로 report-public-depth-coverage --persist 를 "
                        "전·후 두 번 실행한 뒤 다시 시도하세요.",
                    },
                    indent=2,
                    ensure_ascii=False,
                )
            )
            return 1
        after_id = str(rows[0]["id"])
        before_id = str(rows[1]["id"])
    else:
        if not before_id or not after_id:
            print(
                json_lib.dumps(
                    {
                        "ok": False,
                        "error": "before_after_ids_or_from_latest_pair_required",
                        "hint": "수동: --before-report-id 와 --after-report-id. "
                        "자동: --universe U --from-latest-pair (최신 2건: 이전=before, 최신=after).",
                    },
                    indent=2,
                    ensure_ascii=False,
                )
            )
            return 1
        bad = _exit_unless_uuid("before_report_id", before_id)
        if bad is not None:
            return bad
        bad = _exit_unless_uuid("after_report_id", after_id)
        if bad is not None:
            return bad

    out = report_buildout_improvement_from_coverage_ids(
        client,
        before_report_id=str(before_id),
        after_report_id=str(after_id),
    )
    if getattr(args, "from_latest_pair", False):
        out["resolved_before_report_id"] = str(before_id)
        out["resolved_after_report_id"] = str(after_id)
        out["universe_name"] = str(getattr(args, "universe", "") or "").strip()
    if getattr(args, "persist", False) and out.get("ok"):
        br = dbrec.fetch_public_depth_coverage_report(
            client, report_id=str(before_id)
        )
        ar = dbrec.fetch_public_depth_coverage_report(
            client, report_id=str(after_id)
        )
        bm = br.get("metrics_json") if isinstance(br, dict) else {}
        am = ar.get("metrics_json") if isinstance(ar, dict) else {}
        bex = br.get("exclusion_distribution_json") if isinstance(br, dict) else {}
        aex = ar.get("exclusion_distribution_json") if isinstance(ar, dict) else {}
        uid = dbrec.insert_public_buildout_improvement_report(
            client,
            {
                "public_buildout_run_id": None,
                "before_metrics_json": bm if isinstance(bm, dict) else {},
                "after_metrics_json": am if isinstance(am, dict) else {},
                "exclusion_before_json": bex if isinstance(bex, dict) else {},
                "exclusion_after_json": aex if isinstance(aex, dict) else {},
                "improvement_summary_json": out.get("improvement") or {},
            },
        )
        out["persisted_improvement_id"] = uid
    print(json_lib.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0 if out.get("ok") else 1


def _cmd_report_revalidation_trigger(args: argparse.Namespace) -> int:
    import json as json_lib

    from db.client import get_supabase_client
    from public_buildout.revalidation import build_revalidation_trigger

    bad = _exit_unless_uuid("program_id", args.program_id)
    if bad is not None:
        return bad

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    out = build_revalidation_trigger(client, program_id=str(args.program_id))
    print(json_lib.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0 if out.get("ok") else 1


def _cmd_export_buildout_brief(args: argparse.Namespace) -> int:
    import json as json_lib
    from pathlib import Path

    from db.client import get_supabase_client
    from public_buildout.orchestrator import build_public_exclusion_actions_payload
    from public_buildout.revalidation import build_revalidation_trigger

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    base = build_public_exclusion_actions_payload(
        client,
        universe_name=str(args.universe),
        panel_limit=int(args.panel_limit),
    )
    payload: dict = {"ok": True, "exclusion_actions": base}
    if getattr(args, "program_id", None):
        bad = _exit_unless_uuid("program_id", args.program_id)
        if bad is not None:
            return bad
        payload["revalidation"] = build_revalidation_trigger(
            client, program_id=str(args.program_id)
        )
    dest = Path(args.out).expanduser()
    dest.parent.mkdir(parents=True, exist_ok=True)
    json_path = dest if dest.suffix == ".json" else dest.with_suffix(".json")
    md_path = dest if dest.suffix == ".md" else dest.with_suffix(".md")
    json_path.write_text(
        json_lib.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    md_lines = [
        "# Public build-out brief (Phase 18)",
        "",
        "```json",
        json_lib.dumps(payload, indent=2, ensure_ascii=False, default=str),
        "```",
        "",
    ]
    md_path.write_text("\n".join(md_lines), encoding="utf-8")
    print(
        json_lib.dumps(
            {"ok": True, "json": str(json_path), "markdown": str(md_path)},
            indent=2,
        )
    )
    return 0


def _cmd_smoke_phase19_public_repair_campaign(_args: argparse.Namespace) -> int:
    import json as json_lib

    from db.client import get_supabase_client
    from db.records import smoke_phase19_public_repair_campaign_tables

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    smoke_phase19_public_repair_campaign_tables(client)
    print(
        json_lib.dumps({"db_phase19_public_repair_campaign": "ok"}, indent=2, ensure_ascii=False)
    )
    return 0


def _cmd_run_public_repair_campaign(args: argparse.Namespace) -> int:
    import json as json_lib

    from db.client import get_supabase_client
    from public_repair_campaign.service import run_public_repair_campaign

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    pid, err = _resolve_program_id_cli(client, args)
    if err is not None:
        return err

    uni = getattr(args, "universe", None)
    out = run_public_repair_campaign(
        settings,
        program_id=str(pid),
        universe_name=str(uni).strip() if uni else None,
        dry_run_buildout=bool(args.dry_run_buildout),
        skip_reruns=bool(args.skip_reruns),
        panel_limit=int(args.panel_limit),
        campaign_panel_limit=int(args.campaign_panel_limit),
        max_symbols_factor=int(args.max_symbols_factor),
        validation_panel_limit=int(args.validation_panel_limit),
        forward_panel_limit=int(args.forward_panel_limit),
        state_change_limit=int(args.state_change_limit),
    )
    print(json_lib.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0 if out.get("ok") else 1


def _cmd_report_public_repair_campaign(args: argparse.Namespace) -> int:
    import json as json_lib

    from db.client import get_supabase_client
    from public_repair_campaign.service import report_public_repair_campaign

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    rcid, err = _resolve_repair_campaign_id_cli(client, args)
    if err is not None:
        return err

    out = report_public_repair_campaign(
        client, repair_campaign_run_id=str(rcid)
    )
    print(json_lib.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0 if out.get("ok") else 1


def _cmd_compare_repair_revalidation_outcomes(args: argparse.Namespace) -> int:
    import json as json_lib

    from db.client import get_supabase_client
    from public_repair_campaign.service import compare_repair_revalidation_outcomes

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    rcid, err = _resolve_repair_campaign_id_cli(client, args)
    if err is not None:
        return err

    out = compare_repair_revalidation_outcomes(
        client, repair_campaign_run_id=str(rcid)
    )
    print(json_lib.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0 if out.get("ok") else 1


def _cmd_export_public_repair_decision_brief(args: argparse.Namespace) -> int:
    import json as json_lib
    from pathlib import Path

    from db.client import get_supabase_client
    from public_repair_campaign.service import export_public_repair_decision_brief

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    rcid, err = _resolve_repair_campaign_id_cli(
        client, args, latest_success=True
    )
    if err is not None:
        return err

    out = export_public_repair_decision_brief(
        client, repair_campaign_run_id=str(rcid)
    )
    if not out.get("ok"):
        print(json_lib.dumps(out, indent=2, ensure_ascii=False, default=str))
        return 1
    dest = Path(args.out).expanduser()
    dest.parent.mkdir(parents=True, exist_ok=True)
    json_path = dest if dest.suffix == ".json" else dest.with_suffix(".json")
    md_path = dest if dest.suffix == ".md" else dest.with_suffix(".md")
    brief = out["brief"]
    json_path.write_text(
        json_lib.dumps(brief, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    md_path.write_text(str(out.get("markdown") or ""), encoding="utf-8")
    print(
        json_lib.dumps(
            {"ok": True, "json": str(json_path), "markdown": str(md_path)},
            indent=2,
        )
    )
    return 0


def _cmd_list_repair_campaigns(args: argparse.Namespace) -> int:
    import json as json_lib

    from db.client import get_supabase_client
    from public_repair_campaign.service import list_repair_campaigns

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    pid, err = _resolve_program_id_cli(client, args)
    if err is not None:
        return err

    out = list_repair_campaigns(
        client, program_id=str(pid), limit=int(args.limit)
    )
    print(json_lib.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0 if out.get("ok") else 1


def _cmd_smoke_phase20_repair_iteration(_args: argparse.Namespace) -> int:
    import json as json_lib

    from db.client import get_supabase_client
    from db.records import smoke_phase20_repair_iteration_tables

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    smoke_phase20_repair_iteration_tables(client)
    print(
        json_lib.dumps({"db_phase20_repair_iteration": "ok"}, indent=2, ensure_ascii=False)
    )
    return 0


def _cmd_run_public_repair_iteration(args: argparse.Namespace) -> int:
    import json as json_lib

    from db.client import get_supabase_client
    from public_repair_iteration.service import run_public_repair_iteration

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    pid, err = _resolve_program_id_cli(client, args)
    if err is not None:
        return err

    uni = getattr(args, "universe", None)
    out = run_public_repair_iteration(
        settings,
        program_id=str(pid),
        universe_name=str(uni).strip() if uni else None,
        dry_run_buildout=bool(args.dry_run_buildout),
        skip_reruns=bool(args.skip_reruns),
        panel_limit=int(args.panel_limit),
        campaign_panel_limit=int(args.campaign_panel_limit),
        max_symbols_factor=int(args.max_symbols_factor),
        validation_panel_limit=int(args.validation_panel_limit),
        forward_panel_limit=int(args.forward_panel_limit),
        state_change_limit=int(args.state_change_limit),
    )
    print(json_lib.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0 if out.get("ok") else 1


def _cmd_report_public_repair_iteration_history(args: argparse.Namespace) -> int:
    import json as json_lib

    from db.client import get_supabase_client
    from public_repair_iteration.service import (
        report_public_repair_iteration_history,
        report_public_repair_iteration_history_for_program,
    )

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    sid = getattr(args, "series_id", None)
    if sid and str(sid).strip():
        bad = _exit_unless_uuid("series_id", str(sid).strip())
        if bad is not None:
            return bad
        out = report_public_repair_iteration_history(
            client, series_id=str(sid).strip()
        )
    else:
        if not getattr(args, "program_id", None):
            print(
                json_lib.dumps(
                    {
                        "ok": False,
                        "error": "program_id_or_series_id_required",
                        "hint": "Use --series-id <UUID> or --program-id <UUID|latest>.",
                    },
                    indent=2,
                    ensure_ascii=False,
                )
            )
            return 1
        pid, err = _resolve_program_id_cli(client, args)
        if err is not None:
            return err
        out = report_public_repair_iteration_history_for_program(
            client, program_id=str(pid)
        )
    print(json_lib.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0 if out.get("ok") else 1


def _cmd_report_public_repair_plateau(args: argparse.Namespace) -> int:
    import json as json_lib

    from db.client import get_supabase_client
    from public_repair_iteration.service import (
        compute_public_repair_plateau,
        resolve_active_series_for_program,
    )

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    pid, err = _resolve_program_id_cli(client, args)
    if err is not None:
        return err

    sr = resolve_active_series_for_program(client, program_id=str(pid))
    if not sr.get("ok"):
        print(json_lib.dumps(sr, indent=2, ensure_ascii=False))
        return 1
    out = compute_public_repair_plateau(
        client,
        series_id=str(sr["series_id"]),
        exclude_infra_default=not bool(args.include_infra_failed_runs),
    )
    print(json_lib.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0 if out.get("ok") else 1


def _cmd_export_public_repair_escalation_brief(args: argparse.Namespace) -> int:
    import json as json_lib
    from pathlib import Path

    from db.client import get_supabase_client
    from public_repair_iteration.service import (
        export_public_repair_escalation_brief,
        resolve_active_series_for_program,
    )

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    pid, err = _resolve_program_id_cli(client, args)
    if err is not None:
        return err

    sr = resolve_active_series_for_program(client, program_id=str(pid))
    if not sr.get("ok"):
        print(json_lib.dumps(sr, indent=2, ensure_ascii=False))
        return 1
    out = export_public_repair_escalation_brief(
        client, series_id=str(sr["series_id"])
    )
    if not out.get("ok"):
        print(json_lib.dumps(out, indent=2, ensure_ascii=False, default=str))
        return 1
    dest = Path(args.out).expanduser()
    dest.parent.mkdir(parents=True, exist_ok=True)
    json_path = dest if dest.suffix == ".json" else dest.with_suffix(".json")
    md_path = dest if dest.suffix == ".md" else dest.with_suffix(".md")
    brief = out["brief"]
    json_path.write_text(
        json_lib.dumps(brief, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    md_path.write_text(str(out.get("markdown") or ""), encoding="utf-8")
    print(
        json_lib.dumps(
            {"ok": True, "json": str(json_path), "markdown": str(md_path)},
            indent=2,
        )
    )
    return 0


def _cmd_list_public_repair_series(args: argparse.Namespace) -> int:
    import json as json_lib

    from db.client import get_supabase_client
    from public_repair_iteration.service import list_public_repair_series

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    pid, err = _resolve_program_id_cli(client, args)
    if err is not None:
        return err

    out = list_public_repair_series(
        client, program_id=str(pid), limit=int(args.limit)
    )
    print(json_lib.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0 if out.get("ok") else 1


def _cmd_report_latest_repair_state(args: argparse.Namespace) -> int:
    import json as json_lib

    from db.client import get_supabase_client
    from public_repair_iteration.service import report_latest_repair_state

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    pid, err = _resolve_program_id_cli(client, args)
    if err is not None:
        return err

    out = report_latest_repair_state(client, program_id=str(pid))
    print(json_lib.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0 if out.get("ok") else 1


def _cmd_report_premium_discovery_readiness(args: argparse.Namespace) -> int:
    import json as json_lib

    from db.client import get_supabase_client
    from public_repair_iteration.service import (
        compute_public_repair_plateau,
        resolve_active_series_for_program,
    )

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    pid, err = _resolve_program_id_cli(client, args)
    if err is not None:
        return err

    sr = resolve_active_series_for_program(client, program_id=str(pid))
    if not sr.get("ok"):
        print(json_lib.dumps({**sr, "premium_discovery_ready": False}, indent=2))
        return 1
    plateau = compute_public_repair_plateau(
        client, series_id=str(sr["series_id"])
    )
    rec = str(plateau.get("escalation_recommendation") or "")
    ready = rec == "open_targeted_premium_discovery"
    print(
        json_lib.dumps(
            {
                "ok": plateau.get("ok"),
                "premium_discovery_ready": ready,
                "escalation_recommendation": rec,
                "plateau_report": plateau,
            },
            indent=2,
            ensure_ascii=False,
            default=str,
        )
    )
    return 0 if plateau.get("ok") else 1


def _cmd_smoke_phase21_iteration_governance(_args: argparse.Namespace) -> int:
    import json as json_lib

    from db.client import get_supabase_client
    from db.records import smoke_phase21_iteration_governance

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    smoke_phase21_iteration_governance(client)
    print(
        json_lib.dumps(
            {"db_phase21_iteration_governance": "ok"},
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


def _cmd_pause_public_repair_series(args: argparse.Namespace) -> int:
    import json as json_lib

    from db.client import get_supabase_client
    from public_repair_iteration.service import pause_public_repair_series

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    bad = _exit_unless_uuid("series_id", str(args.series_id).strip())
    if bad is not None:
        return bad
    out = pause_public_repair_series(
        client,
        series_id=str(args.series_id).strip(),
        reason=str(args.reason or "").strip() or "operator_pause",
    )
    print(json_lib.dumps(out, indent=2, ensure_ascii=False))
    return 0 if out.get("ok") else 1


def _cmd_resume_public_repair_series(args: argparse.Namespace) -> int:
    import json as json_lib

    from db.client import get_supabase_client
    from public_repair_iteration.service import resume_public_repair_series

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    bad = _exit_unless_uuid("series_id", str(args.series_id).strip())
    if bad is not None:
        return bad
    out = resume_public_repair_series(
        client,
        series_id=str(args.series_id).strip(),
        audit_note=str(args.audit_note or "").strip(),
    )
    print(json_lib.dumps(out, indent=2, ensure_ascii=False))
    return 0 if out.get("ok") else 1


def _cmd_close_public_repair_series(args: argparse.Namespace) -> int:
    import json as json_lib

    from db.client import get_supabase_client
    from public_repair_iteration.service import close_public_repair_series

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    bad = _exit_unless_uuid("series_id", str(args.series_id).strip())
    if bad is not None:
        return bad
    out = close_public_repair_series(
        client,
        series_id=str(args.series_id).strip(),
        reason=str(args.reason or "").strip() or "operator_close",
    )
    print(json_lib.dumps(out, indent=2, ensure_ascii=False))
    return 0 if out.get("ok") else 1


def _cmd_advance_public_repair_series(args: argparse.Namespace) -> int:
    import json as json_lib
    from pathlib import Path

    from db.client import get_supabase_client
    from public_repair_iteration.service import advance_public_repair_series

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    pid, err = _resolve_program_id_cli(client, args)
    if err is not None:
        return err
    uni = getattr(args, "universe", None)
    series_override = getattr(args, "series_id", None)
    so = str(series_override).strip() if series_override else None
    if so:
        bad = _exit_unless_uuid("series_id", so)
        if bad is not None:
            return bad
    run_campaign = not bool(args.attach_only)
    attach_raw = str(getattr(args, "attach_repair_run_id", "") or "").strip()
    attach = attach_raw if attach_raw else None
    out = advance_public_repair_series(
        settings,
        program_id=str(pid),
        universe_name=str(uni).strip() if uni else None,
        series_id_override=so,
        attach_repair_run_id=attach,
        run_new_campaign=run_campaign,
        dry_run_buildout=bool(args.dry_run_buildout),
        skip_reruns=bool(args.skip_reruns),
        panel_limit=int(args.panel_limit),
        campaign_panel_limit=int(args.campaign_panel_limit),
        max_symbols_factor=int(args.max_symbols_factor),
        validation_panel_limit=int(args.validation_panel_limit),
        forward_panel_limit=int(args.forward_panel_limit),
        state_change_limit=int(args.state_change_limit),
    )
    if not out.get("ok"):
        print(json_lib.dumps(out, indent=2, ensure_ascii=False, default=str))
        return 1
    dest = Path(args.out).expanduser()
    dest.parent.mkdir(parents=True, exist_ok=True)
    json_path = dest if dest.suffix == ".json" else dest.with_suffix(".json")
    md_path = dest if dest.suffix == ".md" else dest.with_suffix(".md")
    brief = out.get("brief") or {}
    json_path.write_text(
        json_lib.dumps(brief, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    md_path.write_text(str(out.get("markdown") or ""), encoding="utf-8")
    print(str(out.get("operator_summary") or ""))
    print(
        json_lib.dumps(
            {
                "ok": True,
                "json": str(json_path),
                "markdown": str(md_path),
                "iteration_append": out.get("iteration_append"),
                "escalation_recommendation": out.get("escalation_recommendation"),
            },
            indent=2,
            ensure_ascii=False,
            default=str,
        )
    )
    return 0


def _cmd_resolve_repair_campaign_pair(args: argparse.Namespace) -> int:
    import json as json_lib

    from db.client import get_supabase_client
    from public_repair_iteration.resolver import resolve_repair_campaign_latest_pair
    from public_repair_iteration.service import resolve_active_series_for_program

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    pid, err = _resolve_program_id_cli(client, args)
    if err is not None:
        return err
    series = None
    if args.compatible:
        sr = resolve_active_series_for_program(client, program_id=str(pid))
        if not sr.get("ok"):
            print(json_lib.dumps(sr, indent=2, ensure_ascii=False))
            return 1
        series = sr.get("series")
    out = resolve_repair_campaign_latest_pair(
        client,
        program_id=str(pid),
        series=series,
        compatible=bool(args.compatible),
    )
    print(json_lib.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0 if out.get("ok") else 1


def _cmd_report_public_core_cycle(args: argparse.Namespace) -> int:
    from pathlib import Path

    from public_core.cycle import default_cycle_out_dir, load_latest_cycle_summary

    base = Path(args.out_dir).expanduser() if args.out_dir else default_cycle_out_dir()
    summary = load_latest_cycle_summary(base=base)
    if not summary:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "no_cycle_summary",
                    "hint": f"Run run-public-core-cycle first (writes {base / 'cycle_summary.json'})",
                },
                indent=2,
            )
        )
        return 1
    print(json.dumps(summary, indent=2, ensure_ascii=False, default=str))
    return 0


def _cmd_smoke_facts(_args: argparse.Namespace) -> int:
    """DB facts 테이블 도달 + (선택) 단일 티커 XBRL 로드 가능 여부."""
    import sec.ingest_company_sample  # noqa: F401

    from db.client import get_supabase_client
    from db.records import smoke_facts_db
    from sec.facts.extract_facts import extract_facts_for_ticker

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    smoke_facts_db(client)
    ex = extract_facts_for_ticker("AAPL", settings.edgar_identity)
    out = {
        "db_facts_table": "ok",
        "xbrl_probe": {
            "ok": ex.get("ok"),
            "raw_fact_count": ex.get("raw_fact_count"),
            "accession_no": ex.get("accession_no"),
        },
    }
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0 if ex.get("ok") else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="GenAIProacTrade SEC / XBRL worker CLI")
    sub = p.add_subparsers(dest="command", required=True)

    p1 = sub.add_parser("ingest-single", help="단일 티커 최근 공시 ingest")
    p1.add_argument("--ticker", required=True, help="예: NVDA")
    p1.set_defaults(func=_cmd_ingest_single)

    p2 = sub.add_parser("ingest-watchlist", help="config/watchlist.json 기반 배치 ingest")
    p2.add_argument(
        "--watchlist",
        default=None,
        help="JSON 경로 (기본: 프로젝트 config/watchlist.json 또는 WATCHLIST_PATH)",
    )
    p2.add_argument(
        "--sleep",
        type=float,
        default=float(os.getenv("INGEST_TICKER_SLEEP_SEC", "0.65")),
        help="티커 간 대기 초 (rate limit)",
    )
    p2.set_defaults(func=_cmd_ingest_watchlist)

    p3 = sub.add_parser("smoke-sec", help="edgartools + SEC 연결 스모크")
    p3.set_defaults(func=_cmd_smoke_sec)

    p4 = sub.add_parser("smoke-db", help="Supabase 연결 스모크")
    p4.set_defaults(func=_cmd_smoke_db)

    p5 = sub.add_parser("extract-facts-single", help="단일 티커 최근 10-Q/10-K XBRL facts 추출·적재")
    p5.add_argument("--ticker", required=True)
    p5.add_argument(
        "--forms",
        default=None,
        help="쉼표 구분, 예: 10-Q,10-K (기본: 10-Q,10-K)",
    )
    p5.set_defaults(func=_cmd_extract_facts_single)

    p6 = sub.add_parser("extract-facts-watchlist", help="워치리스트 티커별 facts 추출·적재")
    p6.add_argument("--watchlist", default=None)
    p6.add_argument(
        "--sleep",
        type=float,
        default=float(os.getenv("INGEST_TICKER_SLEEP_SEC", "0.65")),
    )
    p6.add_argument("--forms", default=None, help="쉼표 구분 form 목록")
    p6.set_defaults(func=_cmd_extract_facts_watchlist)

    p7 = sub.add_parser(
        "build-quarter-snapshots",
        help="DB silver_xbrl_facts 기준 분기 스냅샷 재계산",
    )
    p7.add_argument("--ticker", default=None, help="issuer_master 티커로 CIK 한정")
    p7.add_argument("--limit", type=int, default=20, help="처리할 고유 (cik, accession) 상한")
    p7.set_defaults(func=_cmd_build_quarter_snapshots)

    p8 = sub.add_parser("smoke-facts", help="facts 테이블 + SEC XBRL 프로브 (네트워크)")
    p8.set_defaults(func=_cmd_smoke_facts)

    p9 = sub.add_parser("compute-factors-single", help="단일 티커 스냅샷 → factor panel 적재")
    p9.add_argument("--ticker", required=True)
    p9.add_argument(
        "--factor-version",
        default=None,
        help="기본 v1 또는 환경변수 FACTOR_VERSION",
    )
    p9.set_defaults(func=_cmd_compute_factors_single)

    p10 = sub.add_parser("compute-factors-watchlist", help="워치리스트 티커별 factor panel 적재")
    p10.add_argument(
        "--watchlist",
        default=None,
        help="tickers가 든 JSON 경로. 생략 시 WATCHLIST_PATH, 둘 다 없으면 config/watchlist.json",
    )
    p10.add_argument(
        "--sleep",
        type=float,
        default=float(os.getenv("INGEST_TICKER_SLEEP_SEC", "0.65")),
    )
    p10.add_argument("--factor-version", default=None)
    p10.set_defaults(func=_cmd_compute_factors_watchlist)

    p11 = sub.add_parser(
        "smoke-factors",
        help="issuer_quarter_factor_panels 테이블 + accruals 공식 sanity (DB 필요)",
    )
    p11.set_defaults(func=_cmd_smoke_factors_phase3)

    p12 = sub.add_parser("show-factor-panel", help="티커별 최근 factor panel 조회")
    p12.add_argument("--ticker", required=True)
    p12.add_argument("--limit", type=int, default=5)
    p12.set_defaults(func=_cmd_show_factor_panel)

    pu = sub.add_parser(
        "refresh-universe",
        help="S&P 500 current → universe_memberships (네트워크: 위키/프로바이더)",
    )
    pu.add_argument(
        "--universe",
        default="sp500_current",
        help="현재는 sp500_current 만 지원",
    )
    pu.set_defaults(func=_cmd_refresh_universe)

    pun = sub.add_parser(
        "list-universe-names",
        help="DB·프로그램 기준 universe_name 목록(Phase 17 등 --universe 값 확인용)",
    )
    pun.set_defaults(func=_cmd_list_universe_names)

    pc = sub.add_parser(
        "build-candidate-universe",
        help="sp500_proxy_candidates_v1 시드 기반 후보 유니버스 (공식 후보 아님)",
    )
    pc.add_argument(
        "--seed",
        default=None,
        help="JSON 시드 경로 (기본: config/sp500_proxy_candidates_v1.json)",
    )
    pc.set_defaults(func=_cmd_build_candidate_universe)

    pp = sub.add_parser(
        "ingest-market-prices",
        help="유니버스 심볼 일봉 → raw/silver (프로바이더 네트워크)",
    )
    pp.add_argument(
        "--universe",
        required=True,
        help="sp500_current | sp500_proxy_candidates_v1",
    )
    pp.add_argument("--start", default=None, help="YYYY-MM-DD (선택)")
    pp.add_argument("--end", default=None, help="YYYY-MM-DD (선택)")
    pp.add_argument(
        "--lookback-days",
        type=int,
        default=int(os.getenv("MARKET_PRICE_LOOKBACK_DAYS", "400")),
    )
    pp.set_defaults(func=_cmd_ingest_market_prices)

    pm = sub.add_parser(
        "refresh-market-metadata",
        help="프로바이더 메타(있을 때만) → market_metadata_latest",
    )
    pm.add_argument("--universe", required=True)
    pm.set_defaults(func=_cmd_refresh_market_metadata)

    pr = sub.add_parser(
        "ingest-risk-free",
        help="FRED DTB3 CSV → risk_free_rates_daily (네트워크)",
    )
    pr.add_argument("--start", default=None, help="YYYY-MM-DD")
    pr.add_argument("--end", default=None, help="YYYY-MM-DD")
    pr.add_argument("--lookback-years", type=int, default=3)
    pr.add_argument(
        "--fred-timeout",
        type=int,
        default=240,
        help="FRED CSV httpx read 타임아웃(초). 느린 네트워크면 300~600",
    )
    pr.add_argument(
        "--fred-retries",
        type=int,
        default=3,
        help="FRED 다운로드 실패 시 재시도 횟수",
    )
    pr.set_defaults(func=_cmd_ingest_risk_free)

    pf = sub.add_parser(
        "build-forward-returns",
        help="factor panels + silver 가격 + 무위험 → forward_returns_daily_horizons",
    )
    pf.add_argument("--limit-panels", type=int, default=2000)
    pf.add_argument("--price-lookahead-days", type=int, default=400)
    pf.set_defaults(func=_cmd_build_forward_returns)

    pv = sub.add_parser(
        "build-validation-panel",
        help="factor + forward + 메타 → factor_market_validation_panels",
    )
    pv.add_argument("--limit-panels", type=int, default=2000)
    pv.set_defaults(func=_cmd_build_validation_panel)

    sm = sub.add_parser(
        "smoke-market",
        help="Phase 4 시장 테이블 + 스텁 프로바이더 형태 (DB 필요)",
    )
    sm.set_defaults(func=_cmd_smoke_market)

    sv = sub.add_parser("smoke-validation", help="validation 패널 테이블 도달 (DB 필요)")
    sv.set_defaults(func=_cmd_smoke_validation)

    prv = sub.add_parser(
        "run-factor-validation",
        help="Phase 5: factor_market_validation_panels 기반 기술 검증 적재 (연구용)",
    )
    prv.add_argument(
        "--universe",
        required=True,
        help="sp500_current | sp500_proxy_candidates_v1 | combined_largecap_research_v1",
    )
    prv.add_argument(
        "--horizon",
        required=True,
        choices=("next_month", "next_quarter"),
        help="선행 지평",
    )
    prv.add_argument("--factor-version", default="v1")
    prv.add_argument("--panel-limit", type=int, default=8000)
    prv.add_argument(
        "--ols",
        action="store_true",
        help="단순 OLS 보조 요약(summary_json); robust/FM 미구현",
    )
    prv.add_argument(
        "--winsorize",
        action="store_true",
        help="팩터 winsorize(1%%/99%%) 후 상관·분위",
    )
    prv.add_argument("--n-quantiles", type=int, default=5)
    prv.set_defaults(func=_cmd_run_factor_validation)

    prp = sub.add_parser(
        "report-factor-summary",
        help="최근 completed 검증 run 기준 터미널 요약 (투자 추천 아님)",
    )
    prp.add_argument("--factor", required=True, help="예: accruals")
    prp.add_argument("--universe", required=True)
    prp.add_argument(
        "--horizon",
        required=True,
        choices=("next_month", "next_quarter"),
    )
    prp.add_argument(
        "--return-basis",
        default="raw",
        choices=("raw", "excess"),
    )
    prp.set_defaults(func=_cmd_report_factor_summary)

    srr = sub.add_parser(
        "smoke-research",
        help="Phase 5 factor_validation_* 테이블 도달 (DB·마이그레이션 필요)",
    )
    srr.set_defaults(func=_cmd_smoke_research)

    psc = sub.add_parser(
        "run-state-change",
        help="Phase 6: deterministic issuer-date state change (검증 패널·선행수익 미입력)",
    )
    psc.add_argument(
        "--universe",
        required=True,
        help="sp500_current | sp500_proxy_candidates_v1 | combined_largecap_research_v1",
    )
    psc.add_argument("--factor-version", default=None)
    psc.add_argument("--as-of-date", default=None, help="단일 as_of_date 필터 YYYY-MM-DD")
    psc.add_argument("--start-date", default=None)
    psc.add_argument("--end-date", default=None)
    psc.add_argument("--limit", type=int, default=200, help="처리 issuer 상한")
    psc.add_argument("--dry-run", action="store_true")
    psc.add_argument(
        "--include-nullable-overlays",
        action="store_true",
        help="contamination 등 nullable 오버레이 메타 포함(점수는 여전히 결정적)",
    )
    psc.add_argument(
        "--output-json",
        action="store_true",
        help="전체 결과 JSON; 생략 시 한 줄 요약",
    )
    psc.set_defaults(func=_cmd_run_state_change)

    prs = sub.add_parser(
        "report-state-change-summary",
        help="Phase 6: 최근(또는 지정) state change run 요약",
    )
    prs.add_argument("--run-id", default=None, help="우선 사용할 run UUID")
    prs.add_argument(
        "--universe",
        default=None,
        help="run-id 없을 때 completed 최신 run 조회용 유니버스명",
    )
    prs.add_argument("--scores-limit", type=int, default=15)
    prs.add_argument("--candidates-limit", type=int, default=20)
    prs.add_argument("--output-json", action="store_true")
    prs.set_defaults(func=_cmd_report_state_change_summary)

    ssc = sub.add_parser(
        "smoke-state-change",
        help="Phase 6 state_change_* 테이블 도달 (DB·마이그레이션 필요)",
    )
    ssc.set_defaults(func=_cmd_smoke_state_change)

    sbk = sub.add_parser(
        "smoke-backfill",
        help="backfill_orchestration_* 테이블 도달 (DB·마이그레이션 필요)",
    )
    sbk.set_defaults(func=_cmd_smoke_backfill)

    bfu = sub.add_parser(
        "backfill-universe",
        help="유니버스 단위 deterministic 백필 (SEC→facts→snapshots→factors→시장→선행→검증패널)",
    )
    bfu.add_argument(
        "--mode",
        required=True,
        choices=("smoke", "pilot", "full", "extended"),
        help="smoke≈5티커, pilot≈pilot JSON∩유니버스, full/extended=유니버스(캡 가능)",
    )
    bfu.add_argument(
        "--universe",
        required=True,
        help="sp500_current | sp500_proxy_candidates_v1 | combined_largecap_research_v1",
    )
    bfu.add_argument(
        "--symbol-limit",
        type=int,
        default=None,
        help="full/extended 에서 처리 상한(미지정 시 유니버스 전체)",
    )
    bfu.add_argument(
        "--start-stage",
        default=None,
        help="resolve|sec|xbrl|snapshots|factors|market_prices|forward_returns|validation_panel|phase5|phase6",
    )
    bfu.add_argument("--end-stage", default=None, help="start-stage 와 동일 집합")
    bfu.add_argument("--dry-run", action="store_true")
    bfu.add_argument(
        "--retry-failed-only",
        action="store_true",
        help="이전 오케스트레이션 summary 의 retry_tickers_all 만 재시도",
    )
    bfu.add_argument(
        "--from-orchestration-run-id",
        default=None,
        dest="from_orchestration_run_id",
        help="retry-failed-only 시 필수",
    )
    bfu.add_argument("--rerun-phase5", action="store_true")
    bfu.add_argument("--rerun-phase6", action="store_true")
    bfu.add_argument(
        "--sleep",
        type=float,
        default=float(os.getenv("INGEST_TICKER_SLEEP_SEC", "0.55")),
    )
    bfu.add_argument("--factor-version", default=None)
    bfu.add_argument(
        "--market-lookback-days",
        type=int,
        default=int(os.getenv("MARKET_PRICE_LOOKBACK_DAYS", "400")),
    )
    bfu.add_argument(
        "--coverage-stage",
        default=None,
        choices=("stage_a", "stage_b", "full"),
        help="결정적 코호트 확장: stage_a≈150·stage_b≈300·full=전체(issuer-target로 캡 가능). "
        "지정 시 티커는 유니버스 정렬 앞쪽부터 채움(--mode full 권장).",
    )
    bfu.add_argument(
        "--issuer-target",
        type=int,
        default=None,
        help="coverage-stage 와 함께: 목표 issuer 수(미지정 시 stage_a=150, stage_b=300, full=전체).",
    )
    bfu.add_argument(
        "--write-coverage-checkpoint",
        default=None,
        metavar="PATH",
        help="완료 시 coverage_checkpoint JSON을 파일로 저장",
    )
    bfu.add_argument("--output-json", action="store_true", help="항상 JSON 출력(기본도 JSON)")
    bfu.set_defaults(func=_cmd_backfill_universe)

    rbs = sub.add_parser(
        "report-backfill-status",
        help="RPC 커버리지·조인 진단·최근 backfill run 요약",
    )
    rbs.add_argument(
        "--mode",
        default="pilot",
        choices=("smoke", "pilot", "full", "extended"),
        help="진단에 쓸 티커 해석 모드",
    )
    rbs.add_argument(
        "--universe",
        default="sp500_current",
        help="sp500_current | sp500_proxy_candidates_v1 | combined_largecap_research_v1",
    )
    rbs.add_argument("--symbol-limit", type=int, default=None)
    rbs.add_argument(
        "--no-diagnostics",
        action="store_true",
        help="조인·thin issuer 조회 생략(빠른 카운트만)",
    )
    rbs.add_argument("--thin-threshold", type=int, default=4)
    rbs.add_argument(
        "--orchestration-run-id",
        default=None,
        help="특정 오케스트레이션 run 상세",
    )
    rbs.add_argument(
        "--write-diagnostics",
        default=None,
        help="join_diagnostics JSON 저장 경로",
    )
    rbs.add_argument(
        "--coverage-stage",
        default=None,
        choices=("stage_a", "stage_b", "full"),
        help="resolve·join_diagnostics 에 staged 코호트 사용",
    )
    rbs.add_argument(
        "--issuer-target",
        type=int,
        default=None,
        help="coverage-stage 와 함께 목표 issuer 수",
    )
    rbs.add_argument(
        "--include-coverage-checkpoint",
        action="store_true",
        help="페이로드에 coverage_checkpoint 포함",
    )
    rbs.add_argument(
        "--include-sparse-diagnostics",
        action="store_true",
        help="페이로드에 sparse_issuer_diagnostics 포함",
    )
    rbs.add_argument(
        "--write-sparse-diagnostics",
        default=None,
        metavar="PATH",
        help="sparse_issuer_diagnostics JSON 저장(자동으로 포함 조회)",
    )
    rbs.add_argument("--output-json", action="store_true")
    rbs.set_defaults(func=_cmd_report_backfill_status)

    sh7 = sub.add_parser(
        "smoke-harness",
        help="Phase 7 ai_harness_* 테이블 도달 (마이그레이션 필요)",
    )
    sh7.set_defaults(func=_cmd_smoke_harness)

    hai = sub.add_parser(
        "build-ai-harness-inputs",
        help="state_change_candidates → ai_harness_candidate_inputs 결정적 적재",
    )
    hai.add_argument(
        "--universe",
        default="sp500_current",
        help="run-id 미지정 시 최근 completed state_change_runs 기준",
    )
    hai.add_argument("--run-id", default=None, dest="run_id")
    hai.add_argument("--limit", type=int, default=500)
    hai.set_defaults(func=_cmd_build_ai_harness_inputs)

    gim = sub.add_parser(
        "generate-investigation-memos",
        help="harness input → investigation_memos + operator_review_queue",
    )
    gim.add_argument("--universe", default="sp500_current")
    gim.add_argument("--run-id", default=None, dest="run_id")
    gim.add_argument("--limit", type=int, default=500)
    gim.add_argument(
        "--candidate-ids",
        default=None,
        help="쉼표 구분 candidate_id만 처리(해당 run의 harness input 행이 있어야 함)",
    )
    gim.add_argument(
        "--force-new-memo-version",
        action="store_true",
        help="항상 memo_version=max+1로 신규 행 삽입(감사용; 기본은 동일 hash면 in-place 치환)",
    )
    gim.set_defaults(func=_cmd_generate_investigation_memos)

    srq = sub.add_parser(
        "set-review-queue-status",
        help="operator_review_queue 상태 변경(감사 reason 권장)",
    )
    srq.add_argument("--candidate-id", required=True, dest="candidate_id")
    srq.add_argument(
        "--status",
        required=True,
        choices=("pending", "reviewed", "needs_followup", "blocked_insufficient_data"),
    )
    srq.add_argument("--reason", default=None, help="status_reason 텍스트")
    srq.set_defaults(func=_cmd_set_review_queue_status)

    ep7 = sub.add_parser(
        "export-phase7-evidence-bundle",
        help="실데이터 후보별 입력·메모·클레임·큐·재실행 요약 JSON 덤프",
    )
    ep7.add_argument(
        "--candidate-ids",
        default=None,
        help="쉼표 구분 UUID (3개 이상 권장)",
    )
    ep7.add_argument(
        "--from-run",
        default=None,
        dest="from_run",
        metavar="RUN_ID",
        help="state_change_runs.id — 앞에서 sample_n개 후보 선택",
    )
    ep7.add_argument("--sample-n", type=int, default=3, dest="sample_n")
    ep7.add_argument(
        "--out-dir",
        default="docs/phase7_real_samples/latest",
        help="출력 디렉터리",
    )
    ep7.set_defaults(func=_cmd_export_phase7_evidence_bundle)

    rrq = sub.add_parser(
        "report-review-queue",
        help="operator_review_queue 조회 JSON",
    )
    rrq.add_argument(
        "--status",
        default=None,
        choices=("pending", "reviewed", "needs_followup", "blocked_insufficient_data"),
    )
    rrq.add_argument("--limit", type=int, default=200)
    rrq.set_defaults(func=_cmd_report_review_queue)

    sp8 = sub.add_parser(
        "smoke-phase8",
        help="Phase 8 casebook/scanner 테이블 도달 (마이그레이션 필요)",
    )
    sp8.set_defaults(func=_cmd_smoke_phase8)

    boc = sub.add_parser(
        "build-outlier-casebook",
        help="state_change run → outlier_casebook_runs + entries (휴리스틱 v1)",
    )
    boc.add_argument("--universe", default="sp500_current")
    boc.add_argument("--run-id", default=None, dest="run_id")
    boc.add_argument("--candidate-limit", type=int, default=600, dest="candidate_limit")
    boc.set_defaults(func=_cmd_build_outlier_casebook)

    bds = sub.add_parser(
        "build-daily-signal-snapshot",
        help="일일 스냅샷 + 저잡음 우선순위 워치리스트 (scanner_runs + daily_*)",
    )
    bds.add_argument("--universe", default="sp500_current")
    bds.add_argument("--run-id", default=None, dest="run_id")
    bds.add_argument("--as-of-date", default=None, dest="as_of_date")
    bds.add_argument("--candidate-limit", type=int, default=500, dest="candidate_limit")
    bds.add_argument("--top-n", type=int, default=15, dest="top_n")
    bds.add_argument(
        "--min-priority-score",
        type=float,
        default=20.0,
        dest="min_priority_score",
    )
    bds.add_argument(
        "--max-candidate-rank",
        type=int,
        default=60,
        dest="max_candidate_rank",
    )
    bds.set_defaults(func=_cmd_build_daily_signal_snapshot)

    rdw = sub.add_parser(
        "report-daily-watchlist",
        help="최근 또는 지정 scanner_run의 스냅샷 + 워치리스트 JSON",
    )
    rdw.add_argument("--scanner-run-id", default=None, dest="scanner_run_id")
    rdw.add_argument(
        "--universe",
        default=None,
        help="scanner_run_id 없을 때 최신 run 필터(선택)",
    )
    rdw.set_defaults(func=_cmd_report_daily_watchlist)

    ecs = sub.add_parser(
        "export-casebook-samples",
        help="casebook 엔트리 JSON을 디렉터리에 덤프 (실데이터 증거용)",
    )
    ecs.add_argument("--casebook-run-id", default=None, dest="casebook_run_id")
    ecs.add_argument("--state-change-run-id", default=None, dest="state_change_run_id")
    ecs.add_argument(
        "--universe",
        default=None,
        help="casebook/state_change id 없을 때: 해당 universe 최신 completed run의 최신 casebook",
    )
    ecs.add_argument("--limit", type=int, default=50)
    ecs.add_argument(
        "--out-dir",
        default="docs/phase8_samples/latest",
        help="출력 디렉터리",
    )
    ecs.set_defaults(func=_cmd_export_casebook_samples)

    sp9 = sub.add_parser(
        "smoke-phase9-observability",
        help="Phase 9 operational_runs / hypothesis_registry 테이블 도달",
    )
    sp9.set_defaults(func=_cmd_smoke_phase9_observability)

    rrh = sub.add_parser(
        "report-run-health",
        help="operational_runs 최근 요약 (상태·컴포넌트별 카운트)",
    )
    rrh.add_argument("--limit", type=int, default=80)
    rrh.set_defaults(func=_cmd_report_run_health)

    rf9 = sub.add_parser(
        "report-failures",
        help="operational_failures 최근 + 연결 run 메타",
    )
    rf9.add_argument("--limit", type=int, default=80)
    rf9.set_defaults(func=_cmd_report_failures)

    rrr = sub.add_parser(
        "report-research-registry",
        help="hypothesis_registry + promotion_gate_events + 거버넌스 경계 요약",
    )
    rrr.add_argument("--limit", type=int, default=200)
    rrr.set_defaults(func=_cmd_report_research_registry)

    srs = sub.add_parser(
        "seed-phase9-research-samples",
        help="샘플 가설 2건(idempotent) + 게이트 이벤트 — 실DB 증거용",
    )
    srs.set_defaults(func=_cmd_seed_phase9_research_samples)

    ssr = sub.add_parser(
        "seed-source-registry",
        help="data_source_registry 시드 upsert (마이그레이션 시드와 정합)",
    )
    ssr.set_defaults(func=_cmd_seed_source_registry)

    rsr = sub.add_parser(
        "report-source-registry",
        help="소스 레지스트리 + 오버레이 가용성 요약 JSON",
    )
    rsr.set_defaults(func=_cmd_report_source_registry)

    rog = sub.add_parser(
        "report-overlay-gap",
        help="고ROI 프리미엄 오버레이 갭·자격·영향 레이어 보고",
    )
    rog.add_argument(
        "--persist",
        action="store_true",
        help="source_overlay_gap_reports 에 payload 저장",
    )
    rog.set_defaults(func=_cmd_report_overlay_gap)

    ssa = sub.add_parser(
        "smoke-source-adapters",
        help="transcripts/estimates/price_quality 어댑터 seam probe (자격 없음=not_available_yet)",
    )
    ssa.set_defaults(func=_cmd_smoke_source_adapters)

    esr = sub.add_parser(
        "export-source-roi-matrix",
        help="코드 내장 ROI 순위 행렬 JSON (DB 불필요)",
    )
    esr.set_defaults(func=_cmd_export_source_roi_matrix)

    p11a = sub.add_parser(
        "probe-transcripts-provider",
        help="Phase 11: FMP earning_call_transcript 프로브 + source_overlay_availability 갱신",
    )
    p11a.set_defaults(func=_cmd_probe_transcripts_provider)

    p11b = sub.add_parser(
        "ingest-transcripts-sample",
        help="Phase 11: 단일 심볼·분기 샘플 ingest (raw_transcript_payloads_fmp + normalized_transcripts)",
    )
    p11b.add_argument("--symbol", default="AAPL", help="거래 심볼")
    p11b.add_argument("--year", type=int, default=2020)
    p11b.add_argument("--quarter", type=int, default=3)
    p11b.set_defaults(func=_cmd_ingest_transcripts_sample)

    p11c = sub.add_parser(
        "report-transcripts-overlay-status",
        help="Phase 11: earnings_call_transcripts 오버레이 행 + 메타 JSON",
    )
    p11c.set_defaults(func=_cmd_report_transcripts_overlay_status)

    p11d = sub.add_parser(
        "export-transcript-normalization-sample",
        help="Phase 11: 정규화 행 샘플 (본문 길이·접두만; 전문 미공개)",
    )
    p11d.add_argument("--ticker", default="AAPL")
    p11d.set_defaults(func=_cmd_export_transcript_normalization_sample)

    p12a = sub.add_parser(
        "run-public-core-cycle",
        help="Phase 12: 공개 코어 end-to-end (state change → harness → memo → casebook → watchlist) + 번들",
    )
    p12a.add_argument("--universe", default="sp500_current")
    p12a.add_argument("--state-change-run-id", default=None, dest="state_change_run_id")
    p12a.add_argument(
        "--ensure-state-change",
        action="store_true",
        help="completed run 없으면 run_state_change 한 번 시도(패널 전제)",
    )
    p12a.add_argument("--factor-version", default="v1")
    p12a.add_argument("--state-change-limit", type=int, default=200)
    p12a.add_argument("--harness-limit", type=int, default=500)
    p12a.add_argument("--memo-limit", type=int, default=500)
    p12a.add_argument("--casebook-candidate-limit", type=int, default=600)
    p12a.add_argument("--scanner-candidate-limit", type=int, default=500)
    p12a.add_argument("--scanner-top-n", type=int, default=15)
    p12a.add_argument("--min-priority-score", type=float, default=20.0)
    p12a.add_argument("--max-candidate-rank", type=int, default=60)
    p12a.add_argument("--as-of-date", default=None, dest="as_of_date")
    p12a.add_argument(
        "--out-dir",
        default=None,
        help="기본: docs/public_core_cycle/latest",
    )
    p12a.set_defaults(func=_cmd_run_public_core_cycle)

    p12b = sub.add_parser(
        "report-public-core-cycle",
        help="Phase 12: 마지막 run-public-core-cycle 요약 JSON 재출력",
    )
    p12b.add_argument(
        "--out-dir",
        default=None,
        help="cycle_summary.json 위치(기본 docs/public_core_cycle/latest)",
    )
    p12b.set_defaults(func=_cmd_report_public_core_cycle)

    p13a = sub.add_parser(
        "report-public-core-quality",
        help="Phase 13: 최근 public-core cycle 품질·갭·잔차 트리이지 DB 기록 요약",
    )
    p13a.add_argument("--limit", type=int, default=15)
    p13a.set_defaults(func=_cmd_report_public_core_quality)

    p13b = sub.add_parser(
        "export-public-core-quality-sample",
        help="Phase 13: 품질 실행 행을 JSON 파일로보내기 (증거 샘플)",
    )
    p13b.add_argument("--limit", type=int, default=10)
    p13b.add_argument(
        "--out",
        required=True,
        help="출력 JSON 경로 (예: docs/public_core_quality/samples/latest.json)",
    )
    p13b.set_defaults(func=_cmd_export_public_core_quality_sample)

    sp14 = sub.add_parser(
        "smoke-phase14-research-engine",
        help="Phase 14: research_programs 등 연구 엔진 테이블 도달",
    )
    sp14.set_defaults(func=_cmd_smoke_phase14_research_engine)

    p14a = sub.add_parser(
        "create-research-program",
        help="Phase 14: 단일 프로그램 락 질문으로 research_programs 생성",
    )
    p14a.add_argument("--universe", default="sp500_current")
    p14a.add_argument("--title", default=None)
    p14a.add_argument("--quality-run-id", default=None, dest="quality_run_id")
    p14a.add_argument("--owner-actor", default="operator", dest="owner_actor")
    p14a.set_defaults(func=_cmd_create_research_program)

    p14b = sub.add_parser(
        "list-research-programs",
        help="Phase 14: 최근 연구 프로그램 목록",
    )
    p14b.add_argument("--limit", type=int, default=30)
    p14b.set_defaults(func=_cmd_list_research_programs)

    p14c = sub.add_parser(
        "generate-program-hypotheses",
        help="Phase 14: 프로그램에 시드 가설 3건 + 잔차 링크",
    )
    p14c.add_argument("--program-id", required=True, dest="program_id")
    p14c.set_defaults(func=_cmd_generate_program_hypotheses)

    p14d = sub.add_parser(
        "review-research-hypothesis",
        help="Phase 14: 가설에 대해 렌즈 리뷰 1라운드 (최대 2라운드)",
    )
    p14d.add_argument("--hypothesis-id", required=True, dest="hypothesis_id")
    p14d.set_defaults(func=_cmd_review_research_hypothesis)

    p14e = sub.add_parser(
        "run-research-referee",
        help="Phase 14: kill / sandbox / candidate_recipe 판정",
    )
    p14e.add_argument("--hypothesis-id", required=True, dest="hypothesis_id")
    p14e.set_defaults(func=_cmd_run_research_referee)

    p14f = sub.add_parser(
        "report-research-program",
        help="Phase 14: 프로그램 + 가설 JSON",
    )
    p14f.add_argument("--program-id", required=True, dest="program_id")
    p14f.set_defaults(func=_cmd_report_research_program)

    p14g = sub.add_parser(
        "export-research-dossier",
        help="Phase 14: 프로그램 dossier JSON 파일",
    )
    p14g.add_argument("--program-id", required=True, dest="program_id")
    p14g.add_argument(
        "--out",
        required=True,
        help="예: docs/research_engine/dossiers/latest.json",
    )
    p14g.set_defaults(func=_cmd_export_research_dossier)

    sp15 = sub.add_parser(
        "smoke-phase15-recipe-validation",
        help="Phase 15: recipe_validation_runs 등 검증 랩 테이블 도달",
    )
    sp15.set_defaults(func=_cmd_smoke_phase15_recipe_validation)

    p15a = sub.add_parser(
        "run-recipe-validation",
        help="Phase 15: 가설(recipe/sandbox) 결정적 검증 실행·DB 적재",
    )
    p15a.add_argument("--hypothesis-id", required=True, dest="hypothesis_id")
    p15a.add_argument("--panel-limit", type=int, default=6000, dest="panel_limit")
    p15a.set_defaults(func=_cmd_run_recipe_validation)

    p15b = sub.add_parser(
        "report-recipe-validation",
        help="Phase 15: validation_run_id 단일 리포트 JSON",
    )
    p15b.add_argument("--validation-run-id", required=True, dest="validation_run_id")
    p15b.set_defaults(func=_cmd_report_recipe_validation)

    p15c = sub.add_parser(
        "compare-recipe-baselines",
        help="Phase 15: 최근 완료 검증의 베이스라인 비교 JSON",
    )
    p15c.add_argument("--hypothesis-id", required=True, dest="hypothesis_id")
    p15c.set_defaults(func=_cmd_compare_recipe_baselines)

    p15d = sub.add_parser(
        "report-recipe-survivors",
        help="Phase 15: survives / weak_survival 최근 N건",
    )
    p15d.add_argument("--limit", type=int, default=30)
    p15d.set_defaults(func=_cmd_report_recipe_survivors)

    p15e = sub.add_parser(
        "export-recipe-scorecard",
        help="Phase 15: 스코어카드 JSON+Markdown (동일 베이스명)",
    )
    p15e.add_argument("--hypothesis-id", required=True, dest="hypothesis_id")
    p15e.add_argument("--validation-run-id", default=None, dest="validation_run_id")
    p15e.add_argument(
        "--out",
        required=True,
        help="베이스 경로(확장자에 따라 .json/.md 쌍 생성)",
    )
    p15e.set_defaults(func=_cmd_export_recipe_scorecard)

    sp16 = sub.add_parser(
        "smoke-phase16-validation-campaign",
        help="Phase 16: validation_campaign_* 테이블 도달",
    )
    sp16.set_defaults(func=_cmd_smoke_phase16_validation_campaign)

    p16a = sub.add_parser(
        "run-validation-campaign",
        help="Phase 16: 프로그램 단위 검증 캠페인(재사용 또는 실행)",
    )
    p16a.add_argument("--program-id", required=True, dest="program_id")
    p16a.add_argument(
        "--run-mode",
        default="reuse_or_run",
        choices=["reuse_only", "reuse_or_run", "force_rerun"],
        dest="run_mode",
    )
    p16a.add_argument("--panel-limit", type=int, default=6000, dest="panel_limit")
    p16a.set_defaults(func=_cmd_run_validation_campaign)

    p16b = sub.add_parser(
        "report-validation-campaign",
        help="Phase 16: campaign_run_id 리포트 JSON",
    )
    p16b.add_argument("--campaign-run-id", required=True, dest="campaign_run_id")
    p16b.set_defaults(func=_cmd_report_validation_campaign)

    p16c = sub.add_parser(
        "report-program-survival-distribution",
        help="Phase 16: 프로그램 가설별 최근 완료 검증 생존 분포",
    )
    p16c.add_argument("--program-id", required=True, dest="program_id")
    p16c.set_defaults(func=_cmd_report_program_survival_distribution)

    p16d = sub.add_parser(
        "export-validation-decision-brief",
        help="Phase 16: 전략 브리프 JSON+Markdown",
    )
    p16d.add_argument("--campaign-run-id", required=True, dest="campaign_run_id")
    p16d.add_argument("--out", required=True, help="베이스 경로(.json/.md 쌍)")
    p16d.set_defaults(func=_cmd_export_validation_decision_brief)

    p16e = sub.add_parser(
        "list-eligible-validation-hypotheses",
        help="Phase 16: 캠페인 자격 있는 가설 목록",
    )
    p16e.add_argument("--program-id", required=True, dest="program_id")
    p16e.set_defaults(func=_cmd_list_eligible_validation_hypotheses)

    sp17 = sub.add_parser(
        "smoke-phase17-public-depth",
        help="Phase 17: public_depth_* 테이블 도달",
    )
    sp17.set_defaults(func=_cmd_smoke_phase17_public_depth)

    p17a = sub.add_parser(
        "run-public-depth-expansion",
        help="Phase 17: 공개 기판 확장(선택 빌드) + before/after·uplift 적재",
    )
    p17a.add_argument(
        "--universe",
        required=True,
        help="`list-universe-names` 의 use_for_phase17_cli 값 중 하나(예: sp500_current)",
    )
    p17a.add_argument("--panel-limit", type=int, default=8000, dest="panel_limit")
    p17a.add_argument(
        "--run-validation-panels",
        action="store_true",
        dest="run_validation_panels",
        help="전역 상한으로 factor_market_validation_panels 빌드",
    )
    p17a.add_argument(
        "--run-forward-returns",
        action="store_true",
        dest="run_forward_returns",
        help="전역 상한으로 forward_returns_daily_horizons 빌드",
    )
    p17a.add_argument(
        "--validation-panel-limit",
        type=int,
        default=2000,
        dest="validation_panel_limit",
    )
    p17a.add_argument(
        "--forward-panel-limit",
        type=int,
        default=2000,
        dest="forward_panel_limit",
    )
    p17a.add_argument(
        "--max-universe-factor-builds",
        type=int,
        default=0,
        dest="max_universe_factor_builds",
        help="유니버스 티커별 CIK factor 패널 빌드 최대 건수(0=스킵)",
    )
    p17a.set_defaults(func=_cmd_run_public_depth_expansion)

    p17b = sub.add_parser(
        "report-public-depth-coverage",
        help="Phase 17: 유니버스 기판 커버리지 스냅샷 JSON",
    )
    p17b.add_argument(
        "--universe",
        required=True,
        help="`list-universe-names` 의 use_for_phase17_cli 값 중 하나",
    )
    p17b.add_argument("--panel-limit", type=int, default=8000, dest="panel_limit")
    p17b.add_argument(
        "--persist",
        action="store_true",
        help="public_depth_coverage_reports 에 standalone 스냅샷 저장",
    )
    p17b.set_defaults(func=_cmd_report_public_depth_coverage)

    p17c = sub.add_parser(
        "report-quality-uplift",
        help="Phase 17: 두 커버리지 리포트 ID로 업리프트 지표 계산",
    )
    p17c.add_argument("--before-report-id", required=True, dest="before_report_id")
    p17c.add_argument("--after-report-id", required=True, dest="after_report_id")
    p17c.add_argument(
        "--persist",
        action="store_true",
        help="public_depth_uplift_reports 에 저장",
    )
    p17c.set_defaults(func=_cmd_report_quality_uplift)

    p17d = sub.add_parser(
        "report-research-readiness",
        help="Phase 17: 프로그램 기준 기판·Phase15/16 재실행 권고 요약",
    )
    p17d.add_argument("--program-id", required=True, dest="program_id")
    p17d.set_defaults(func=_cmd_report_research_readiness)

    p17e = sub.add_parser(
        "export-public-depth-brief",
        help="Phase 17: 기판 브리프 JSON+Markdown(--universe 또는 --program-id)",
    )
    p17e.add_argument("--out", required=True)
    p17e.add_argument("--universe", default=None)
    p17e.add_argument("--program-id", default=None, dest="program_id")
    p17e.add_argument("--panel-limit", type=int, default=8000, dest="panel_limit")
    p17e.set_defaults(func=_cmd_export_public_depth_brief)

    sp18 = sub.add_parser(
        "smoke-phase18-public-buildout",
        help="Phase 18: public_exclusion_action / public_buildout_* 테이블 도달",
    )
    sp18.set_defaults(func=_cmd_smoke_phase18_public_buildout)

    p18a = sub.add_parser(
        "report-public-exclusion-actions",
        help="Phase 18: 우세 제외 사유·심볼 큐·권장 수리 액션 JSON",
    )
    p18a.add_argument("--universe", required=True)
    p18a.add_argument("--panel-limit", type=int, default=8000, dest="panel_limit")
    p18a.add_argument(
        "--persist",
        action="store_true",
        help="public_exclusion_action_reports 에 스냅샷 저장",
    )
    p18a.set_defaults(func=_cmd_report_public_exclusion_actions)

    p18b = sub.add_parser(
        "run-targeted-public-buildout",
        help="Phase 18: 제외 사유 인지·상한 있는 공개 기판 수리 실행",
    )
    p18b.add_argument("--universe", required=True)
    p18b.add_argument("--panel-limit", type=int, default=8000, dest="panel_limit")
    p18b.add_argument(
        "--max-symbols-factor",
        type=int,
        default=50,
        dest="max_symbols_factor",
        help="no_validation_panel 대상 factor 패널 빌드 심볼 상한",
    )
    p18b.add_argument(
        "--validation-panel-limit",
        type=int,
        default=2000,
        dest="validation_panel_limit",
    )
    p18b.add_argument(
        "--forward-panel-limit",
        type=int,
        default=2000,
        dest="forward_panel_limit",
    )
    p18b.add_argument(
        "--state-change-limit",
        type=int,
        default=400,
        dest="state_change_limit",
    )
    p18b.add_argument(
        "--no-attack-validation",
        action="store_true",
        dest="no_attack_validation",
    )
    p18b.add_argument(
        "--no-attack-state-change",
        action="store_true",
        dest="no_attack_state_change",
    )
    p18b.add_argument(
        "--no-attack-forward-returns",
        action="store_true",
        dest="no_attack_forward_returns",
    )
    p18b.add_argument(
        "--dry-run",
        action="store_true",
        dest="dry_run",
        help="빌드 없이 타깃 제외 목록만 확정·런 행 기록",
    )
    p18b.set_defaults(func=_cmd_run_targeted_public_buildout)

    p18c = sub.add_parser(
        "report-buildout-improvement",
        help="Phase 18: 두 public_depth_coverage_reports ID로 제외·기판 델타",
    )
    p18c.add_argument(
        "--before-report-id",
        default=None,
        dest="before_report_id",
        help="수동 모드: 이전 스냅샷 persisted_report_id",
    )
    p18c.add_argument(
        "--after-report-id",
        default=None,
        dest="after_report_id",
        help="수동 모드: 이후 스냅샷 persisted_report_id",
    )
    p18c.add_argument(
        "--universe",
        default=None,
        help="--from-latest-pair 와 함께: 해당 유니버스 최신 2건으로 before/after 자동 선택",
    )
    p18c.add_argument(
        "--from-latest-pair",
        action="store_true",
        dest="from_latest_pair",
        help="created_at 기준 최신=after, 그다음=before (UUID 복사 불필요)",
    )
    p18c.add_argument(
        "--persist",
        action="store_true",
        help="public_buildout_improvement_reports 에 저장(run_id 없음)",
    )
    p18c.set_defaults(func=_cmd_report_buildout_improvement)

    p18d = sub.add_parser(
        "report-revalidation-trigger",
        help="Phase 18: Phase15/Phase16 재실행 권고(별도 불리언)",
    )
    p18d.add_argument("--program-id", required=True, dest="program_id")
    p18d.set_defaults(func=_cmd_report_revalidation_trigger)

    p18e = sub.add_parser(
        "export-buildout-brief",
        help="Phase 18: 제외 액션 브리프 JSON+Markdown",
    )
    p18e.add_argument("--universe", required=True)
    p18e.add_argument("--out", required=True)
    p18e.add_argument("--program-id", default=None, dest="program_id")
    p18e.add_argument("--panel-limit", type=int, default=8000, dest="panel_limit")
    p18e.set_defaults(func=_cmd_export_buildout_brief)

    p19s = sub.add_parser(
        "smoke-phase19-public-repair-campaign",
        help="Phase 19: repair campaign / comparison / decision 테이블 도달",
    )
    p19s.set_defaults(func=_cmd_smoke_phase19_public_repair_campaign)

    p19a = sub.add_parser(
        "run-public-repair-campaign",
        help="Phase 19: baseline→빌드아웃→개선→게이트된 Phase15/16→비교→최종 분기",
    )
    p19a.add_argument(
        "--program-id",
        required=True,
        dest="program_id",
        help="research_programs.id 또는 latest(다중 유니버스면 --universe 필수)",
    )
    p19a.add_argument(
        "--universe",
        default=None,
        help="미지정 시 research_programs.universe_name 사용",
    )
    p19a.add_argument(
        "--dry-run-buildout",
        action="store_true",
        dest="dry_run_buildout",
        help="타깃 빌드아웃만 dry-run(실제 수리 없음)",
    )
    p19a.add_argument(
        "--skip-reruns",
        action="store_true",
        dest="skip_reruns",
        help="Phase 15/16 캠페인 재실행 생략(비교·결정은 진행)",
    )
    p19a.add_argument("--panel-limit", type=int, default=8000, dest="panel_limit")
    p19a.add_argument(
        "--campaign-panel-limit", type=int, default=6000, dest="campaign_panel_limit"
    )
    p19a.add_argument("--max-symbols-factor", type=int, default=50, dest="max_symbols_factor")
    p19a.add_argument(
        "--validation-panel-limit", type=int, default=2000, dest="validation_panel_limit"
    )
    p19a.add_argument(
        "--forward-panel-limit", type=int, default=2000, dest="forward_panel_limit"
    )
    p19a.add_argument("--state-change-limit", type=int, default=400, dest="state_change_limit")
    p19a.set_defaults(func=_cmd_run_public_repair_campaign)

    p19b = sub.add_parser(
        "report-public-repair-campaign",
        help="Phase 19: 캠페인 런·스텝·결정·비교 조회",
    )
    p19b.add_argument(
        "--repair-campaign-id",
        required=True,
        dest="repair_campaign_id",
        help="UUID 또는 latest / latest-success / latest-compatible / latest-for-program (program-id 필요)",
    )
    p19b.add_argument(
        "--program-id",
        default=None,
        dest="program_id",
        help="repair-campaign-id=latest 일 때 필수(또는 latest+--universe)",
    )
    p19b.add_argument(
        "--universe",
        default=None,
        help="--program-id latest 와 함께 유니버스 고정",
    )
    p19b.set_defaults(func=_cmd_report_public_repair_campaign)

    p19c = sub.add_parser(
        "compare-repair-revalidation-outcomes",
        help="Phase 19: 저장된 재검증 비교 행 조회",
    )
    p19c.add_argument(
        "--repair-campaign-id",
        required=True,
        dest="repair_campaign_id",
        help="UUID 또는 latest 등(Phase 21 선택자, program-id 필요)",
    )
    p19c.add_argument("--program-id", default=None, dest="program_id")
    p19c.add_argument("--universe", default=None)
    p19c.set_defaults(func=_cmd_compare_repair_revalidation_outcomes)

    p19d = sub.add_parser(
        "export-public-repair-decision-brief",
        help="Phase 19: 최종 분기 브리프 JSON+Markdown",
    )
    p19d.add_argument(
        "--repair-campaign-id",
        required=True,
        dest="repair_campaign_id",
        help="UUID 또는 latest-success 등(완료+final_decision, program-id 필요)",
    )
    p19d.add_argument("--program-id", default=None, dest="program_id")
    p19d.add_argument("--universe", default=None)
    p19d.add_argument("--out", required=True)
    p19d.set_defaults(func=_cmd_export_public_repair_decision_brief)

    p19e = sub.add_parser(
        "list-repair-campaigns",
        help="Phase 19: 프로그램별 repair campaign 런 목록",
    )
    p19e.add_argument(
        "--program-id",
        required=True,
        dest="program_id",
        help="UUID 또는 latest",
    )
    p19e.add_argument("--universe", default=None)
    p19e.add_argument("--limit", type=int, default=20)
    p19e.set_defaults(func=_cmd_list_repair_campaigns)

    p20s = sub.add_parser(
        "smoke-phase20-repair-iteration",
        help="Phase 20: iteration series / members / escalation 테이블 도달",
    )
    p20s.set_defaults(func=_cmd_smoke_phase20_repair_iteration)

    p20a = sub.add_parser(
        "run-public-repair-iteration",
        help="Phase 20: Phase 19 캠페인 1회 + 시리즈 멤버·에스컬레이션 적재",
    )
    p20a.add_argument(
        "--program-id",
        required=True,
        dest="program_id",
        help="research_programs.id 또는 latest",
    )
    p20a.add_argument("--universe", default=None)
    p20a.add_argument("--dry-run-buildout", action="store_true", dest="dry_run_buildout")
    p20a.add_argument("--skip-reruns", action="store_true", dest="skip_reruns")
    p20a.add_argument("--panel-limit", type=int, default=8000, dest="panel_limit")
    p20a.add_argument(
        "--campaign-panel-limit", type=int, default=6000, dest="campaign_panel_limit"
    )
    p20a.add_argument("--max-symbols-factor", type=int, default=50, dest="max_symbols_factor")
    p20a.add_argument(
        "--validation-panel-limit", type=int, default=2000, dest="validation_panel_limit"
    )
    p20a.add_argument(
        "--forward-panel-limit", type=int, default=2000, dest="forward_panel_limit"
    )
    p20a.add_argument("--state-change-limit", type=int, default=400, dest="state_change_limit")
    p20a.set_defaults(func=_cmd_run_public_repair_iteration)

    p20b = sub.add_parser(
        "report-public-repair-iteration-history",
        help="Phase 20: 시리즈·멤버·에스컬레이션 이력",
    )
    p20b.add_argument("--series-id", default=None, dest="series_id")
    p20b.add_argument(
        "--program-id",
        default=None,
        dest="program_id",
        help="series-id 없을 때 필수(또는 latest)",
    )
    p20b.add_argument("--universe", default=None)
    p20b.set_defaults(func=_cmd_report_public_repair_iteration_history)

    p20c = sub.add_parser(
        "report-public-repair-plateau",
        help="Phase 20: 활성 시리즈 기준 플래토·에스컬레이션(재계산, DB 미삽입)",
    )
    p20c.add_argument(
        "--program-id",
        required=True,
        dest="program_id",
        help="UUID 또는 latest",
    )
    p20c.add_argument("--universe", default=None)
    p20c.add_argument(
        "--include-infra-failed-runs",
        action="store_true",
        dest="include_infra_failed_runs",
        help="기본(제외) 해제: 인프라성 실패 런도 플래토 스냅샷에 포함",
    )
    p20c.set_defaults(func=_cmd_report_public_repair_plateau)

    p20d = sub.add_parser(
        "export-public-repair-escalation-brief",
        help="Phase 20: 에스컬레이션 브리프 JSON+Markdown",
    )
    p20d.add_argument(
        "--program-id",
        required=True,
        dest="program_id",
        help="UUID 또는 latest",
    )
    p20d.add_argument("--universe", default=None)
    p20d.add_argument("--out", required=True)
    p20d.set_defaults(func=_cmd_export_public_repair_escalation_brief)

    p20e = sub.add_parser(
        "list-public-repair-series",
        help="Phase 20: 프로그램별 iteration series 목록",
    )
    p20e.add_argument(
        "--program-id",
        required=True,
        dest="program_id",
        help="UUID 또는 latest",
    )
    p20e.add_argument("--universe", default=None)
    p20e.add_argument("--limit", type=int, default=30)
    p20e.set_defaults(func=_cmd_list_public_repair_series)

    p20f = sub.add_parser(
        "report-latest-repair-state",
        help="Phase 20: 최근 repair 런·활성 시리즈·플래토 요약",
    )
    p20f.add_argument(
        "--program-id",
        required=True,
        dest="program_id",
        help="UUID 또는 latest",
    )
    p20f.add_argument("--universe", default=None)
    p20f.set_defaults(func=_cmd_report_latest_repair_state)

    p20g = sub.add_parser(
        "report-premium-discovery-readiness",
        help="Phase 20: targeted premium discovery 진입 가능 여부(에스컬레이션 기준)",
    )
    p20g.add_argument(
        "--program-id",
        required=True,
        dest="program_id",
        help="UUID 또는 latest",
    )
    p20g.add_argument("--universe", default=None)
    p20g.set_defaults(func=_cmd_report_premium_discovery_readiness)

    p21s = sub.add_parser(
        "smoke-phase21-iteration-governance",
        help="Phase 21: iteration governance 컬럼·테이블 도달",
    )
    p21s.set_defaults(func=_cmd_smoke_phase21_iteration_governance)

    p21p = sub.add_parser(
        "pause-public-repair-series",
        help="Phase 21: 활성 시리즈 일시중지(감사 reason)",
    )
    p21p.add_argument("--series-id", required=True, dest="series_id")
    p21p.add_argument("--reason", default="", dest="reason")
    p21p.set_defaults(func=_cmd_pause_public_repair_series)

    p21r = sub.add_parser(
        "resume-public-repair-series",
        help="Phase 21: 일시중지 시리즈 재개(감사 노트)",
    )
    p21r.add_argument("--series-id", required=True, dest="series_id")
    p21r.add_argument("--audit-note", default="", dest="audit_note")
    p21r.set_defaults(func=_cmd_resume_public_repair_series)

    p21c = sub.add_parser(
        "close-public-repair-series",
        help="Phase 21: 시리즈 종료(closure reason)",
    )
    p21c.add_argument("--series-id", required=True, dest="series_id")
    p21c.add_argument("--reason", default="", dest="reason")
    p21c.set_defaults(func=_cmd_close_public_repair_series)

    p21a = sub.add_parser(
        "advance-public-repair-series",
        help="Phase 21: 호환 시리즈·캠페인→멤버→플래토→브리프 한 번에",
    )
    p21a.add_argument(
        "--program-id",
        required=True,
        dest="program_id",
        help="UUID 또는 latest",
    )
    p21a.add_argument("--universe", default=None)
    p21a.add_argument(
        "--series-id",
        default=None,
        dest="series_id",
        help="선택: 명시 시리즈 UUID (latest-active-series 대신)",
    )
    p21a.add_argument(
        "--attach-only",
        action="store_true",
        dest="attach_only",
        help="새 캠페인 생략, --attach-repair-run-id 만 부착",
    )
    p21a.add_argument(
        "--attach-repair-run-id",
        default="",
        dest="attach_repair_run_id",
        help="attach-only 시 필수: UUID 또는 latest-compatible 등",
    )
    p21a.add_argument("--dry-run-buildout", action="store_true", dest="dry_run_buildout")
    p21a.add_argument("--skip-reruns", action="store_true", dest="skip_reruns")
    p21a.add_argument("--panel-limit", type=int, default=8000, dest="panel_limit")
    p21a.add_argument(
        "--campaign-panel-limit", type=int, default=6000, dest="campaign_panel_limit"
    )
    p21a.add_argument("--max-symbols-factor", type=int, default=50, dest="max_symbols_factor")
    p21a.add_argument(
        "--validation-panel-limit", type=int, default=2000, dest="validation_panel_limit"
    )
    p21a.add_argument(
        "--forward-panel-limit", type=int, default=2000, dest="forward_panel_limit"
    )
    p21a.add_argument("--state-change-limit", type=int, default=400, dest="state_change_limit")
    p21a.add_argument("--out", required=True)
    p21a.set_defaults(func=_cmd_advance_public_repair_series)

    p21pair = sub.add_parser(
        "resolve-repair-campaign-pair",
        help="Phase 21: 최신 2개 호환/성공 런 id (from-latest-pair)",
    )
    p21pair.add_argument(
        "--program-id",
        required=True,
        dest="program_id",
        help="UUID 또는 latest",
    )
    p21pair.add_argument("--universe", default=None)
    p21pair.add_argument(
        "--compatible",
        action="store_true",
        dest="compatible",
        help="활성 시리즈와 universe/policy 일치 완료 런만",
    )
    p21pair.set_defaults(func=_cmd_resolve_repair_campaign_pair)

    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return int(args.func(args))
    except RuntimeError as e:
        print(f"오류: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
