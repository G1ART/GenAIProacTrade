"""AGH v1 Patch 6 — Supabase probe for completed factor_validation_runs.

Read-only probe used by the Patch 6 runbook to decide between:
  - R branch: live evaluator + sandbox smoke (at least 1 completed run present)
  - D branch: honest-deferred evidence + copy-paste runbook

Writes a small JSON evidence file to
``data/mvp/evidence/agentic_operating_harness_v1_milestone_17_supabase_probe.json``
and exits 0 in all non-exception cases. The branch decision is encoded in the
JSON (and also echoed to stdout as a single line
``patch6_probe_branch=R`` or ``patch6_probe_branch=D``) so the runbook can
``grep`` it.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


def _default_evidence_path(repo_root: Path) -> Path:
    return (
        repo_root
        / "data"
        / "mvp"
        / "evidence"
        / "agentic_operating_harness_v1_milestone_17_supabase_probe.json"
    )


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _probe(repo_root: Path) -> dict[str, Any]:
    load_dotenv(repo_root / ".env")
    supabase_url = os.environ.get("SUPABASE_URL", "").strip()
    service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not supabase_url or not service_key:
        return {
            "contract": "AGH_V1_PATCH_6_SUPABASE_PROBE_V1",
            "probed_at_utc": _now_iso(),
            "branch": "D",
            "reason": "env_missing",
            "detail": (
                "SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not set; "
                "live smoke deferred."
            ),
            "completed_run_count": None,
            "sample_run": None,
        }
    try:
        from supabase import create_client  # type: ignore
    except Exception as exc:  # pragma: no cover - defensive
        return {
            "contract": "AGH_V1_PATCH_6_SUPABASE_PROBE_V1",
            "probed_at_utc": _now_iso(),
            "branch": "D",
            "reason": "supabase_import_failed",
            "detail": str(exc),
            "completed_run_count": None,
            "sample_run": None,
        }
    try:
        client = create_client(supabase_url, service_key)
        # Count-only: pull a single newest completed run to also capture a
        # sample shape, but do NOT pull the whole table.
        res = (
            client.table("factor_validation_runs")
            .select(
                "id,run_type,factor_version,universe_name,horizon_type,completed_at,status"
            )
            .eq("status", "completed")
            .order("completed_at", desc=True)
            .limit(1)
            .execute()
        )
        rows = list(res.data or [])
        # For count we do a second, count=exact call.
        count_res = (
            client.table("factor_validation_runs")
            .select("id", count="exact")
            .eq("status", "completed")
            .limit(1)
            .execute()
        )
        total = int(getattr(count_res, "count", None) or 0)
    except Exception as exc:
        return {
            "contract": "AGH_V1_PATCH_6_SUPABASE_PROBE_V1",
            "probed_at_utc": _now_iso(),
            "branch": "D",
            "reason": "supabase_query_failed",
            "detail": str(exc),
            "completed_run_count": None,
            "sample_run": None,
        }
    if total <= 0:
        return {
            "contract": "AGH_V1_PATCH_6_SUPABASE_PROBE_V1",
            "probed_at_utc": _now_iso(),
            "branch": "D",
            "reason": "no_completed_factor_validation_run",
            "detail": (
                "factor_validation_runs has zero rows with status='completed'; "
                "Patch 6 live smoke is honest-deferred (CF-4)."
            ),
            "completed_run_count": 0,
            "sample_run": None,
        }
    sample = rows[0] if rows else None
    return {
        "contract": "AGH_V1_PATCH_6_SUPABASE_PROBE_V1",
        "probed_at_utc": _now_iso(),
        "branch": "R",
        "reason": "completed_run_present",
        "detail": (
            f"Found {total} completed factor_validation_run(s); Patch 6 live "
            "smoke will attempt real evaluator + sandbox paths in dry_run mode."
        ),
        "completed_run_count": total,
        "sample_run": sample,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Supabase probe for Patch 6")
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root (defaults to CWD).",
    )
    parser.add_argument(
        "--out",
        default="",
        help="Override evidence output path.",
    )
    args = parser.parse_args(argv)
    repo_root = Path(args.repo_root).resolve()
    out = Path(args.out) if args.out else _default_evidence_path(repo_root)
    out.parent.mkdir(parents=True, exist_ok=True)
    result = _probe(repo_root)
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"patch6_probe_branch={result['branch']}")
    print(f"patch6_probe_reason={result['reason']}")
    print(f"patch6_probe_evidence={out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
