#!/usr/bin/env python3
"""Patch 11 — M4 Ask AI semantic regression runbook.

Walks ``data/mvp/ask_semantic_golden_set_v1.json``, exercises each
entry against the real Product Shell Ask composers with deterministic
fake LLMs, and emits a JSON evidence file summarizing:

- ``regression_score`` = mean(0.4*grounded + 0.3*bounded + 0.3*useful)
- per-axis rates (grounded / bounded / useful)
- per-entry breakdown with expected vs realized kind

The script mirrors the in-test regression but is meant to be run as a
standalone manifest producer (``data/mvp/evidence/...``) so operators
can inspect answer quality without running the full pytest suite.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

# Re-use the golden-set runner from the test module. This guarantees
# the runbook and the regression test agree on a single scoring path.
from tests.test_agh_v1_patch_11_ask_semantic_quality import (  # noqa: E402
    GOLDEN_SET_PATH,
    _load_golden_set,
    _run_all,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        default=str(ROOT / "data/mvp/evidence/patch_11_ask_semantic_golden_set_evidence.json"),
        help="Path to the evidence JSON file to emit.",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.75,
        help="Minimum regression score for the runbook to return 0.",
    )
    args = parser.parse_args()

    entries = _load_golden_set()
    out = _run_all()
    evidence = {
        "contract_version":  "PATCH_11_ASK_SEMANTIC_EVIDENCE_V1",
        "golden_set_path":   str(GOLDEN_SET_PATH.relative_to(ROOT)),
        "entry_count":       len(entries),
        "rubric": {
            "formula":            "score = 0.4*grounded + 0.3*bounded + 0.3*useful",
            "regression_threshold": args.threshold,
            "bounded_strict":     True,
        },
        "rates": {
            "grounded_rate": round(out["grounded_rate"], 4),
            "bounded_rate":  round(out["bounded_rate"],  4),
            "useful_rate":   round(out["useful_rate"],   4),
        },
        "regression_score":  round(out["regression_score"], 4),
        "per_entry":         out["per_entry"],
        "all_ok":            bool(
            out["regression_score"] >= args.threshold
            and out["bounded_rate"] == 1.0
        ),
    }
    dest = Path(args.output)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        json.dumps(evidence, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"[patch-11-ask-semantic] wrote evidence → {dest}")
    print(
        f"  regression_score={evidence['regression_score']:.3f}  "
        f"grounded={evidence['rates']['grounded_rate']:.3f}  "
        f"bounded={evidence['rates']['bounded_rate']:.3f}  "
        f"useful={evidence['rates']['useful_rate']:.3f}  "
        f"all_ok={evidence['all_ok']}"
    )
    return 0 if evidence["all_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
