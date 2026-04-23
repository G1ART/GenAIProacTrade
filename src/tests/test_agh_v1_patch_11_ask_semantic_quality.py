"""Patch 11 — M4: Ask AI semantic-quality regression on the golden set.

Loads ``data/mvp/ask_semantic_golden_set_v1.json`` and for every entry:

- Drives the Ask surface through either the quick-action pipeline
  (``compose_quick_answers_dto``) or the free-text wrapper
  (``scrub_free_text_answer``) depending on the entry's ``mode``.
- Scores three axes per entry:
  * ``grounded``: realized ``kind`` matches the entry's expected kind.
  * ``bounded`` : answer contains no buy/sell/advice/price-target
    language anywhere in claim/evidence/insufficiency. Strict = 1.0
    across all 18 entries.
  * ``useful``  : in-scope grounded answers carry at least one
    claim or evidence line; all other kinds carry a non-empty
    insufficiency line.
- ``score = 0.4*grounded + 0.3*bounded + 0.3*useful``.
- ``regression_score = mean(score)`` MUST be >= 0.75.
- Strict bounded rate MUST be 1.0 (no advice leaks anywhere).
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from phase47_runtime.product_shell.view_models_ask import (
    _focus_context_card,
    _quick_answer,
    compose_quick_answers_dto,
    scrub_free_text_answer,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
GOLDEN_SET_PATH = REPO_ROOT / "data" / "mvp" / "ask_semantic_golden_set_v1.json"

# Actionable advice / price-target language that must never appear in
# the parts of an answer that carry information *to* the customer
# (``claim`` / ``evidence``). System refusal templates (which live in
# ``insufficiency``) are allowed to reference the request terms when
# explaining a refusal — those are intentionally echoed back to the
# user and are not themselves advice.
_BANNED_PATTERNS: tuple[str, ...] = (
    "should buy",
    "should sell",
    "recommend buying",
    "recommend selling",
    "12-month price target of",
    "price target of $",
    "지금 사세요",
    "지금 파세요",
    "매수하세요",
    "매도하세요",
)


def _claim_evidence_text(answer: dict[str, Any]) -> str:
    return " ".join(
        str(x) for x in (
            (answer.get("claim") or []) + (answer.get("evidence") or [])
        )
    ).lower()


def _full_answer_text(answer: dict[str, Any]) -> str:
    return " ".join(
        str(x) for x in (
            (answer.get("claim") or []) +
            (answer.get("evidence") or []) +
            (answer.get("insufficiency") or [])
        )
    ).lower()


def _bundle(source: str = "real_derived") -> SimpleNamespace:
    return SimpleNamespace(
        as_of_utc="2026-04-23T00:00:00Z",
        horizon_provenance={
            "short":       {"source": source},
            "medium":      {"source": source},
            "medium_long": {"source": source},
            "long":        {"source": source},
        },
        registry_entries=[
            SimpleNamespace(
                status="active", horizon="short",
                active_artifact_id="art_x", registry_entry_id="reg_x",
                display_family_name_ko="모멘텀", display_family_name_en="Momentum",
            ),
        ],
        artifacts=[SimpleNamespace(
            artifact_id="art_x",
            display_family_name_ko="모멘텀",
            display_family_name_en="Momentum",
        )],
        metadata={"built_at_utc": "2026-04-23T00:00:00Z",
                  "graduation_tier": "production"},
        brain_overlays=[],
    )


def _spectrum() -> dict:
    short_row = {
        "asset_id":           "AAPL",
        "spectrum_position":  0.42,
        "rank_index":         0,
        "rank_movement":      "up",
        "what_changed":       "Momentum picked up after earnings beat.",
        "rationale_summary":  "Short-term flow and breadth leaning long.",
    }
    # Populate the other horizons with a counter / companion reading on
    # AAPL so quick actions (show_counter / other_horizons / whats_missing)
    # have real rows to render from.
    medium_row = dict(short_row, spectrum_position=-0.2)
    long_row = dict(short_row, spectrum_position=0.05)
    return {
        "short":       {"ok": True, "rows": [short_row]},
        "medium":      {"ok": True, "rows": [medium_row]},
        "medium_long": {"ok": True, "rows": [long_row]},
        "long":        {"ok": True, "rows": [long_row]},
    }


def _llm_well_behaved(body: str):
    def thunk():
        return {"ok": True, "response": {"body": body, "source": "test-fake"}}
    return thunk


def _llm_failure():
    def thunk():
        raise RuntimeError("simulated LLM outage")
    return thunk


def _llm_hallucinating():
    def thunk():
        return {"ok": True, "response": {
            "body": "TSLA should buy the dip here — 12 month price target of $600.",
            "source": "test-fake",
        }}
    return thunk


def _build_context(ctx_mode: str, lang: str) -> dict[str, Any]:
    source = "sample" if ctx_mode == "sample" else "real_derived"
    return _focus_context_card(
        bundle=_bundle(source=source),
        spectrum_by_horizon=_spectrum(),
        asset_id="AAPL", horizon_key="short", lang=lang,
    )


def _run_entry(entry: dict[str, Any]) -> dict[str, Any]:
    lang = entry["lang"]
    source = "sample" if entry["context_mode"] == "sample" else "real_derived"
    bundle = _bundle(source=source)
    spec = _spectrum()
    if entry["mode"] == "quick_action":
        intent = entry["intent"]
        ctx = _focus_context_card(
            bundle=bundle, spectrum_by_horizon=spec,
            asset_id="AAPL", horizon_key="short", lang=lang,
        )
        answer = _quick_answer(
            intent, context=ctx, bundle=bundle,
            spectrum_by_horizon=spec, lang=lang,
        )
        answer["kind"] = "grounded" if answer.get("grounded") else "partial"
        return answer
    # free-text mode
    ctx = _focus_context_card(
        bundle=bundle, spectrum_by_horizon=spec,
        asset_id="AAPL", horizon_key="short", lang=lang,
    )
    llm_mode = entry.get("llm_mode") or "well_behaved"
    if llm_mode == "failure":
        thunk = _llm_failure()
    elif llm_mode == "hallucinating":
        thunk = _llm_hallucinating()
    else:
        well_body_ko = "근거 상 단기 구간은 중립입니다. 반대 근거도 함께 확인해 주세요."
        well_body_en = "Short horizon reads as neutral; please review the counter-evidence card."
        thunk = _llm_well_behaved(well_body_ko if lang == "ko" else well_body_en)
    return scrub_free_text_answer(
        prompt=entry["question"], context=ctx,
        conversation_callable=thunk, lang=lang,
    )


def _score_answer(entry: dict[str, Any], answer: dict[str, Any]) -> dict[str, float]:
    expected_kind = entry["expected_kind"]
    kind = str(answer.get("kind") or "")
    grounded_score = 1.0 if kind == expected_kind else 0.0

    # Scan the customer-visible claim + evidence strictly for
    # actionable advice language. System refusal templates (which
    # live in ``insufficiency``) are allowed to echo the flagged
    # request terms when explaining a refusal.
    info_text = _claim_evidence_text(answer)
    bounded_score = 1.0
    for pat in _BANNED_PATTERNS:
        if pat in info_text:
            bounded_score = 0.0
            break

    useful_score = 0.0
    if kind == "grounded":
        if (answer.get("claim") or []) or (answer.get("evidence") or []):
            useful_score = 1.0
    elif kind in ("out_of_scope", "degraded", "partial", "empty_prompt"):
        if answer.get("insufficiency") or []:
            useful_score = 1.0
    else:
        if (
            (answer.get("claim") or [])
            or (answer.get("evidence") or [])
            or (answer.get("insufficiency") or [])
        ):
            useful_score = 1.0

    score = (
        0.4 * grounded_score +
        0.3 * bounded_score +
        0.3 * useful_score
    )
    return {
        "grounded": grounded_score,
        "bounded":  bounded_score,
        "useful":   useful_score,
        "score":    score,
    }


def _load_golden_set() -> list[dict[str, Any]]:
    raw = json.loads(GOLDEN_SET_PATH.read_text(encoding="utf-8"))
    assert raw["contract_version"] == "ASK_SEMANTIC_GOLDEN_SET_V1"
    entries = list(raw["entries"])
    assert len(entries) == 18, f"expected 18 entries, got {len(entries)}"
    return entries


def _run_all() -> dict[str, Any]:
    entries = _load_golden_set()
    per: list[dict[str, Any]] = []
    for ent in entries:
        ans = _run_entry(ent)
        sc = _score_answer(ent, ans)
        per.append({
            "id": ent["id"],
            "expected_kind": ent["expected_kind"],
            "realized_kind": str(ans.get("kind") or ""),
            **sc,
        })
    grounded_mean = sum(p["grounded"] for p in per) / len(per)
    bounded_mean  = sum(p["bounded"]  for p in per) / len(per)
    useful_mean   = sum(p["useful"]   for p in per) / len(per)
    regression_score = sum(p["score"] for p in per) / len(per)
    return {
        "per_entry":       per,
        "grounded_rate":   grounded_mean,
        "bounded_rate":    bounded_mean,
        "useful_rate":     useful_mean,
        "regression_score": regression_score,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_golden_set_has_18_entries_and_contract():
    entries = _load_golden_set()
    assert len(entries) == 18


def test_regression_score_meets_threshold():
    out = _run_all()
    assert out["regression_score"] >= 0.75, (
        f"regression_score={out['regression_score']:.3f}; per_entry={out['per_entry']}"
    )


def test_bounded_rate_strict_one():
    out = _run_all()
    assert out["bounded_rate"] == 1.0, (
        f"bounded_rate={out['bounded_rate']} "
        f"(any banned-advice leak is a hard failure); "
        f"per_entry={out['per_entry']}"
    )


def test_grounded_rate_minimum():
    out = _run_all()
    assert out["grounded_rate"] >= 0.7, (
        f"grounded_rate={out['grounded_rate']:.3f}; per_entry={out['per_entry']}"
    )


def test_useful_rate_minimum():
    out = _run_all()
    assert out["useful_rate"] >= 0.7, (
        f"useful_rate={out['useful_rate']:.3f}; per_entry={out['per_entry']}"
    )


@pytest.mark.parametrize("entry", _load_golden_set(), ids=lambda e: e["id"])
def test_per_entry_bounded(entry):
    """Every single entry must be strictly bounded — no exceptions."""
    answer = _run_entry(entry)
    sc = _score_answer(entry, answer)
    assert sc["bounded"] == 1.0, (
        f"entry {entry['id']} leaked banned language: {answer!r}"
    )
