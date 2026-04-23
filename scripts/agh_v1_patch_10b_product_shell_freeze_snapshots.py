"""Patch 10B — Product Shell Research/Replay/Ask freeze snapshots.

Writes deterministic snapshots of the *10B* customer-facing surfaces so
a future demo / design review / regression harness can diff against a
known-good baseline without needing a running HTTP server.

Artifacts (under ``data/mvp/evidence/screenshots_patch_10b/``):

    * ``product_shell_index.html``                  (verbatim copy)
    * ``product_shell.js``                          (verbatim copy)
    * ``product_shell.css``                         (verbatim copy)
    * ``product_research_landing_dto_sample_ko.json``
    * ``product_research_landing_dto_sample_en.json``
    * ``product_research_deepdive_dto_sample_ko.json``
    * ``product_research_deepdive_dto_sample_en.json``
    * ``product_replay_dto_sample_ko.json``
    * ``product_replay_dto_sample_en.json``
    * ``product_ask_landing_dto_sample_ko.json``
    * ``product_ask_landing_dto_sample_en.json``
    * ``product_ask_quick_dto_sample_ko.json``
    * ``product_ask_quick_dto_sample_en.json``
    * ``product_ask_freetext_degraded_sample_ko.json``
    * ``product_ask_freetext_degraded_sample_en.json``
    * ``product_request_state_dto_sample_ko.json``
    * ``product_request_state_dto_sample_en.json``
    * ``patch_10b_manifest.json``

This script is side-effect safe — no Supabase writes, no network calls.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))


SCREENSHOT_DIR = REPO_ROOT / "data/mvp/evidence/screenshots_patch_10b"


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


def _copy(src: Path, dst: Path) -> dict:
    shutil.copyfile(src, dst)
    return {
        "source": str(src.relative_to(REPO_ROOT)),
        "target": str(dst.relative_to(REPO_ROOT)),
        "bytes":  dst.stat().st_size,
        "sha256": _sha256(dst),
    }


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
         "rationale_summary": "중기 추세 강세가 지속되며 변동성이 축소되는 국면입니다.",
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
        {
            "request": {
                "created_at_utc": "2026-04-23T07:15:00Z",
                "payload": {"kind": "validation_rerun"},
            },
            "result": None,
        },
    ]


def main() -> int:
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    static = REPO_ROOT / "src/phase47_runtime/static"

    copies: list[dict] = []
    copies.append(_copy(static / "index.html",          SCREENSHOT_DIR / "product_shell_index.html"))
    copies.append(_copy(static / "product_shell.js",    SCREENSHOT_DIR / "product_shell.js"))
    copies.append(_copy(static / "product_shell.css",   SCREENSHOT_DIR / "product_shell.css"))

    from phase47_runtime.product_shell.view_models_ask import (  # type: ignore
        compose_ask_product_dto,
        compose_quick_answers_dto,
        compose_request_state_dto,
        scrub_free_text_answer,
    )
    from phase47_runtime.product_shell.view_models_replay import (  # type: ignore
        compose_replay_product_dto,
    )
    from phase47_runtime.product_shell.view_models_research import (  # type: ignore
        compose_research_deepdive_dto,
        compose_research_landing_dto,
    )

    bundle = _stub_bundle()
    spec = _stub_spectrum()
    followups = _stub_followups()
    now_utc = "2026-04-23T08:00:00Z"

    dto_files: list[dict] = []
    def _write_dto(name: str, dto: dict) -> None:
        p = SCREENSHOT_DIR / name
        p.write_text(json.dumps(dto, ensure_ascii=False, indent=2), encoding="utf-8")
        dto_files.append({
            "target":  str(p.relative_to(REPO_ROOT)),
            "bytes":   p.stat().st_size,
            "sha256":  _sha256(p),
            "contract": dto.get("contract"),
        })

    for lg in ("ko", "en"):
        landing = compose_research_landing_dto(
            bundle=bundle, spectrum_by_horizon=spec, lang=lg, now_utc=now_utc,
        )
        _write_dto(f"product_research_landing_dto_sample_{lg}.json", landing)

        deepdive = compose_research_deepdive_dto(
            bundle=bundle, spectrum_by_horizon=spec,
            asset_id="AAPL", horizon_key="short", lang=lg, now_utc=now_utc,
        )
        _write_dto(f"product_research_deepdive_dto_sample_{lg}.json", deepdive)

        import inspect
        kwargs = dict(
            bundle=bundle, spectrum_by_horizon=spec,
            asset_id="AAPL", horizon_key="short",
            lang=lg, now_utc=now_utc,
        )
        sig = inspect.signature(compose_replay_product_dto)
        if "lineage" in sig.parameters: kwargs["lineage"] = None
        if "followups" in sig.parameters: kwargs["followups"] = followups
        replay_dto = compose_replay_product_dto(**kwargs)
        _write_dto(f"product_replay_dto_sample_{lg}.json", replay_dto)

        ask_dto = compose_ask_product_dto(
            bundle=bundle, spectrum_by_horizon=spec,
            asset_id="AAPL", horizon_key="short",
            followups=followups, lang=lg, now_utc=now_utc,
        )
        _write_dto(f"product_ask_landing_dto_sample_{lg}.json", ask_dto)

        quick_dto = compose_quick_answers_dto(
            bundle=bundle, spectrum_by_horizon=spec,
            asset_id="AAPL", horizon_key="short", lang=lg,
        )
        _write_dto(f"product_ask_quick_dto_sample_{lg}.json", quick_dto)

        freetext = scrub_free_text_answer(
            prompt="왜 등급이 올랐나요?" if lg == "ko" else "Why did the grade go up?",
            context={"horizon_caption": "단기" if lg == "ko" else "Short term"},
            conversation_callable=lambda: {"ok": False},
            lang=lg,
        )
        _write_dto(f"product_ask_freetext_degraded_sample_{lg}.json", freetext)

        req_dto = compose_request_state_dto(followups, lang=lg)
        _write_dto(f"product_request_state_dto_sample_{lg}.json", req_dto)

    manifest = {
        "contract": "PATCH_10B_PRODUCT_SHELL_FREEZE_V1",
        "generated_utc": _iso_now(),
        "git_head_sha": _git_sha(),
        "copies": copies,
        "dto_samples": dto_files,
    }
    manifest_path = SCREENSHOT_DIR / "patch_10b_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(json.dumps({
        "ok": True,
        "output_dir": str(SCREENSHOT_DIR.relative_to(REPO_ROOT)),
        "artifacts": [c["target"] for c in copies] + [d["target"] for d in dto_files] + [
            str(manifest_path.relative_to(REPO_ROOT))
        ],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
