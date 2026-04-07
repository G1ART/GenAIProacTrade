"""Local migration inventory vs Supabase schema_migrations (when API exposes it)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

_VERSION_PREFIX = re.compile(r"^(\d{14})")


def default_migrations_dir(repo_root: Path | None = None) -> Path:
    root = repo_root or Path(__file__).resolve().parents[2]
    return root / "supabase" / "migrations"


def migration_version_from_stem(stem: str) -> str | None:
    m = _VERSION_PREFIX.match(stem)
    return m.group(1) if m else None


def list_local_migration_files(migrations_dir: Path | None = None) -> list[dict[str, Any]]:
    d = migrations_dir or default_migrations_dir()
    if not d.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    for p in sorted(d.glob("*.sql")):
        stem = p.stem
        ver = migration_version_from_stem(stem)
        rows.append(
            {
                "filename": p.name,
                "path": str(p.resolve()),
                "version": ver,
                "stem": stem,
            }
        )
    return rows


def try_fetch_applied_migration_versions(client: Any) -> tuple[bool, list[str], str | None]:
    """
    Returns (ok, versions, error_message).
    `ok` is False when the history table is not reachable via PostgREST (common on some projects).
    """
    try:
        sch = getattr(client, "schema", None)
        if sch is None:
            return False, [], "client_has_no_schema_accessor"
        r = (
            sch("supabase_migrations")
            .table("schema_migrations")
            .select("version")
            .execute()
        )
        data = r.data or []
        versions: list[str] = []
        for row in data:
            v = row.get("version")
            if v is not None:
                versions.append(str(v))
        return True, versions, None
    except Exception as e:  # noqa: BLE001 — surface to operator as probe failure
        return False, [], str(e)


def report_required_migrations(
    client: Any | None,
    *,
    migrations_dir: Path | None = None,
) -> dict[str, Any]:
    """
    Compare local `supabase/migrations/*.sql` to DB `schema_migrations.version` when available.

    Supabase often stores only the numeric timestamp prefix as `version`.
    """
    local = list_local_migration_files(migrations_dir)
    local_versions = [x["version"] for x in local if x["version"]]

    applied_probe_ok = False
    applied_versions: list[str] = []
    probe_error: str | None = None
    if client is not None:
        applied_probe_ok, applied_versions, probe_error = try_fetch_applied_migration_versions(client)

    applied_set = set(applied_versions)
    missing: list[dict[str, Any]] = []
    if applied_probe_ok:
        for row in local:
            v = row["version"]
            if v and v not in applied_set:
                missing.append(
                    {
                        "filename": row["filename"],
                        "version": v,
                        "reason": "version_not_in_supabase_schema_migrations",
                    }
                )

    return {
        "ok": applied_probe_ok and len(missing) == 0,
        "applied_probe_ok": applied_probe_ok,
        "probe_error": probe_error,
        "applied_versions_count": len(applied_versions),
        "local_files": [x["filename"] for x in local],
        "missing_migrations": missing,
        "hint": (
            "Apply missing files in filename order in Supabase SQL Editor, then re-run."
            if missing
            else (
                "schema_migrations history not readable via API; use verify-db-phase-state smokes as schema truth."
                if not applied_probe_ok
                else "No missing migrations detected vs schema_migrations."
            )
        ),
    }


def generate_migration_bundle_file(
    report: dict[str, Any],
    *,
    out_path: Path,
    migrations_dir: Path | None = None,
) -> dict[str, Any]:
    """Concatenate SQL bodies for `missing_migrations` rows (in local sort order)."""
    d = migrations_dir or default_migrations_dir()
    missing_names = {m["filename"] for m in (report.get("missing_migrations") or [])}
    if not missing_names:
        return {"ok": True, "written": False, "path": str(out_path), "reason": "nothing_missing"}

    lines: list[str] = [
        "-- Operator-closeout bundle: paste into Supabase SQL Editor in one transaction if desired.",
        "-- Review before running; order follows repository filenames.",
        "",
    ]
    for row in list_local_migration_files(d):
        name = row["filename"]
        if name not in missing_names:
            continue
        path = Path(row["path"])
        body = path.read_text(encoding="utf-8")
        lines.append(f"-- === begin {name} ===")
        lines.append(body.rstrip())
        lines.append("")
        lines.append(f"-- === end {name} ===")
        lines.append("")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return {"ok": True, "written": True, "path": str(out_path), "files_included": sorted(missing_names)}
