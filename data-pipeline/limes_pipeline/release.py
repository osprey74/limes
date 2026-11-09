"""Daily release job: detect a new JARTIC release, rebuild the prefectures it
changes, gate them and lay out what to publish.

  release plan  --published DIR [--force] [--only PREF]...
  release build --published DIR --dist DIR --work DIR --limes-cli PATH [--region REGION]
  release merge --published DIR --parts DIR --dist DIR --work DIR
  release prune --objects LIST.json --manifest manifest.json

`DIR` mirrors the R2 bucket:

  manifest.json                         prefecture databases the apps read
  <prefecture>-<version>.sqlite.zst
  <prefecture>-<version>.pmtiles        speed-line tiles of the same build
  stats/<prefecture>.json               gate stats, the next build's baseline
  state.json                            JARTIC release each prefecture was built from
  archive/jartic/<release>/typeD_<prefecture>.zip   original ZIPs (JARTIC drops old ones)

`plan` compares the current release (opendata.json) with state.json and writes
the prefectures to build, and their OSM regions, to <work>/plan.json. `build`
builds them (those of one region with `--region`, so regions can run as
parallel jobs), reading each region's OSM extract and prefecture boundaries
once; it copies the published manifest/state into `--dist`, adds what passed
the gate and lists it in <work>/built.json. `merge` combines the `--dist` and
<work> of each region job (`--parts`/<job>/{dist,work}) into one `--dist`,
taking only the prefectures each job built. Each prefecture stands alone: one
that fails keeps its published version, is listed in <work>/failures.md and is
tried again on the next run. Upload `--dist` with the `.zst`, tiles, stats and
archive first, then manifest.json, then state.json.

`prune` lists the build files to delete from the bucket: for each prefecture
it keeps the version in the manifest and the newest one before it (an app may
still be downloading it with last month's manifest), and nothing at all when
the manifest is missing. Only `<prefecture>-<version>.sqlite.zst` and
`<prefecture>-<version>.pmtiles` at the top level are considered.

prefectures.json lists every prefecture with its ISO 3166-2 code and the
Geofabrik region extract that contains it; segments are cut to the prefecture
boundary found in that extract.
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

from . import boundary, evidence, fetch, gate

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


def utc_stamp(now: datetime) -> str:
    return now.strftime("%Y-%m-%dT%H:%M:%SZ")


def load_region(region: str, work: Path) -> tuple[Path, list[evidence.Way], Path]:
    """The region's extract (downloaded once), its car roads and its prefecture boundaries."""
    pbf = work / "osm" / f"{region}-latest.osm.pbf"
    if not pbf.exists():
        download(OSM_URL.format(region=region), pbf)
    boundaries = work / "osm" / f"{region}.boundaries.geojson"
    if not boundaries.exists():
        boundary.write(boundary.extract(pbf), boundaries)
    return pbf, evidence.read_osm(pbf), boundaries


def build_one(
    prefecture: str,
    iso: str,
    region: tuple[Path, list[evidence.Way], Path],
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

    pbf, ways, boundaries = region
    build = work / "build"
    build.mkdir(parents=True, exist_ok=True)
    ndjson = build / f"{prefecture}.ndjson"
    evidence.write_segments(ways, csv_path, ndjson, boundary.read(boundaries, iso))

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
        "built_at": utc_stamp(now),
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
    regions = list(dict.fromkeys(config[p]["osm_region"] for p in todo))
    write_json(args.work / "plan.json", {"release": entry, "prefectures": todo, "regions": regions})
    print(f"release {release_id(entry)} ({entry.get('targetMonth')}): build {todo or 'nothing'}")
    if output := os.environ.get("GITHUB_OUTPUT"):
        with open(output, "a", encoding="utf-8") as f:
            f.write(f"build={'true' if todo else 'false'}\n")
            f.write(f"regions={json.dumps(regions)}\n")
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
    by_region: dict[str, list[str]] = {}
    for prefecture in planned["prefectures"]:
        by_region.setdefault(config[prefecture]["osm_region"], []).append(prefecture)
    if args.region:
        by_region = {args.region: by_region.get(args.region, [])}
    passed: list[str] = []
    failures: list[str] = []
    for region_name, prefectures in by_region.items():
        try:
            region = load_region(region_name, args.work)
        except Exception as e:  # nothing in the region can be built
            failures += [_error_report(p, e) for p in prefectures]
            continue
        for prefecture in prefectures:
            try:
                ok, report = build_one(
                    prefecture,
                    config[prefecture]["iso"],
                    region,
                    planned["release"],
                    args.published,
                    args.dist,
                    args.work,
                    args.limes_cli,
                    now,
                )
            except Exception as e:  # one prefecture's failure must not stop the others
                ok, report = False, _error_report(prefecture, e)
            print(report, flush=True)
            if ok:
                passed.append(prefecture)
            else:
                failures.append(report)
        del region  # free the region's roads before the next one

    write_json(args.work / "built.json", {"regions": list(by_region), "passed": passed})
    failures_md = args.work / "failures.md"
    if failures:
        failures_md.write_text("\n".join(failures), encoding="utf-8")
    else:
        failures_md.unlink(missing_ok=True)
    return 0


def _error_report(prefecture: str, e: Exception) -> str:
    return f"# Build error: {prefecture}\n\n```text\n{e!r}\n```\n"


def merge(published: Path, parts: Path, dist: Path, regions: list[str], now: datetime) -> list[str]:
    """Combine the region jobs' outputs into `dist`; returns the failure reports."""
    dist.mkdir(parents=True, exist_ok=True)
    manifest = read_json(published / "manifest.json", None)
    state = read_json(published / "state.json", {"format": STATE_FORMAT, "prefectures": {}})
    failures: list[str] = []
    done: set[str] = set()
    for part in sorted(p for p in parts.glob("*") if p.is_dir()):
        built = read_json(part / "work" / "built.json", None)
        if built is None:
            continue
        done.update(built["regions"])
        if (part / "work" / "failures.md").exists():
            failures.append((part / "work" / "failures.md").read_text(encoding="utf-8"))
        part_dist = part / "dist"
        for path in part_dist.rglob("*"):
            relative = path.relative_to(part_dist)
            if path.is_file() and relative.as_posix() not in ("manifest.json", "state.json"):
                (dist / relative).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, dist / relative)
        part_manifest = read_json(part_dist / "manifest.json", {})
        part_state = read_json(part_dist / "state.json", {})
        for prefecture in built["passed"]:
            if manifest is None:
                manifest = {k: v for k, v in part_manifest.items() if k != "prefectures"} | {"prefectures": {}}
            manifest["prefectures"][prefecture] = part_manifest["prefectures"][prefecture]
            state["prefectures"][prefecture] = part_state["prefectures"][prefecture]
    for region in regions:
        if region not in done:
            failures.append(f"# Build job failed: {region}\n\nNo output from the {region} job; "
                            "its prefectures keep their published versions.\n")
    if manifest is not None:
        manifest["generated_at"] = utc_stamp(now)
        write_json(dist / "manifest.json", manifest)
    write_json(dist / "state.json", state)
    return failures


def cmd_merge(args: argparse.Namespace) -> int:
    planned = read_json(args.work / "plan.json", None)
    if planned is None:
        raise SystemExit("run `plan` first")
    failures = merge(args.published, args.parts, args.dist, planned["regions"], datetime.now(timezone.utc))
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
    b.add_argument("--region", help="only the planned prefectures of this OSM region")
    b.set_defaults(func=cmd_build)
    m = sub.add_parser("merge", help="combine the region jobs' outputs")
    m.add_argument("--published", type=Path, required=True)
    m.add_argument("--parts", type=Path, required=True, help="one directory per job, each with dist/ and work/")
    m.add_argument("--dist", type=Path, required=True)
    m.add_argument("--work", type=Path, default=Path("data/work"), help="holds plan.json; gets failures.md")
    m.set_defaults(func=cmd_merge)
    r = sub.add_parser("prune", help="print database keys to delete, one per line")
    r.add_argument("--objects", type=Path, required=True, help="aws s3api list-objects-v2 output")
    r.add_argument("--manifest", type=Path, required=True, help="the manifest just published")
    r.set_defaults(func=cmd_prune)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
