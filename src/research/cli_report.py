"""CLI용 인간可讀 요약 — 투자 추천·전략 포장 없음."""

from __future__ import annotations

from typing import Any

from db.records import (
    fetch_factor_quantiles_for_run,
    fetch_latest_factor_validation_summaries,
)


def print_factor_summary_cli(
    client: Any,
    *,
    factor_name: str,
    universe_name: str,
    horizon_type: str,
    return_basis: str = "raw",
) -> int:
    rid, rows = fetch_latest_factor_validation_summaries(
        client,
        factor_name=factor_name,
        universe_name=universe_name,
        horizon_type=horizon_type,
    )
    if not rid or not rows:
        print("(요약 없음: 해당 조건의 completed 검증 run 또는 요약 행이 없습니다.)")
        return 1
    row_by_basis = {str(r.get("return_basis")): r for r in rows}
    r0 = row_by_basis.get(return_basis) or rows[0]
    print("--- factor validation summary (descriptive research, not advice) ---")
    print(f"run_id: {rid}")
    print(f"factor_name: {r0.get('factor_name')}")
    print(f"universe_name: {r0.get('universe_name')}")
    print(f"horizon_type: {r0.get('horizon_type')}")
    print(f"return_basis (아래 상세): {return_basis}")
    print(f"sample_count (패널 행): {r0.get('sample_count')}")
    print(f"valid pairs (factor+return): {r0.get('valid_factor_count')}")
    print(f"spearman_rank_corr: {r0.get('spearman_rank_corr')}")
    print(f"pearson_corr: {r0.get('pearson_corr')}")
    print(f"hit_rate_same_sign: {r0.get('hit_rate_same_sign')}")
    cov = (
        client.table("factor_coverage_reports")
        .select("*")
        .eq("run_id", rid)
        .eq("factor_name", factor_name)
        .eq("universe_name", universe_name)
        .limit(1)
        .execute()
    )
    if cov.data:
        c = cov.data[0]
        print(
            f"coverage: available_rows={c.get('available_rows')} / "
            f"total_rows={c.get('total_rows')} (missing={c.get('missing_rows')})"
        )
    quants = fetch_factor_quantiles_for_run(
        client,
        run_id=rid,
        factor_name=factor_name,
        universe_name=universe_name,
        horizon_type=horizon_type,
        return_basis=return_basis,
    )
    if quants:
        lo = quants[0]
        hi = quants[-1]
        if return_basis == "raw":
            print(
                f"bottom quantile (idx={lo.get('quantile_index')}) avg raw return: "
                f"{lo.get('avg_raw_return')}"
            )
            print(
                f"top quantile (idx={hi.get('quantile_index')}) avg raw return: "
                f"{hi.get('avg_raw_return')}"
            )
        else:
            print(
                f"bottom quantile avg excess return: {lo.get('avg_excess_return')}"
            )
            print(
                f"top quantile avg excess return: {hi.get('avg_excess_return')}"
            )
    else:
        print("(quantile 행 없음 — 표본 부족 등)")
    print("--- end ---")
    return 0
