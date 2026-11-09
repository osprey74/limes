"""Daily release job: detect a new JARTIC release, rebuild the prefectures it
changes, gate them and lay out what to publish.

  release plan  --published DIR [--force] [--only PREF]...
  release build --published DIR --dist DIR --work DIR --limes-cli PATH
  release prune --objects LIST.json --manifest manifest.json

`DIR` mirrors the R2 bucket:

  manifest.json                         prefecture databases the apps read
  <prefecture>-<version>.sqlite.zst
  <prefecture>-<version>.pmtiles        speed-line tiles of the same build
  stats/<prefecture>.json               gate stats, the next build's baseline
  state.json                            JARTIC release each prefecture was built from
  archive/jartic/<release>/typeD_<prefecture>.zip   original ZIPs (JARTIC drops old ones)

`plan` compares the current release (opendata.json) with state.json and writes
the prefectures to build to <work>/plan.json. `build` builds each, copies the
published manifest/state into `--dist` and adds what passed the gate. Each
prefecture stands alone: one that fails keeps its published version, is listed
in <work>/failures.md and is tried again on the next run. Upload `--dist` with
the `.zst`, stats and archive first, then manifest.json, then state.json.

`prune` lists the build files to delete from the bucket: for each prefecture
it keeps the version in the manifest and the newest one before it (an app may
still be downloading it with last month's manifest), and nothing at all when
the manifest is missing. Only `<prefecture>-<version>.sqlite.zst` and
`<prefecture>-<version>.pmtiles` at the top level are considered.

The prefectures to build and their OSM extracts are listed in prefectures.json.
Only extracts that cover exactly one prefecture work until the evidence build
clips to prefecture boundaries.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

import osmium

from . import evidence, fetch, gate

CONFIG = Path(__file__).resolve().parent.parent / "prefectures.json"
OSM_URL = "https://download.geofabrik.de/asia/japan/{region}-latest.osm.pbf"
STATE_FORMAT = 1
# A build's files: the database and its speed tiles, named by prefecture and version.
BUILD_KEY = re.compile(r"^([a-z]+)-(\d{4}-\d{2}\.\d{12})\.(sqlite\.zst|pmtiles)$")


def release_id(entry: dict) -> str:
    """Directory of the release's ZIPs, e.g. "202611010000" from
    "/202611010000/typeD_hokkaido.zip"; it changes with every publication."""
    links = [t["link"] for t in entry.get("targetList", [])]
    if not links:
        raise LookupError("no ZIP links in the release")
    return PurePosixPath(links[0]).parent.name


def read_json(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def plan(entry: dict, state: dict, prefectures: list[str], force: bool = False) -> list[str]:
    """Prefectures whose published build is not from this release."""
    current = release_id(entry)
    built = state.get("prefectures", {})
    available = set(fetch.prefecture_slugs(entry))
    return [
        p
        for p in prefectures
        if p in available and (force or built.get(p, {}).get("release") != current)
    ]


def build_version(target_month: str, now: datetime) -> str:
    """"2026-09.202611091830": JARTIC month, then the build time (UTC)."""
    return f"{target_month}.{now:%Y%m%d%H%M}"


def prune(keys: list[str], manifest: dict) -> list[str]:
    """Build files (databases, tiles) that neither the manifest nor the fallback needs."""
    in_use = {}
    for prefecture, entry in manifest.get("prefectures", {}).items():
        if m := BUILD_KEY.match(entry["path"]):
            in_use[prefecture] = m[2]
    older: dict[tuple[str, str], list[tuple[str, str]]] = {}
    for key in keys:
        m = BUILD_KEY.match(key)
        # Unpublished prefectures and versions newer than the one in use (a
        # build that never reached the manifest) are left alone.
        if m and m[1] in in_use and m[2] < in_use[m[1]]:
            older.setdefault((m[1], m[3]), []).append((m[2], key))
    return sorted(key for found in older.values() for _, key in sorted(found)[:-1])


def osm_date(pbf: Path) -> str | None:
    reader = osmium.io.Reader(str(pbf), osmium.osm.osm_entity_bits.NOTHING)
    try:
        stamp = reader.header().get("osmosis_replication_timestamp")
    finally:
        reader.close()
    return stamp[:10] if stamp else None


def download(url: str, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": fetch.USER_AGENT})
    with urllib.request.urlopen(request, timeout=600) as response, open(out, "wb") as f:
        shutil.copyfileobj(response, f)


def run(args: list[str]) -> None:
    print("$", " ".join(args), flush=True)
    subprocess.run(args, check=True)


def build_one(
    prefecture: str,
    region: str,
    entry: dict,
    published: Path,
    dist: Path,
    work: Path,
    limes_cli: Path,
    now: datetime,
) -> tuple[bool, str]:
    """Build, gate and package one prefecture. Returns (passed, gate report)."""
    raw = work / "raw"
    meta = fetch.fetch(prefecture, raw, entry)
    csv_path = raw / meta["csvPath"]
    zip_name = PurePosixPath(meta["link"]).name
    archive = dist / "archive" / "jartic" / release_id(entry) / zip_name
    archive.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(raw / zip_name, archive)

    pbf = work / "osm" / f"{region}-latest.osm.pbf"
    if not pbf.exists():
        download(OSM_URL.format(region=region), pbf)
    build = work / "build"
    build.mkdir(parents=True, exist_ok=True)
    ndjson = build / f"{prefecture}.ndjson"
    evidence.main(["--pbf", str(pbf), "--jartic", str(csv_path), "--out", str(ndjson)])

    month = gate.target_month(meta)
    if month is None:
        raise ValueError(f"unexpected targetMonth {meta.get('targetMonth')!r}")
    version = build_version(month, now)
    db = build / f"{prefecture}.sqlite"
    db_meta = {"prefecture": prefecture, "version": version, "jartic_month": month}
    if date := osm_date(pbf):
        db_meta["osm_date"] = date
    with open(ndjson, "rb") as stdin:
        args = [str(limes_cli), "build-db", "--out", str(db)]
        for key, value in db_meta.items():
            args += ["--meta", f"{key}={value}"]
        print("$", " ".join(args), flush=True)
        subprocess.run(args, stdin=stdin, check=True)

    stats = work / "stats" / f"{prefecture}.json"
    report = build / f"{prefecture}.gate.md"
    code = gate.main([
        prefecture,
        "--csv", str(csv_path),
        "--db", str(db),
        "--release-meta", str(raw / f"typeD_{prefecture}.meta.json"),
        "--previous", str(published / "stats" / f"{prefecture}.json"),
        "--limes-cli", str(limes_cli),
        "--stats-out", str(stats),
        "--report", str(report),
    ])
    report_text = report.read_text(encoding="utf-8")
    if code != 0:
        return False, report_text

    tiles = build / f"{prefecture}.pmtiles"
    run([str(limes_cli), "tiles", "--db", str(db), "--out", str(tiles)])
    run([str(limes_cli), "package", "--db", str(db), "--tiles", str(tiles), "--out-dir", str(dist)])
    (dist / "stats").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(stats, dist / "stats" / f"{prefecture}.json")
    state = read_json(dist / "state.json", {"format": STATE_FORMAT, "prefectures": {}})
    state["prefectures"][prefecture] = {
        "release": release_id(entry),
        "target_month": month,
        "version": version,
        "built_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    write_json(dist / "state.json", state)
    return True, report_text


def cmd_plan(args: argparse.Namespace) -> int:
    config = read_json(CONFIG, {})
    prefectures = args.only or list(config)
    unknown = [p for p in prefectures if p not in config]
    if unknown:
        raise SystemExit(f"not in {CONFIG.name}: {', '.join(unknown)}")
    entry = fetch.current_release()
    state = read_json(args.published / "state.json", {})
    todo = plan(entry, state, prefectures, args.force)
    write_json(args.work / "plan.json", {"release": entry, "prefectures": todo})
    print(f"release {release_id(entry)} ({entry.get('targetMonth')}): build {todo or 'nothing'}")
    if output := os.environ.get("GITHUB_OUTPUT"):
        with open(output, "a", encoding="utf-8") as f:
            f.write(f"build={'true' if todo else 'false'}\n")
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    config = read_json(CONFIG, {})
    planned = read_json(args.work / "plan.json", None)
    if planned is None:
        raise SystemExit("run `plan` first")
    args.dist.mkdir(parents=True, exist_ok=True)
    for name in ("manifest.json", "state.json"):
        if (args.published / name).exists():
            shutil.copyfile(args.published / name, args.dist / name)

    now = datetime.now(timezone.utc)
    failures: list[str] = []
    for prefecture in planned["prefectures"]:
        try:
            passed, report = build_one(
                prefecture,
                config[prefecture]["osm_region"],
                planned["release"],
                args.published,
                args.dist,
                args.work,
                args.limes_cli,
                now,
            )
        except Exception as e:  # one prefecture's failure must not stop the others
            passed, report = False, f"# Build error: {prefecture}\n\n```text\n{e!r}\n```\n"
        print(report, flush=True)
        if not passed:
            failures.append(report)

    failures_md = args.work / "failures.md"
    if failures:
        failures_md.write_text("\n".join(failures), encoding="utf-8")
    else:
        failures_md.unlink(missing_ok=True)
    return 0


def cmd_prune(args: argparse.Namespace) -> int:
    text = args.objects.read_text(encoding="utf-8") if args.objects.exists() else ""
    listing = json.loads(text) if text.strip() else {}  # the CLI may print nothing for an empty bucket
    keys = [o["Key"] for o in listing.get("Contents") or []]
    manifest = read_json(args.manifest, {})
    stale = prune(keys, manifest)
    builds = sum(1 for k in keys if BUILD_KEY.match(k))
    print(f"{len(keys)} keys listed, {builds} build files, {len(stale)} to delete", file=sys.stderr)
    for key in stale:
        print(key)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("plan")
    p.add_argument("--published", type=Path, required=True, help="copy of the bucket's state.json and stats/")
    p.add_argument("--work", type=Path, default=Path("data/work"))
    p.add_argument("--force", action="store_true", help="rebuild even if built from this release")
    p.add_argument("--only", action="append", help="limit to these prefectures")
    p.set_defaults(func=cmd_plan)
    b = sub.add_parser("build")
    b.add_argument("--published", type=Path, required=True)
    b.add_argument("--dist", type=Path, required=True, help="files to upload")
    b.add_argument("--work", type=Path, default=Path("data/work"))
    b.add_argument("--limes-cli", type=Path, required=True)
    b.set_defaults(func=cmd_build)
    r = sub.add_parser("prune", help="print database keys to delete, one per line")
    r.add_argument("--objects", type=Path, required=True, help="aws s3api list-objects-v2 output")
    r.add_argument("--manifest", type=Path, required=True, help="the manifest just published")
    r.set_defaults(func=cmd_prune)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
