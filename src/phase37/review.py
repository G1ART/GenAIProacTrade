"""Phase 37 operator closeout — review MD + bundle JSON."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def write_phase37_research_engine_backlog_sprint_bundle_json(
    out_path: str,
    *,
    bundle: dict[str, Any],
) -> str:
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(bundle, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    return str(p.resolve())


def write_phase37_research_engine_backlog_sprint_review_md(
    out_path: str,
    *,
    bundle: dict[str, Any],
) -> str:
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    ex = bundle.get("executable_vs_conceptual") or {}
    p38 = bundle.get("phase38") or {}
    gt = bundle.get("ground_truth_phase36_1") or {}
    hyp = (bundle.get("hypothesis_registry_v1") or {}).get("hypotheses") or []
    pit = bundle.get("pit_lab") or {}
    cb = bundle.get("casebook_v1") or []
    expl = bundle.get("explanation_prototype") or {}

    lines = [
        "# Phase 37 — Research engine backlog sprint 1",
        "",
        f"_Generated (UTC): `{datetime.now(timezone.utc).isoformat()}`_",
        f"_Bundle generated (UTC): `{bundle.get('generated_utc', '')}`_",
        "",
        "## Ground truth (Phase 36.1)",
        "",
        f"- `joined_recipe_substrate_row_count`: `{gt.get('joined_recipe_substrate_row_count')}`",
        f"- `joined_market_metadata_flagged_count`: `{gt.get('joined_market_metadata_flagged_count')}`",
        f"- `no_state_change_join`: `{gt.get('no_state_change_join')}`",
        f"- `missing_excess_return_1q`: `{gt.get('missing_excess_return_1q')}`",
        f"- `missing_validation_symbol_count`: `{gt.get('missing_validation_symbol_count')}`",
        "",
        "## Research engine constitution",
        "",
        "Pillars mapped to modules + JSON artifacts — see `docs/research_engine_constitution.md` and bundle `research_engine_constitution`.",
        "",
        "## Executable vs still conceptual",
        "",
        "### Executable now",
    ]
    for item in ex.get("executable_now") or []:
        lines.append(f"- {item}")
    lines.extend(["", "### Conceptual (Phase 38+)", ""])
    for item in ex.get("conceptual_phase38") or []:
        lines.append(f"- {item}")

    lines.extend(
        [
            "",
            "## Hypothesis registry v1",
            "",
            f"- Count: **{len(hyp)}**",
        ]
    )
    for h in hyp:
        lines.append(
            f"- `{h.get('hypothesis_id')}` — **{h.get('status')}** — {h.get('title', '')[:120]}"
        )

    exps = pit.get("experiments") or []
    lines.extend(
        [
            "",
            "## PIT experiment scaffold",
            "",
            f"- Experiments recorded: **{len(exps)}** (scaffold; no DB replay in Sprint 1)",
            f"- Fixture rows: **{len(pit.get('fixture_join_key_mismatch_rows') or [])}** (`join_key_mismatch`)",
        ]
    )

    lines.extend(
        [
            "",
            "## Casebook",
            "",
            f"- Entries: **{len(cb)}**",
        ]
    )
    for c in cb:
        lines.append(f"- `{c.get('case_id')}` — {c.get('title', '')[:100]}")

    lines.extend(
        [
            "",
            "## Adversarial reviews",
            "",
            f"- Records: **{len(bundle.get('adversarial_reviews_v1') or [])}**",
            "",
            "## Explanation prototype",
            "",
            f"- Path: `{expl.get('path')}`",
            f"- Hypothesis: `{expl.get('hypothesis_id')}`",
            f"- Signal symbol: `{expl.get('signal_symbol')}`",
            "",
            "## Phase 38 recommendation",
            "",
            f"- **`{p38.get('phase38_recommendation')}`**",
            f"- {p38.get('rationale', '')}",
            "",
        ]
    )
    p.write_text("\n".join(lines), encoding="utf-8")
    return str(p.resolve())
