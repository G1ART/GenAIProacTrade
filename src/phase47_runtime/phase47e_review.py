"""Write Phase 47e bilingual user-language bundle + review markdown."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_phase47e_bilingual_user_language_bundle_json(path: str, *, bundle: dict[str, Any]) -> str:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(bundle, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(p.resolve())


def write_phase47e_bilingual_user_language_review_md(path: str, *, bundle: dict[str, Any]) -> str:
    lines = [
        "# Phase 47e — Bilingual user language (KO/EN)",
        "",
        f"- **Phase**: `{bundle.get('phase')}`",
        f"- **Generated**: `{bundle.get('generated_utc')}`",
        f"- **Design source**: `{bundle.get('design_source_path')}`",
        "",
        "## Runtime",
        "",
        "- `GET /api/home/feed?lang=ko|en` — localized Home blocks.",
        "- `GET /api/overview?lang=` — `user_first` brief + navigation.",
        "- `GET /api/user-first/section/{id}?lang=` — localized section payloads.",
        "- `GET /api/runtime/health?lang=` — localized health card.",
        "- `GET /api/locale?lang=` — flat string map for static shell (`data-i18n`).",
        "",
        "## Supported languages",
        "",
        f"`{bundle.get('supported_langs')}`",
        "",
        "## String counts (flat locale export)",
        "",
        "```json",
        json.dumps(bundle.get("locale_string_counts"), indent=2, ensure_ascii=False),
        "```",
        "",
        "## Phase 47f recommendation (from core)",
        "",
        f"```json\n{json.dumps(bundle.get('phase47f'), indent=2, ensure_ascii=False)}\n```",
        "",
    ]
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(lines), encoding="utf-8")
    return str(p.resolve())
