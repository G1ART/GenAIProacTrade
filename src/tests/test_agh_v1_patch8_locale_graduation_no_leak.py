"""AGH v1 Patch 8 A4+D1 — "demo" → "sample" graduation leak scanner.

Rationale: the frozen investor pack is now called *sample*, not *demo*.
The word "demo" implies throw-away UI; the bundle is live seed data. We
must therefore keep the public primary UI free of the literal tokens
"(demo)" / "(데모)" (user-facing parenthetical), while still allowing
the term to survive in:

    • code comments,
    • docstrings,
    • legacy-alias keys documented inside ``LEGACY_LOCALE_ALIASES``,
    • snapshot JSON fixtures referenced by the legacy alias table.

Scope: canonical locale strings (values), not keys.
"""

from __future__ import annotations

from pathlib import Path

from phase47_runtime.phase47e_user_locale import (
    HOME_FEED,
    LEGACY_LOCALE_ALIASES,
    SECTION_PAYLOAD,
    SHELL,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

FORBIDDEN_PHRASES: tuple[str, ...] = (
    "(demo)",
    "(Demo)",
    "(DEMO)",
    "(데모)",
)


def _all_locale_strings() -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    for bucket_name, bucket in (
        ("SHELL", SHELL),
        ("HOME_FEED", HOME_FEED),
        ("SECTION_PAYLOAD", SECTION_PAYLOAD),
    ):
        for lang, flat in bucket.items():
            for k, v in flat.items():
                if not isinstance(v, str):
                    continue
                rows.append((f"{bucket_name}[{lang}]::{k}", k, v))
    return rows


def test_locale_values_do_not_contain_demo_parenthetical() -> None:
    leaks: list[str] = []
    for where, _key, val in _all_locale_strings():
        for phrase in FORBIDDEN_PHRASES:
            if phrase in val:
                leaks.append(f"{where} contains forbidden '{phrase}': {val!r}")
    assert not leaks, (
        "'(demo)' / '(데모)' graduated to 'sample' in Patch 8 — found leaks:\n"
        + "\n".join(leaks)
    )


def test_legacy_demo_aliases_resolve_to_sample_keys() -> None:
    assert LEGACY_LOCALE_ALIASES, "expected non-empty legacy alias table"
    for legacy_key, canonical_key in LEGACY_LOCALE_ALIASES.items():
        assert "demo" in legacy_key, (
            f"alias legacy key should contain 'demo': {legacy_key!r}"
        )
        assert "sample" in canonical_key, (
            f"alias canonical target should contain 'sample': {canonical_key!r}"
        )


def test_legacy_alias_keys_resolve_via_t() -> None:
    """t() must transparently route legacy *.demo.* keys to *.sample.* values."""
    from phase47_runtime.phase47e_user_locale import t

    for legacy_key in LEGACY_LOCALE_ALIASES:
        for lang in ("ko", "en"):
            val = t(lang, legacy_key)
            assert val and val != legacy_key, (
                f"legacy alias {legacy_key!r} did not resolve to a value "
                f"in lang={lang}"
            )
