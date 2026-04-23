"""Shared helpers for Product Shell view-model composers (Patch 10B).

Patch 10B splits the single-file view-model from Patch 10A into one
module per surface (Today / Research / Replay / Ask AI). This module
holds the helpers that are reused across all four composers so that the
invariants stay centralized:

- :func:`strip_engineering_ids` — last-line regex scrub; no DTO should
  ever leave the Product Shell surface without passing through this.
- :func:`spectrum_position_to_grade` / :func:`spectrum_position_to_stance` /
  :func:`horizon_provenance_to_confidence` — atomic mappers from internal
  numerics to product-facing labels.
- :func:`family_alias` — founder-facing family name lookup (never the
  raw engineering family slug).
- :func:`human_relative_time` — timestamp → "방금 갱신" / "3h ago".

Patch 10A composers (``view_models.py``) re-export these helpers under
their original underscored names for backwards compatibility; tests
continue to import them from :mod:`phase47_runtime.product_shell.view_models`.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from metis_brain.bundle import BrainBundleV0


HORIZON_KEYS: tuple[str, ...] = ("short", "medium", "medium_long", "long")


HORIZON_DEFAULT_LABELS: dict[str, dict[str, str]] = {
    "ko": {
        "short":       "오늘~이번 주",
        "medium":      "이번 달",
        "medium_long": "한 분기",
        "long":        "반 년 이상",
    },
    "en": {
        "short":       "today / this week",
        "medium":      "this month",
        "medium_long": "this quarter",
        "long":        "half-year +",
    },
}


HORIZON_CAPTION: dict[str, dict[str, str]] = {
    "ko": {
        "short":       "단기",
        "medium":      "중기",
        "medium_long": "중장기",
        "long":        "장기",
    },
    "en": {
        "short":       "Short",
        "medium":      "Medium",
        "medium_long": "Medium-long",
        "long":        "Long",
    },
}


PROVENANCE_TO_SOURCE_KEY: dict[str, str] = {
    "real_derived":                          "live",
    "real_derived_with_degraded_challenger": "live_with_caveat",
    "template_fallback":                     "sample",
    "insufficient_evidence":                 "preparing",
}


# ---------------------------------------------------------------------------
# Engineering-ID scrubber (last-line defense)
# ---------------------------------------------------------------------------

ENG_ID_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bart_[A-Za-z0-9_]+\b"),
    re.compile(r"\breg_[A-Za-z0-9_]+\b"),
    re.compile(r"\bfactor_[A-Za-z0-9_]+\b"),
    re.compile(r"\bpkt_[A-Za-z0-9_]+\b"),
    re.compile(r"\bjob_[A-Za-z0-9_]+\b"),
    re.compile(r"\bpit:demo:[A-Za-z0-9_:\-]+\b"),
    re.compile(
        r"\b(?:registry_entry_id|artifact_id|proposal_packet_id|"
        r"decision_packet_id|replay_lineage_pointer|sandbox_request_id|"
        r"sandbox_result_id)\b"
    ),
    re.compile(r"\bhorizon_provenance\b"),
    re.compile(
        r"\b(?:real_derived_with_degraded_challenger|real_derived|"
        r"insufficient_evidence|template_fallback)\b"
    ),
    re.compile(r"\bprocess_governed_prompt\b"),
    re.compile(r"\bcounterfactual_preview_v1\b"),
    re.compile(r"\bsandbox_queue\b"),
    re.compile(r"\b[a-zA-Z_]+_v\d+\b"),
)


def strip_engineering_ids(obj: Any) -> Any:
    """Recursively scrub engineering tokens from string *values* in ``obj``.

    Keys are preserved because DTO schemas use product-level names; only
    string values are rewritten. When a token matches, it is replaced
    with ``[redacted]``. On a clean DTO the replacement never fires — the
    scrubber is a last-line defense that CI regression tests also run
    against every freeze artifact.
    """
    if isinstance(obj, str):
        cleaned = obj
        for pat in ENG_ID_PATTERNS:
            cleaned = pat.sub("[redacted]", cleaned)
        return cleaned
    if isinstance(obj, dict):
        return {k: strip_engineering_ids(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [strip_engineering_ids(v) for v in obj]
    if isinstance(obj, tuple):
        return tuple(strip_engineering_ids(v) for v in obj)
    return obj


# ---------------------------------------------------------------------------
# Atomic mappers: grade, stance, confidence
# ---------------------------------------------------------------------------


def spectrum_position_to_grade(
    position: float | None,
    *,
    source_key: str,
) -> dict[str, str]:
    """Map a representative ``spectrum_position`` into a grade chip.

    Grade encodes **how confidently the product is willing to speak**
    about this horizon — it combines signal magnitude with evidence
    quality. See ``view_models.py`` Patch 10A notes for the tier logic.
    """
    if source_key == "preparing":
        return {"key": "f", "label": "F"}
    if source_key == "sample":
        return {"key": "d", "label": "D"}
    if position is None:
        return {"key": "c", "label": "C"}
    mag = abs(float(position))
    if source_key == "live_with_caveat" and mag < 0.2:
        return {"key": "c", "label": "C"}
    if mag >= 0.8:
        return {"key": "a_plus", "label": "A+"}
    if mag >= 0.5:
        return {"key": "a", "label": "A"}
    if mag >= 0.2:
        return {"key": "b", "label": "B"}
    return {"key": "c", "label": "C"}


def spectrum_position_to_stance(
    position: float | None,
    *,
    lang: str,
) -> dict[str, str]:
    """Map a representative ``spectrum_position`` into a directional label.

    Stance is direction-only — never an imperative. Symmetric around
    zero and monotonic in position.
    """
    if position is None:
        key = "neutral"
    else:
        p = float(position)
        if p >= 0.5:
            key = "strong_long"
        elif p >= 0.2:
            key = "long"
        elif p > -0.2:
            key = "neutral"
        elif p > -0.5:
            key = "short"
        else:
            key = "strong_short"
    label_ko = {
        "strong_long":  "강한 매수 경향",
        "long":         "매수 경향",
        "neutral":      "중립",
        "short":        "매도 경향",
        "strong_short": "강한 매도 경향",
    }
    label_en = {
        "strong_long":  "Strong long bias",
        "long":         "Long bias",
        "neutral":      "Neutral",
        "short":        "Short bias",
        "strong_short": "Strong short bias",
    }
    label = label_ko.get(key, "") if lang == "ko" else label_en.get(key, "")
    return {"key": key, "label": label}


def horizon_provenance_to_confidence(
    provenance_entry: dict[str, Any] | None,
    *,
    lang: str,
) -> dict[str, str]:
    """Translate a ``horizon_provenance[hz]`` block into a confidence badge.

    The DTO surfaces ``source_key`` for CSS targeting and ``label`` /
    ``tooltip`` for user-visible text. The raw engineering enum
    (``real_derived`` and siblings) is deliberately dropped.
    """
    raw_src = ""
    if provenance_entry is not None and isinstance(provenance_entry, dict):
        raw_src = str(provenance_entry.get("source") or "").strip()
    source_key = PROVENANCE_TO_SOURCE_KEY.get(raw_src, "preparing")
    ko_labels = {
        "live":             ("실데이터 근거",
                             "실제 시장 데이터로 학습된 모델 출력입니다."),
        "live_with_caveat": ("실데이터 근거 (보조 지표 제한)",
                             "실데이터 근거이지만 보조 지표 일부가 기대치에 못 미칩니다."),
        "sample":           ("샘플 시나리오",
                             "실데이터가 아직 충분하지 않아 샘플 시나리오를 보여 드립니다."),
        "preparing":        ("실데이터 준비 중",
                             "이 구간의 실데이터 근거는 수집·학습 중입니다. 제품은 과장된 확신을 드리지 않습니다."),
    }
    en_labels = {
        "live":             ("Live-data evidence",
                             "Model output trained on real market data."),
        "live_with_caveat": ("Live with caveats",
                             "Real-data evidence, but companion signals are below threshold."),
        "sample":           ("Sample scenario",
                             "Live data is not yet sufficient; showing a labelled sample scenario."),
        "preparing":        ("Live data preparing",
                             "Evidence for this horizon is still being gathered. No overconfident claim is made."),
    }
    label_map = ko_labels if lang == "ko" else en_labels
    label, tooltip = label_map.get(source_key, label_map["preparing"])
    return {
        "source_key": source_key,
        "label": label,
        "tooltip": tooltip,
    }


# ---------------------------------------------------------------------------
# Spectrum-row helpers
# ---------------------------------------------------------------------------


def best_representative_row(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Pick the row with the largest ``|spectrum_position|``."""
    best: dict[str, Any] | None = None
    best_mag: float = -1.0
    for r in rows or []:
        try:
            p = float(r.get("spectrum_position") or 0.0)
        except (TypeError, ValueError):
            continue
        mag = abs(p)
        if mag > best_mag:
            best_mag = mag
            best = r
    return best


def family_alias(
    bundle: BrainBundleV0 | None,
    horizon: str,
    *,
    lang: str,
) -> str:
    """Return a customer-facing family name for ``horizon``.

    Uses the founder-facing alias from the active registry entry /
    artifact (``display_family_name_ko`` / ``display_family_name_en``).
    Never returns the raw family slug.
    """
    if bundle is None:
        return ""
    by_art = {a.artifact_id: a for a in bundle.artifacts}
    for ent in bundle.registry_entries:
        if ent.status != "active" or ent.horizon != horizon:
            continue
        art = by_art.get(ent.active_artifact_id)
        if lang == "ko":
            return (
                (getattr(art, "display_family_name_ko", "") if art else "")
                or str(getattr(ent, "display_family_name_ko", "") or "")
                or ""
            )
        return (
            (getattr(art, "display_family_name_en", "") if art else "")
            or str(getattr(ent, "display_family_name_en", "") or "")
            or ""
        )
    return ""


def human_relative_time(utc_str: str, *, now_utc: str, lang: str) -> str:
    """Render a UTC timestamp as a ``X분 전 갱신`` / ``Xm ago`` string.

    Returns ``—`` for malformed or empty input.
    """
    if not utc_str:
        return "—"
    try:
        s = utc_str.replace("Z", "+00:00")
        then = datetime.fromisoformat(s)
        if then.tzinfo is None:
            then = then.replace(tzinfo=timezone.utc)
        now_s = now_utc.replace("Z", "+00:00")
        now = datetime.fromisoformat(now_s)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return "—"
    delta_s = max(0, int((now - then).total_seconds()))
    mins = delta_s // 60
    hours = mins // 60
    days = hours // 24
    if lang == "ko":
        if days >= 1:
            return f"{days}일 전 갱신"
        if hours >= 1:
            return f"{hours}시간 전 갱신"
        if mins >= 1:
            return f"{mins}분 전 갱신"
        return "방금 갱신"
    if days >= 1:
        return f"{days}d ago"
    if hours >= 1:
        return f"{hours}h ago"
    if mins >= 1:
        return f"{mins}m ago"
    return "just now"
