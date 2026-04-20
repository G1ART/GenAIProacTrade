"""AGH v1 Patch 6 — D2 primary-UI copy no-leak scanner.

Guardrail: engineering/snake_case tokens (e.g. ``registry_entry_id``,
``active_artifact_id``, ``horizon_type``, ``research_structured_v1``) must
not leak into primary UI copy — neither the ``tsr.*`` / ``research_section.*``
/ ``lineage.*`` / ``plot.*`` locale strings that the client pulls via
``/api/locale``, nor the inline KO/EN literals inside the TSR render
functions in ``src/phase47_runtime/static/app.js``.

These tokens ARE allowed inside progressive-disclosure audit blocks
(``<details>...raw identifiers...</details>``) and inside ``data-*``
attributes (which are not user-visible). The scanner therefore only flags
tokens that appear inside user-facing copy.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


FORBIDDEN_ENG_TOKENS: tuple[str, ...] = (
    "registry_entry_id",
    "active_artifact_id",
    "to_active_artifact_id",
    "from_active_artifact_id",
    "factor_validation_run",
    "factor_validation_runs",
    "horizon_type",
    "return_basis",
    "universe_name",
    "factor_name",
    "sandbox_kind",
    "research_structured_v1",
    "proposed_sandbox_request",
    "registry_surface_v1",
    "replay_lineage_join_v1",
    "evidence_cited",
    "cited_packet_ids",
    "recent_governed_applies_for_horizon",
    "recent_sandbox_completions_for_horizon",
    "active_model_family_name",
    "active_thesis_family",
    "message_snapshot_id",
    "packet_id",
    "completed_at",
)


# ---------------------------------------------------------------------------
# Part 1 — locale dictionary scanner
# ---------------------------------------------------------------------------


TSR_LOCALE_KEY_PREFIXES: tuple[str, ...] = (
    "tsr.",
    "research_section.",
    "lineage.",
    "plot.",
)


REQUIRED_TSR_KEYS: tuple[str, ...] = (
    # Rail (block 1 of 4)
    "tsr.rail.today_summary",
    "tsr.rail.no_recent",
    "tsr.rail.change_chip_prefix",
    # Primary (block 2 of 4)
    "tsr.primary.meta_sep",
    "tsr.primary.why_now_empty",
    # Decision stack (block 3 of 4)
    "tsr.decision.one_line_empty",
    "tsr.decision.deeper",
    "tsr.decision.signals",
    "tsr.decision.supporting",
    "tsr.decision.opposing",
    "tsr.decision.unproven",
    "tsr.decision.watch",
    # Evidence strip (block 4 of 4)
    "tsr.evidence.head",
    "tsr.evidence.active_artifact",
    "tsr.evidence.no_artifact",
    "tsr.evidence.raw_ids",
    # Research 5-section renderer
    "research_section.head",
    "research_section.current_read",
    "research_section.why_plausible",
    "research_section.unproven",
    "research_section.watch",
    "research_section.bounded_next",
    "research_section.empty_head",
    "research_section.empty_body",
    "research_section.locale_dual",
    "research_section.locale_ko_only",
    "research_section.locale_en_only",
    "research_section.locale_degraded",
    "research_section.invoke_copy_hint",
    "research_section.invoke_ui_hint",
    "research_section.invoke_copy_btn",
    "research_section.invoke_enqueue_btn",
    # Replay governance lineage
    "lineage.head",
    "lineage.chip_applies",
    "lineage.chip_sandbox_completed",
    "lineage.step.proposal",
    "lineage.step.apply",
    "lineage.step.spectrum_refresh",
    "lineage.step.validation_eval",
    "lineage.followups",
    "lineage.no_followups",
    # Replay timeline plot
    "plot.no_events",
    "plot.governed_apply",
    "plot.sandbox_followup",
)


def _load_shell() -> dict[str, dict[str, str]]:
    from phase47_runtime.phase47e_user_locale import SHELL

    return SHELL


def test_tsr_locale_keys_present_in_both_languages() -> None:
    shell = _load_shell()
    for lang in ("ko", "en"):
        assert lang in shell, f"SHELL missing lang={lang}"
        flat = shell[lang]
        missing = [k for k in REQUIRED_TSR_KEYS if k not in flat or not str(flat[k])]
        assert not missing, (
            f"SHELL[{lang}] missing required TSR locale keys: {missing}"
        )


def test_tsr_locale_strings_do_not_leak_eng_tokens() -> None:
    shell = _load_shell()
    leaks: list[str] = []
    for lang, flat in shell.items():
        for key, value in flat.items():
            if not any(key.startswith(p) for p in TSR_LOCALE_KEY_PREFIXES):
                continue
            for tok in FORBIDDEN_ENG_TOKENS:
                if tok in str(value):
                    leaks.append(f"{lang}::{key} leaked token {tok!r}: {value!r}")
    assert not leaks, "engineering tokens leaked into TSR primary-UI locale strings:\n" + "\n".join(leaks)


# ---------------------------------------------------------------------------
# Part 2 — app.js TSR renderer inline copy scanner
# ---------------------------------------------------------------------------


APP_JS = REPO_ROOT / "src" / "phase47_runtime" / "static" / "app.js"


TSR_RENDERER_FUNCTIONS: tuple[str, ...] = (
    "renderTodaySummaryRailHtml",
    "renderTodayPrimaryPanelHtml",
    "renderTodayDecisionStackHtml",
    "renderTodayEvidenceStripHtml",
    "renderResearchStructuredSection",
    "hydrateReplayGovernanceLineageCompact",
    "renderReplayTimelinePlotSvg",
)


def _extract_fn_body(src: str, fn_name: str) -> str:
    """Extract a JS function body by brace matching from ``function NAME(`` onward.

    Returns an empty string if the function is not found. This is a simple
    brace counter; it is good enough for our TSR renderer style (no regex
    literals with braces, strings do not nest raw ``{``/``}`` characters
    we would misinterpret).
    """
    marker = f"function {fn_name}("
    idx = src.find(marker)
    if idx < 0:
        return ""
    brace_start = src.find("{", idx)
    if brace_start < 0:
        return ""
    depth = 0
    i = brace_start
    in_str: str | None = None
    escape = False
    while i < len(src):
        ch = src[i]
        if in_str is not None:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == in_str:
                in_str = None
            i += 1
            continue
        if ch in ("'", '"', "`"):
            in_str = ch
            i += 1
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return src[brace_start : i + 1]
        i += 1
    return ""


_STRING_RE = re.compile(
    r"""(?P<q>["'`])(?P<body>(?:\\.|(?!\1).)*?)(?P=q)""",
    re.DOTALL,
)

_DETAILS_BLOCK_RE = re.compile(r"<details>.*?</details>", re.DOTALL | re.IGNORECASE)
_DATA_ATTR_RE = re.compile(r"""data-[\w-]+=\\?["'][^"']*\\?["']""")


def _strip_template_exprs(text: str) -> str:
    """Remove ``${...}`` expressions with brace-matched balancing.

    Template-literal expressions contain JS code, not displayed copy; only
    the surrounding static text is user-visible. ``[^}]*`` is not enough
    because nested braces in arrow-function bodies would terminate early.
    """
    out: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        if i + 1 < n and text[i] == "$" and text[i + 1] == "{":
            depth = 1
            j = i + 2
            while j < n and depth > 0:
                if text[j] == "{":
                    depth += 1
                elif text[j] == "}":
                    depth -= 1
                j += 1
            out.append(" ")
            i = j
            continue
        out.append(text[i])
        i += 1
    return "".join(out)


_URL_LIKE_MARKERS: tuple[str, ...] = (
    "/api/",
    "encodeURIComponent",
    "?lang=",
    "&lang=",
    "Content-Type",
    "application/json",
)


def _looks_like_url_or_fetch_payload(raw: str) -> bool:
    """Return True if the string is an internal URL / fetch payload, not user copy."""
    return any(marker in raw for marker in _URL_LIKE_MARKERS)


def _strip_non_primary(text: str) -> str:
    """Remove ``<details>...</details>`` audit blocks, ``data-*`` attrs, and ``${...}`` template expressions.

    Template-literal expressions (``${foo.sandbox_kind}``) contain JS code,
    not displayed copy; only the surrounding static text is user-visible.
    """
    text = _DETAILS_BLOCK_RE.sub(" ", text)
    text = _DATA_ATTR_RE.sub(" ", text)
    text = _strip_template_exprs(text)
    return text


def test_app_js_file_exists() -> None:
    assert APP_JS.is_file(), f"app.js missing at {APP_JS}"


@pytest.mark.parametrize("fn_name", TSR_RENDERER_FUNCTIONS)
def test_tsr_renderer_inline_copy_has_no_eng_token_leak(fn_name: str) -> None:
    src = APP_JS.read_text(encoding="utf-8")
    body = _extract_fn_body(src, fn_name)
    assert body, f"could not extract function body for {fn_name}"

    leaks: list[str] = []
    for m in _STRING_RE.finditer(body):
        raw = m.group("body")
        if not raw.strip():
            continue
        if _looks_like_url_or_fetch_payload(raw):
            continue
        cleaned = _strip_non_primary(raw)
        if not cleaned.strip():
            continue
        for tok in FORBIDDEN_ENG_TOKENS:
            pattern = r"\b" + re.escape(tok) + r"\b"
            if re.search(pattern, cleaned):
                snippet = cleaned.strip()
                if len(snippet) > 140:
                    snippet = snippet[:140] + "…"
                leaks.append(f"{fn_name}: token {tok!r} leaked via {snippet!r}")
    assert not leaks, "engineering tokens leaked into primary-UI copy:\n" + "\n".join(leaks)
