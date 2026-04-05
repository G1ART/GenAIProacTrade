#!/usr/bin/env python3
"""Convert founder spec .docx files to Markdown under docs/spec/ (no external deps)."""

from __future__ import annotations

import argparse
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

W_P = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"
W_T = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t"


def docx_to_md(src: Path) -> str:
    with zipfile.ZipFile(src) as z:
        xml = z.read("word/document.xml")
    root = ET.fromstring(xml)
    lines: list[str] = []
    for p in root.iter(W_P):
        parts: list[str] = []
        for t in p.iter(W_T):
            if t.text:
                parts.append(t.text)
            if t.tail:
                parts.append(t.tail)
        line = "".join(parts).strip()
        if line:
            lines.append(line)
    body = "\n\n".join(lines)
    title = src.stem.replace("_", " ")
    return (
        f"# {title}\n\n"
        f"> 원본: `{src.name}` — 레포 내 보관용 자동 추출본(표·머리글은 단순화됨).\n\n"
        f"{body}\n"
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--downloads",
        type=Path,
        default=Path.home() / "Downloads",
        help="Directory containing tech500_*.docx",
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "docs" / "spec",
    )
    args = ap.parse_args()
    mapping = [
        "tech500_factor_ai_architecture_blueprint_ko_v2.docx",
        "tech500_cursor_agent_protocol_ko.docx",
        "tech500_plan_mode_roadmap_ko.docx",
        "tech500_phase0_cursor_workorder_ko.docx",
    ]
    args.out.mkdir(parents=True, exist_ok=True)
    for name in mapping:
        src = args.downloads / name
        if not src.is_file():
            print(f"skip missing: {src}")
            continue
        md_name = src.with_suffix(".md").name
        (args.out / md_name).write_text(docx_to_md(src), encoding="utf-8")
        print(f"wrote {args.out / md_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
