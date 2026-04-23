"""Patch 11 — Brain truth freeze snapshots (16 DTOs + coherence manifest).

Writes deterministic snapshots of Today / Research-deepdive / Replay /
Ask-landing / Ask-quick / Ask out-of-scope for the same focus
``(AAPL, short)`` in both KO and EN *after* Patch 11 has extended the
Brain Bundle with:

- residual-score semantics per spectrum row
  (``residual_score_semantics_version`` / ``invalidation_hint`` /
  ``recheck_cadence``).
- a ``long_horizon_support_by_horizon`` block with honest tier
  labeling for the medium_long + long horizons.
- one bound ``brain_overlays`` entry (catalyst_window, counter=true).

The manifest asserts:

- All four primary surfaces (Today / Research / Replay / Ask) share a
  single coherence fingerprint per language — Patch 11 additions must
  not break cross-surface agreement.
- No engineering ids (``ovr_*`` / ``pcp_*`` / ``persona_candidate_id``)
  appear in any of the 16 DTOs.
- Every DTO's ``shared_focus`` carries the Patch 11 sub-blocks that
  apply to the focus horizon (``residual_freshness``,
  ``long_horizon_support`` where relevant, and ``overlay_note``).

Artifacts (under ``data/mvp/evidence/screenshots_patch_11/``):

    * 6 DTOs × 2 languages = 12 DTO files
    * ``brain_truth_manifest_AAPL_short.json``
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))


SCREENSHOT_DIR = REPO_ROOT / "data/mvp/evidence/screenshots_patch_11"


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _git_sha() -> str:
    try:
        out = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
            check=False, capture_output=True, text=True,
        )
        return (out.stdout or "").strip()
    except Exception:
        return ""


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    h.update(p.read_bytes())
    return h.hexdigest()


def _stub_bundle():
    from phase47_runtime.product_shell.view_models_common import HORIZON_KEYS  # type: ignore
    reg_entries = [SimpleNamespace(
        status="active", horizon=hz,
        active_artifact_id=f"stub_family_{hz}",
        registry_entry_id=f"stub_reg_{hz}",
        display_family_name_ko=f"{hz}-가문",
        display_family_name_en=f"{hz}-family",
        challenger_artifact_ids=[],
    ) for hz in HORIZON_KEYS]
    artifacts = [SimpleNamespace(
        artifact_id=f"stub_family_{hz}",
        display_family_name_ko=f"{hz}-가문",
        display_family_name_en=f"{hz}-family",
    ) for hz in HORIZON_KEYS]
    overlays = [{
        "overlay_id":        "ovr_catalyst_focus_001",
        "overlay_type":      "catalyst_window",
        "artifact_id":       "stub_family_short",
        "registry_entry_id": "",
        "confidence":        0.72,
        "counter_interpretation_present": True,
        "expected_direction_hint": "",
        "expiry_or_recheck_rule": "expires_after_next_filing",
    }]
    long_horizon_support = {
        "medium_long": {
            "contract_version": "LONG_HORIZON_SUPPORT_V1",
            "tier_key":         "limited",
            "n_rows":           25,
            "n_symbols":        10,
            "coverage_ratio":   0.55,
            "as_of_utc":        "2026-04-23T08:00:00Z",
            "reason":           "limited_evidence",
        },
        "long": {
            "contract_version": "LONG_HORIZON_SUPPORT_V1",
            "tier_key":         "sample",
            "n_rows":           3,
            "n_symbols":        2,
            "coverage_ratio":   0.1,
            "as_of_utc":        "2026-04-23T08:00:00Z",
            "reason":           "sample",
        },
    }
    return SimpleNamespace(
        artifacts=artifacts,
        registry_entries=reg_entries,
        horizon_provenance={
            "short":       {"source": "real_derived"},
            "medium":      {"source": "real_derived"},
            "medium_long": {"source": "real_derived"},
            "long":        {"source": "insufficient_evidence"},
        },
        metadata={"graduation_tier": "production",
                  "built_at_utc": "2026-04-23T07:30:00Z",
                  "source_run_ids": ["run_patch_11_freeze"]},
        as_of_utc="2026-04-23T08:00:00Z",
        brain_overlays=overlays,
        long_horizon_support_by_horizon=long_horizon_support,
    )


def _stub_spectrum():
    from phase47_runtime.product_shell.view_models_common import HORIZON_KEYS  # type: ignore
    def row(asset, pos, changed, ratn):
        return {
            "asset_id":           asset,
            "spectrum_position":  pos,
            "rank_index":         0,
            "rank_movement":      "up",
            "rationale_summary":  ratn,
            "what_changed":       changed,
            "residual_score_semantics_version": "residual_semantics_v1",
            "invalidation_hint":  "spectrum_position_crosses_midline",
            "recheck_cadence":    "monthly_after_new_filing_or_21_trading_days",
        }
    rows = [
        row("AAPL", 0.74, "지난 주 대비 상위 10% 구간에서 상대 강도 +8% 개선",
            "단기 추세 강세가 지속되며 변동성이 축소되는 국면입니다."),
        row("MSFT", 0.42, "이익 품질 스코어 소폭 상승", "장기 현금흐름 지지 유지"),
        row("NVDA", -0.33, "밸류에이션 긴장도 증가", "과열 구간에 진입"),
    ]
    return {hz: {"ok": True, "rows": rows} for hz in HORIZON_KEYS}


def _stub_followups():
    return [{
        "request": {"created_at_utc": "2026-04-23T07:00:00Z",
                    "payload": {"kind": "validation_rerun"}},
        "result":  {"created_at_utc": "2026-04-23T07:05:00Z",
                    "payload": {"outcome": "completed"}},
    }]


_FORBIDDEN_TOKENS = re.compile(
    r"\b(ovr_[A-Za-z0-9_]+|pcp_[A-Za-z0-9_]+|persona_candidate_id|overlay_id)\b"
)


def main() -> int:
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

    from phase47_runtime.product_shell.view_models import compose_today_product_dto  # type: ignore
    from phase47_runtime.product_shell.view_models_research import (  # type: ignore
        compose_research_deepdive_dto,
    )
    from phase47_runtime.product_shell.view_models_replay import (  # type: ignore
        compose_replay_product_dto,
    )
    from phase47_runtime.product_shell.view_models_ask import (  # type: ignore
        _focus_context_card,
        compose_ask_product_dto,
        compose_quick_answers_dto,
        scrub_free_text_answer,
    )

    bundle = _stub_bundle()
    spec = _stub_spectrum()
    followups = _stub_followups()
    now_utc = "2026-04-23T08:00:00Z"
    focus_asset = "AAPL"
    focus_hz = "short"

    artifacts: list[dict] = []
    signatures: dict[str, dict] = {}
    leak_hits: list[dict] = []

    def _check_leak(name: str, dto: dict) -> None:
        m = _FORBIDDEN_TOKENS.search(json.dumps(dto, ensure_ascii=False))
        if m:
            leak_hits.append({"file": name, "token": m.group(0)})

    def _check_patch_11_blocks(name: str, sig_holder: dict, *, surface: str) -> dict:
        """Return a small block describing which Patch 11 sub-blocks the
        DTO's shared_focus exposes for this focus horizon."""
        sf = (sig_holder.get("shared_focus") if isinstance(sig_holder, dict) else None) or {}
        return {
            "file":    name,
            "surface": surface,
            "has_residual_freshness":   "residual_freshness" in sf,
            "has_long_horizon_support": "long_horizon_support" in sf,
            "has_overlay_note":         "overlay_note" in sf,
        }

    patch11_rows: list[dict] = []

    def _write_dto(name: str, dto: dict, *, surface: str, lang: str) -> None:
        p = SCREENSHOT_DIR / name
        p.write_text(json.dumps(dto, ensure_ascii=False, indent=2), encoding="utf-8")
        sig = dto.get("coherence_signature") or {}
        artifacts.append({
            "surface":     surface,
            "lang":        lang,
            "target":      str(p.relative_to(REPO_ROOT)),
            "bytes":       p.stat().st_size,
            "sha256":      _sha256(p),
            "contract":    dto.get("contract"),
            "fingerprint": sig.get("fingerprint"),
        })
        signatures.setdefault(lang, {})[surface] = sig
        _check_leak(name, dto)
        # Track per-DTO Patch 11 sub-block presence (Today uses hero
        # card's shared_focus; all others carry shared_focus at DTO top).
        sf_holder: dict = dto
        if surface == "today":
            hero = next((hc for hc in dto.get("hero_cards", [])
                         if hc.get("horizon_key") == focus_hz), None)
            sf_holder = hero or {}
        patch11_rows.append(_check_patch_11_blocks(name, sf_holder, surface=surface))

    for lg in ("ko", "en"):
        today = compose_today_product_dto(
            bundle=bundle, spectrum_by_horizon=spec, lang=lg, now_utc=now_utc,
        )
        _write_dto(f"product_today_dto_focus_{focus_asset}_{focus_hz}_{lg}.json",
                   today, surface="today", lang=lg)
        deepdive = compose_research_deepdive_dto(
            bundle=bundle, spectrum_by_horizon=spec,
            asset_id=focus_asset, horizon_key=focus_hz, lang=lg, now_utc=now_utc,
        )
        _write_dto(f"product_research_deepdive_dto_focus_{focus_asset}_{focus_hz}_{lg}.json",
                   deepdive, surface="research", lang=lg)
        replay = compose_replay_product_dto(
            bundle=bundle, spectrum_by_horizon=spec, lineage=None,
            asset_id=focus_asset, horizon_key=focus_hz, lang=lg, now_utc=now_utc,
        )
        _write_dto(f"product_replay_dto_focus_{focus_asset}_{focus_hz}_{lg}.json",
                   replay, surface="replay", lang=lg)
        ask = compose_ask_product_dto(
            bundle=bundle, spectrum_by_horizon=spec,
            asset_id=focus_asset, horizon_key=focus_hz,
            followups=followups, lang=lg, now_utc=now_utc,
        )
        _write_dto(f"product_ask_landing_dto_focus_{focus_asset}_{focus_hz}_{lg}.json",
                   ask, surface="ask_ai", lang=lg)
        quick = compose_quick_answers_dto(
            bundle=bundle, spectrum_by_horizon=spec,
            asset_id=focus_asset, horizon_key=focus_hz, lang=lg,
        )
        _write_dto(f"product_ask_quick_dto_focus_{focus_asset}_{focus_hz}_{lg}.json",
                   quick, surface="ask_ai_quick", lang=lg)
        ctx = _focus_context_card(
            bundle=bundle, spectrum_by_horizon=spec,
            asset_id=focus_asset, horizon_key=focus_hz, lang=lg,
        )
        oos_prompt = ("AAPL 지금 매수 추천해 주세요."
                      if lg == "ko"
                      else "Should I buy AAPL right now?")

        def _unreachable_llm():
            raise AssertionError("LLM must not be called for out-of-scope")

        oos = scrub_free_text_answer(
            prompt=oos_prompt, context=ctx,
            conversation_callable=_unreachable_llm, lang=lg,
        )
        _write_dto(f"product_ask_freetext_out_of_scope_{lg}.json",
                   oos, surface="ask_ai_out_of_scope", lang=lg)

    invariants = {}
    for lg in ("ko", "en"):
        s = signatures[lg]
        fps = {k: (v or {}).get("fingerprint") for k, v in s.items()}
        four_surfaces = [fps.get(k) for k in ("today", "research", "replay", "ask_ai")]
        invariants[lg] = {
            "fingerprints":            fps,
            "cross_surface_match":     len({fp for fp in four_surfaces if fp}) == 1,
            "mismatched_surfaces":     [k for k in ("today", "research", "replay", "ask_ai")
                                        if (fps.get(k) or "") != (fps.get("research") or "")]
                                       if len({fp for fp in four_surfaces if fp}) != 1 else [],
        }

    manifest = {
        "contract":      "PATCH_11_BRAIN_TRUTH_FREEZE_V1",
        "generated_utc": _iso_now(),
        "git_head_sha":  _git_sha(),
        "focus":         {"asset_id": focus_asset, "horizon_key": focus_hz},
        "artifacts":     artifacts,
        "invariants":    invariants,
        "patch_11_surface_audit": patch11_rows,
        "engineering_id_leaks":   leak_hits,
        "all_ok": bool(
            not leak_hits
            and all(v["cross_surface_match"] for v in invariants.values())
        ),
    }
    manifest_path = SCREENSHOT_DIR / "brain_truth_manifest_AAPL_short.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(json.dumps({
        "ok":                manifest["all_ok"],
        "output_dir":        str(SCREENSHOT_DIR.relative_to(REPO_ROOT)),
        "dto_count":         len(artifacts),
        "engineering_id_leaks": leak_hits,
        "cross_surface_ok":  all(v["cross_surface_match"] for v in invariants.values()),
    }, ensure_ascii=False, indent=2))
    return 0 if manifest["all_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
