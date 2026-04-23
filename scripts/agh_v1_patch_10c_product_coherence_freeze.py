"""Patch 10C — Product Shell coherence freeze snapshots.

Writes deterministic snapshots of the *four* customer-facing surfaces
(Today / Research-deepdive / Replay / Ask) for the **same**
(asset_id, horizon_key) focus, so a future demo / regression harness
can diff against a known-good baseline that proves they are all
speaking about the same evidence.

Unlike the 10A/10B snapshots, this one binds the four DTOs together
with a shared :func:`coherence_signature` manifest, and asserts at
freeze time that the fingerprints match across Today / Research /
Replay / Ask (both KO and EN).

Artifacts (under ``data/mvp/evidence/screenshots_patch_10c/``):

    * ``product_today_dto_focus_AAPL_short_{ko,en}.json``
    * ``product_research_deepdive_dto_focus_AAPL_short_{ko,en}.json``
    * ``product_replay_dto_focus_AAPL_short_{ko,en}.json``
    * ``product_ask_landing_dto_focus_AAPL_short_{ko,en}.json``
    * ``product_ask_quick_dto_focus_AAPL_short_{ko,en}.json``
    * ``product_ask_freetext_out_of_scope_{ko,en}.json``
    * ``coherence_manifest_AAPL_short.json``  (SHA-256 per file +
      coherence_signature per DTO + cross-surface invariants)

This script is side-effect safe — no Supabase writes, no network
calls. It is the byte-level ground truth for the freeze_runbook
evidence bundle produced by ``agh_v1_patch_10c_product_coherence_runbook.py``.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))


SCREENSHOT_DIR = REPO_ROOT / "data/mvp/evidence/screenshots_patch_10c"


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


def _sha256_bytes(b: bytes) -> str:
    h = hashlib.sha256()
    h.update(b)
    return h.hexdigest()


def _sha256(p: Path) -> str:
    return _sha256_bytes(p.read_bytes())


def _stub_bundle():
    from phase47_runtime.product_shell.view_models_common import HORIZON_KEYS  # type: ignore
    reg_entries = []
    artifacts = []
    for hz in HORIZON_KEYS:
        reg_entries.append(SimpleNamespace(
            status="active", horizon=hz,
            active_artifact_id=f"stub_family_{hz}",
            registry_entry_id=f"stub_reg_{hz}",
            display_family_name_ko=f"{hz}-가문",
            display_family_name_en=f"{hz}-family",
        ))
        artifacts.append(SimpleNamespace(
            artifact_id=f"stub_family_{hz}",
            display_family_name_ko=f"{hz}-가문",
            display_family_name_en=f"{hz}-family",
        ))
    return SimpleNamespace(
        artifacts=artifacts,
        registry_entries=reg_entries,
        horizon_provenance={
            "short":       {"source": "real_derived"},
            "medium":      {"source": "real_derived"},
            "medium_long": {"source": "real_derived_with_degraded_challenger"},
            "long":        {"source": "template_fallback"},
        },
        metadata={"graduation_tier": "production",
                  "built_at_utc": "2026-04-23T07:30:00Z",
                  "source_run_ids": ["run_stub_a"]},
        as_of_utc="2026-04-23T08:00:00Z",
    )


def _stub_spectrum():
    from phase47_runtime.product_shell.view_models_common import HORIZON_KEYS  # type: ignore
    rows = [
        {"asset_id": "AAPL", "spectrum_position": 0.74,
         "rank_index": 1, "rank_movement": "up",
         "rationale_summary": "단기 추세 강세가 지속되며 변동성이 축소되는 국면입니다.",
         "what_changed": "지난 주 대비 상위 10% 구간에서 상대 강도 +8% 개선"},
        {"asset_id": "MSFT", "spectrum_position": 0.42,
         "rank_index": 4, "rank_movement": "up",
         "rationale_summary": "장기 현금흐름 지지 유지",
         "what_changed": "이익 품질 스코어 소폭 상승"},
        {"asset_id": "NVDA", "spectrum_position": -0.33,
         "rank_index": 18, "rank_movement": "down",
         "rationale_summary": "과열 구간에 진입",
         "what_changed": "밸류에이션 긴장도 증가"},
    ]
    return {hz: {"ok": True, "rows": rows} for hz in HORIZON_KEYS}


def _stub_followups():
    return [
        {
            "request": {
                "created_at_utc": "2026-04-23T07:00:00Z",
                "payload": {"kind": "validation_rerun"},
            },
            "result": {
                "created_at_utc": "2026-04-23T07:05:00Z",
                "payload": {"outcome": "completed"},
            },
        },
    ]


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

    def _write_dto(name: str, dto: dict, *, surface: str, lang: str) -> None:
        p = SCREENSHOT_DIR / name
        p.write_text(json.dumps(dto, ensure_ascii=False, indent=2), encoding="utf-8")
        sig = dto.get("coherence_signature") or {}
        artifacts.append({
            "surface":    surface,
            "lang":       lang,
            "target":     str(p.relative_to(REPO_ROOT)),
            "bytes":      p.stat().st_size,
            "sha256":     _sha256(p),
            "contract":   dto.get("contract"),
            "fingerprint": sig.get("fingerprint"),
        })
        signatures.setdefault(lang, {})[surface] = sig

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
            bundle=bundle, spectrum_by_horizon=spec,
            lineage=None, asset_id=focus_asset, horizon_key=focus_hz,
            lang=lg, now_utc=now_utc,
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

        # out-of-scope freeze — proves the pre-LLM guard fires without
        # calling the LLM, and its wording is the shared "out_of_scope"
        # bucket.
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

    # --- coherence invariants across the four primary surfaces ----------
    invariants = {}
    for lg in ("ko", "en"):
        s = signatures[lg]
        fps = {k: (v or {}).get("fingerprint") for k, v in s.items()}
        four_surfaces = [fps.get(k) for k in ("today", "research", "replay", "ask_ai")]
        mismatch = [k for k in ("today", "research", "replay", "ask_ai")
                    if (fps.get(k) or "") != (fps.get("research") or "")]
        invariants[lg] = {
            "fingerprints": fps,
            "cross_surface_match":
                len({fp for fp in four_surfaces if fp}) == 1,
            "mismatched_surfaces": mismatch if len({fp for fp in four_surfaces if fp}) != 1 else [],
        }

    manifest = {
        "contract":      "PATCH_10C_PRODUCT_COHERENCE_FREEZE_V1",
        "generated_utc": _iso_now(),
        "git_head_sha":  _git_sha(),
        "focus":         {"asset_id": focus_asset, "horizon_key": focus_hz},
        "artifacts":     artifacts,
        "invariants":    invariants,
    }
    manifest_path = SCREENSHOT_DIR / "coherence_manifest_AAPL_short.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(json.dumps({
        "ok": True,
        "output_dir": str(SCREENSHOT_DIR.relative_to(REPO_ROOT)),
        "artifact_count": len(artifacts) + 1,
        "cross_surface_coherence_ok": all(v["cross_surface_match"] for v in invariants.values()),
    }, ensure_ascii=False, indent=2))
    return 0 if all(v["cross_surface_match"] for v in invariants.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
