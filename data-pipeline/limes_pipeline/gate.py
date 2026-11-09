"""Validation gate: decides whether a prefecture build may be published.

Checks the JARTIC CSV (format, encoding, coordinates), the built database
(meta, decided segments) and the month-over-month change of both against the
stats of the last published build. Any failure stops publishing; the stats
written here become the baseline for the next build.

Thresholds are provisional (only the 2026-09 release has been seen) and are to
be revisited once a few monthly releases have passed.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from . import jartic
from .inspect import inspect

STATS_FORMAT = 1
# Regulation codes compared with the previous build: speed (112, 114), the
# center line evidence (15, 17) and lanes (20).
COMPARED_CODES = ("112", "114", "15", "17", "20")
# A count may move by this share of the previous one, or by the floor when the
# count is small.
MAX_CHANGE = 0.10
MIN_CHANGE_FLOOR = 20
# Share of 112 rows whose coordinates are missing, unparsable, outside Japan or
# too short to draw.
MAX_BAD_COORDS = 0.01


@dataclass
class Check:
    name: str
    ok: bool
    detail: str


def jartic_stats(csv_path: Path) -> dict:
    report = inspect(csv_path)
    speed = report.targets["112"]
    return {
        "header_columns": report.header_columns,
        "rows": report.rows,
        "short_rows": report.short_rows,
        "versions": dict(report.versions),
        "mojibake_rows": report.mojibake_rows,
        "duplicate_keys": report.duplicate_keys,
        "codes": {code: report.codes.get(code, 0) for code in COMPARED_CODES},
        "bad_coords_112": speed.coords_empty
        + speed.coords_invalid
        + speed.outside_japan
        + speed.short_lines,
    }


def db_stats(db_path: Path) -> dict:
    con = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
    try:
        meta = dict(con.execute("SELECT key, value FROM meta"))
        segments = con.execute("SELECT count(*) FROM segments").fetchone()[0]
        stages = dict(con.execute("SELECT stage, count(*) FROM segments GROUP BY stage"))
    finally:
        con.close()
    return {
        "meta": meta,
        "segments": segments,
        "stages": {str(stage): n for stage, n in sorted(stages.items())},
    }


def target_month(release_meta: dict) -> str | None:
    """"2026年09月" in fetch_jartic's metadata -> "2026-09"."""
    m = re.fullmatch(r"(\d{4})年(\d{1,2})月", release_meta.get("targetMonth") or "")
    return f"{m[1]}-{int(m[2]):02d}" if m else None


def _change(name: str, current: int, previous: int | None) -> Check:
    if previous is None:
        return Check(name, True, f"{current:,} (no previous build)")
    allowed = max(previous * MAX_CHANGE, MIN_CHANGE_FLOOR)
    delta = current - previous
    return Check(
        name,
        abs(delta) <= allowed,
        f"{previous:,} -> {current:,} ({delta:+,}; allowed ±{allowed:,.0f})",
    )


def evaluate(
    prefecture: str,
    csv: dict,
    db: dict,
    previous: dict | None,
    release_meta: dict | None = None,
) -> list[Check]:
    checks = [
        Check(
            "header columns",
            csv["header_columns"] == jartic.EXPECTED_COLUMNS,
            f"{csv['header_columns']} (expected {jartic.EXPECTED_COLUMNS})",
        ),
        Check("short rows", csv["short_rows"] == 0, str(csv["short_rows"])),
        Check(
            "format version",
            set(csv["versions"]) == {jartic.EXPECTED_VERSION},
            ", ".join(f"{v}: {n:,}" for v, n in csv["versions"].items()),
        ),
        Check("undecodable rows", csv["mojibake_rows"] == 0, str(csv["mojibake_rows"])),
        Check("duplicate unique keys", csv["duplicate_keys"] == 0, str(csv["duplicate_keys"])),
        Check("speed regulations (112)", csv["codes"]["112"] > 0, f"{csv['codes']['112']:,}"),
    ]
    speed_rows = csv["codes"]["112"]
    bad_share = csv["bad_coords_112"] / speed_rows if speed_rows else 0.0
    checks.append(
        Check(
            "112 coordinate problems",
            bad_share <= MAX_BAD_COORDS,
            f"{csv['bad_coords_112']:,} ({bad_share:.2%}; allowed {MAX_BAD_COORDS:.0%})",
        )
    )

    meta = db["meta"]
    checks.append(
        Check(
            "database prefecture",
            meta.get("prefecture") == prefecture,
            f"{meta.get('prefecture')!r} (expected {prefecture!r})",
        )
    )
    checks.append(Check("database version", bool(meta.get("version")), repr(meta.get("version"))))
    if release_meta is not None:
        month = target_month(release_meta)
        checks.append(
            Check(
                "database jartic_month",
                month is not None and meta.get("jartic_month") == month,
                f"{meta.get('jartic_month')!r} (release {month!r})",
            )
        )
    checks.append(Check("database segments", db["segments"] > 0, f"{db['segments']:,}"))

    prev_csv = (previous or {}).get("jartic", {})
    prev_db = (previous or {}).get("db", {})
    checks.append(_change("JARTIC rows", csv["rows"], prev_csv.get("rows")))
    for code in COMPARED_CODES:
        checks.append(
            _change(f"code {code}", csv["codes"][code], prev_csv.get("codes", {}).get(code))
        )
    checks.append(_change("segments", db["segments"], prev_db.get("segments")))
    checks.append(
        _change(
            "segments at stage 1 (regulated)",
            db["stages"].get("1", 0),
            prev_db["stages"].get("1", 0) if prev_db else None,
        )
    )
    return checks


def golden(limes_cli: Path) -> Check:
    result = subprocess.run([str(limes_cli), "golden"], capture_output=True, text=True)
    lines = (result.stdout + result.stderr).strip().splitlines()
    return Check("golden decisions", result.returncode == 0, lines[-1] if lines else "")


def render(prefecture: str, checks: list[Check]) -> str:
    failed = [c for c in checks if not c.ok]
    lines = [
        f"# Gate: {prefecture}: {'FAIL' if failed else 'PASS'}",
        "",
        "| Check | Result | Detail |",
        "| --- | --- | --- |",
    ]
    lines += [f"| {c.name} | {'ok' if c.ok else '**FAIL**'} | {c.detail} |" for c in checks]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prefecture")
    parser.add_argument("--csv", type=Path, required=True, help="JARTIC CSV used for the build")
    parser.add_argument("--db", type=Path, required=True, help="database from limes-cli build-db")
    parser.add_argument("--release-meta", type=Path, help="metadata JSON written by fetch_jartic")
    parser.add_argument("--previous", type=Path, help="stats of the last published build")
    parser.add_argument("--limes-cli", type=Path, help="run the golden decision cases with it")
    parser.add_argument("--stats-out", type=Path, required=True, help="stats of this build")
    parser.add_argument("--report", type=Path, help="Markdown report (default: stdout)")
    args = parser.parse_args(argv)

    csv = jartic_stats(args.csv)
    db = db_stats(args.db)
    previous = None
    if args.previous and args.previous.exists():
        previous = json.loads(args.previous.read_text(encoding="utf-8"))
    release_meta = None
    if args.release_meta:
        release_meta = json.loads(args.release_meta.read_text(encoding="utf-8"))

    checks = evaluate(args.prefecture, csv, db, previous, release_meta)
    if args.limes_cli:
        checks.append(golden(args.limes_cli))

    stats = {"format": STATS_FORMAT, "prefecture": args.prefecture, "jartic": csv, "db": db}
    args.stats_out.parent.mkdir(parents=True, exist_ok=True)
    args.stats_out.write_text(json.dumps(stats, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = render(args.prefecture, checks)
    if args.report:
        args.report.write_text(report, encoding="utf-8")
    else:
        sys.stdout.write(report)
    return 0 if all(c.ok for c in checks) else 1
