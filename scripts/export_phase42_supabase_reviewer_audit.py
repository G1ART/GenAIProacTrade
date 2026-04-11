#!/usr/bin/env python3
"""
Phase 42 리뷰어 패키지: Supabase fresh 번들(게이트 쓰기는 임시 디렉터리) + MD 감사
(행 표, filing_index 10-K/10-Q 샘플, market_metadata_latest 원시·분류).

Usage (저장소 루트, .env 등 Supabase 설정 필요):
  export PYTHONPATH=src
  python3 scripts/export_phase42_supabase_reviewer_audit.py
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

_FORMS = frozenset({"10-K", "10-Q"})


def _load_json(p: Path) -> dict[str, Any]:
    return json.loads(p.read_text(encoding="utf-8"))


def _md_table(headers: list[str], rows: list[list[str]]) -> str:
    esc = lambda s: str(s).replace("|", "\\|").replace("\n", " ")
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for r in rows:
        lines.append("| " + " | ".join(esc(c) for c in r) + " |")
    return "\n".join(lines)


def _sample_filings(
    filing_rows: list[dict[str, Any]],
    *,
    signal_ymd: str,
    max_pre: int = 6,
    max_post: int = 6,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    sig = (signal_ymd or "")[:10]
    if len(sig) < 10:
        sig = "9999-12-31"
    forms = [r for r in filing_rows if str(r.get("form") or "").strip() in _FORMS]

    def fd(r: dict[str, Any]) -> str:
        x = str(r.get("filed_at") or "").strip()
        return x[:10] if len(x) >= 10 else ""

    pre = [r for r in forms if len(fd(r)) >= 10 and fd(r) <= sig]
    post = [r for r in forms if len(fd(r)) >= 10 and fd(r) > sig]
    pre.sort(key=lambda r: fd(r), reverse=True)
    post.sort(key=lambda r: fd(r))
    return pre[:max_pre], post[:max_post]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--phase41-bundle-in",
        default="docs/operator_closeout/phase41_falsifier_substrate_bundle.json",
    )
    ap.add_argument(
        "--out-md",
        default="docs/operator_closeout/phase42_supabase_reviewer_audit.md",
    )
    ap.add_argument(
        "--out-bundle",
        default="docs/operator_closeout/phase42_evidence_accumulation_bundle_supabase.json",
    )
    ap.add_argument(
        "--research-data-template",
        default="data/research_engine",
        help="hypotheses_v1.json / promotion_gate_v1.json 복사 원본(게이트 스냅샷용)",
    )
    ap.add_argument("--filing-index-limit", type=int, default=200)
    ap.add_argument("--skip-phase42-run", action="store_true", help="번들(1) 생략, 감사 표만")
    args = ap.parse_args()

    from config import load_settings
    from db import records as dbrec
    from db.client import get_supabase_client

    from phase42.blocker_taxonomy import classify_filing_blocker_cause, classify_sector_blocker_cause
    from phase42.evidence_accumulation import extract_fixture_rows_from_phase41_bundle
    from phase42.orchestrator import build_row_blockers_supabase
    from phase42.review import write_phase42_evidence_accumulation_bundle_json

    p41 = REPO / args.phase41_bundle_in
    bundle41 = _load_json(p41)
    fixture_rows = extract_fixture_rows_from_phase41_bundle(bundle41)
    if not fixture_rows:
        print("error: no fixture rows in phase41 bundle", file=sys.stderr)
        return 1

    settings = load_settings()
    client = get_supabase_client(settings)

    lines: list[str] = [
        "# Phase 42 — Supabase 리뷰어 감사 패키지",
        "",
        f"_생성 UTC: `{datetime.now(timezone.utc).isoformat()}`_",
        f"_입력 Phase 41 번들: `{args.phase41_bundle_in}`_",
        "",
        "## 1. Phase 42 (Supabase fresh, `blocker_replay_source: supabase_fresh`)",
        "",
    ]

    phase42_summary: dict[str, Any] = {}

    if not args.skip_phase42_run:
        rtemplate = REPO / args.research_data_template
        td = Path(tempfile.mkdtemp(prefix="phase42_audit_"))
        try:
            for name in ("hypotheses_v1.json", "promotion_gate_v1.json"):
                src = rtemplate / name
                if src.is_file():
                    shutil.copy(src, td / name)
                elif name == "hypotheses_v1.json":
                    (td / name).write_text("[]", encoding="utf-8")
            from phase42.orchestrator import run_phase42_evidence_accumulation

            out = run_phase42_evidence_accumulation(
                settings,
                phase41_bundle_in=str(p41.resolve()),
                research_data_dir=str(td),
                use_supabase=True,
                filing_index_limit=int(args.filing_index_limit),
                bundle_out_ref=str(Path(args.out_bundle).name),
                explanation_out=str(
                    REPO / "docs/operator_closeout/phase42_explanation_surface_v5_supabase.md"
                ),
            )
            phase42_summary = {
                "ok": out.get("ok"),
                "generated_utc": out.get("generated_utc"),
                "stable_run_digest": out.get("stable_run_digest"),
                "family_evidence_scorecard": out.get("family_evidence_scorecard"),
                "promotion_gate_primary_block_category": out.get(
                    "promotion_gate_primary_block_category"
                ),
            }
            bout = REPO / args.out_bundle
            write_phase42_evidence_accumulation_bundle_json(str(bout), bundle=out)
            lines.extend(
                [
                    f"- **번들 JSON**: `{args.out_bundle}` (게이트·히스토리 쓰기는 임시 디렉터리 `{td.name}` 에만 수행 후 폐기)",
                    f"- **설명 v5 (이 실행)**: `docs/operator_closeout/phase42_explanation_surface_v5_supabase.md`",
                    "",
                    "```json",
                    json.dumps(phase42_summary, indent=2, ensure_ascii=False, default=str),
                    "```",
                    "",
                ]
            )
        finally:
            shutil.rmtree(td, ignore_errors=True)
    else:
        lines.append("_`--skip-phase42-run`: 섹션 1 번들 생략._\n")

    rows_supa = build_row_blockers_supabase(
        client,
        fixture_rows=fixture_rows,
        filing_index_limit=int(args.filing_index_limit),
    )

    lines.extend(
        [
            "## 2. Row-level blockers (Supabase 분류, 동일 로직 as orchestrator)",
            "",
            _md_table(
                [
                    "symbol",
                    "cik",
                    "signal_available_date",
                    "filing_blocker_cause",
                    "sector_blocker_cause",
                    "blocker_replay_source",
                ],
                [
                    [
                        str(r.get("symbol") or ""),
                        str(r.get("cik") or ""),
                        str(r.get("signal_available_date") or ""),
                        str(r.get("filing_blocker_cause") or ""),
                        str(r.get("sector_blocker_cause") or ""),
                        str(r.get("blocker_replay_source") or ""),
                    ]
                    for r in rows_supa
                ],
            ),
            "",
        ]
    )

    symbols = [str(r.get("symbol") or "").upper().strip() for r in fixture_rows]
    cik_by_sym = {str(r.get("symbol") or "").upper().strip(): str(r.get("cik") or "") for r in fixture_rows}
    sig_by_sym = {
        str(r.get("symbol") or "").upper().strip(): str(r.get("signal_available_date") or "")
        for r in fixture_rows
    }

    lines.append("## 3. `filing_index` — 10-K/10-Q 신호일 전·후 샘플\n")
    for fr in fixture_rows:
        sym = str(fr.get("symbol") or "").upper().strip()
        cik = str(fr.get("cik") or "").strip()
        sig = str(fr.get("signal_available_date") or "")[:10]
        all_rows = dbrec.fetch_filing_index_rows_for_cik(
            client, cik=cik, limit=int(args.filing_index_limit)
        )
        pre, post = _sample_filings(all_rows, signal_ymd=sig)
        lines.append(f"### {sym} (CIK `{cik}`, signal `{sig}`)\n")
        lines.append(f"- `filing_index` 행 수 (limit {args.filing_index_limit}, 전 form): **{len(all_rows)}**")
        lines.append("")
        for label, chunk in (("on_or_before_signal", pre), ("after_signal", post)):
            lines.append(f"**{label}** (10-K/10-Q, 최대 {len(chunk)}행)\n")
            if not chunk:
                lines.append("_해당 없음_\n")
                continue
            lines.append(
                _md_table(
                    ["form", "filed_at", "accepted_at", "accession_no"],
                    [
                        [
                            str(x.get("form") or ""),
                            str(x.get("filed_at") or ""),
                            str(x.get("accepted_at") or ""),
                            str(x.get("accession_no") or x.get("accession") or ""),
                        ]
                        for x in chunk
                    ],
                )
            )
            lines.append("")

    lines.append("## 4. `market_metadata_latest` — 행 존재·sector·industry\n")
    for sym in symbols:
        if not sym:
            continue
        cik = cik_by_sym.get(sym, "")
        r = client.table("market_metadata_latest").select("*").eq("symbol", sym).execute()
        raw_list = [dict(x) for x in (r.data or [])]
        picked = dbrec.fetch_market_metadata_latest_row_deterministic(client, symbol=sym)
        cause = classify_sector_blocker_cause(metadata_row=picked)
        if not raw_list:
            diag = "no_rows_in_table"
            sec_s = ind_s = ""
        else:
            diag = "rows_exist"
            if picked:
                sec = picked.get("sector")
                ind = picked.get("industry")
                sec_s = str(sec).strip() if sec is not None else ""
                ind_s = str(ind).strip() if ind is not None else ""
                if not sec_s and ind_s:
                    diag = "rows_exist_sector_blank_industry_present"
                elif not sec_s and not ind_s:
                    diag = "rows_exist_sector_blank_industry_blank"
                else:
                    diag = "rows_exist_sector_present"
            else:
                sec_s = ind_s = ""
                diag = "rows_exist_pick_failed"
        lines.append(f"### {sym} (CIK `{cik}`)\n")
        lines.append(f"- **raw_row_count**: {len(raw_list)}")
        lines.append(f"- **diagnostic**: `{diag}`")
        lines.append(f"- **taxonomy** (`classify_sector_blocker_cause` on picked row): `{cause.get('sector_blocker_cause')}`")
        if picked:
            lines.append(
                f"- **picked** (결정적 1건): `sector`={repr(sec_s) or 'empty'} · `industry`={repr(ind_s) or 'empty'}`"
            )
        else:
            lines.append("- **picked**: _없음_")
        lines.append("")

    out_md = REPO / args.out_md
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text("\n".join(lines), encoding="utf-8")
    print("wrote", out_md.relative_to(REPO))
    if not args.skip_phase42_run:
        print("wrote", Path(args.out_bundle))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
