# data-pipeline

JARTIC traffic regulation data (and later OSM / GSI road data) ingestion for Limes. Requires [uv](https://docs.astral.sh/uv/).

```sh
uv sync
uv run pytest

# Download the current release for one prefecture into data/raw/ (gitignored)
uv run python scripts/fetch_jartic.py hokkaido --out-dir data/raw

# Phase 0 report
uv run python scripts/inspect_jartic.py data/raw/typeD_hokkaido.csv \
  --meta data/raw/typeD_hokkaido.meta.json \
  --bbox 139.3,41.3,148.9,45.6 \
  --out ../docs/phase0/jartic-hokkaido-202609.md
```

Prefecture slugs are the ones in the ZIP names (`hokkaido`, `tokyo`, `gumma`, ...). An unknown slug prints the available list.

```sh
# All 47 prefectures, one row each (downloads ~320 MB; CSVs are deleted after inspection)
uv run python scripts/survey_jartic.py --out-dir data/survey --report ../docs/phase0/jartic-survey-202609.md

# Apply the decision stages to OSM ways in a test area (OSM via Overpass, GSI road width tiles)
uv run python scripts/mesh_check.py --jartic data/raw/typeD_hokkaido.csv \
  --jartic-meta data/raw/typeD_hokkaido.meta.json \
  --center 141.35,43.09 --tiles 6 --report ../docs/phase0/mesh-sapporo-kita24.md
```

`mesh_check` also writes `data/mesh/<area>/result.geojson` for viewing in QGIS.

```sh
# Street-level images for the ways mesh_check flags (needs a Mapillary client token, read scope)
MAPILLARY_TOKEN=MLY|... uv run python scripts/mapillary_check.py collect --work data/mesh/16_58496_24055_6 \
  --area 札幌市北区 [--judged earlier-judgments.json]
# Open data/mesh/<area>/mapillary_review.html, judge each way, export judgments.json, then:
uv run python scripts/mapillary_check.py summarize --work data/mesh/16_58496_24055_6 \
  --judgments judgments.json [more.json ...] --report ../docs/phase0/mapillary-sapporo-kita24.md
```

Groups larger than `--max-per-group` (default 60) are randomly sampled; the report gives each group's size so the sampled share can be applied to it. The review page links signed, expiring Mapillary thumbnails (CC BY-SA) and stays local under `data/`.

## Phase 1: prefecture database

```sh
# OSM extract (Geofabrik regions; Hokkaido is one prefecture)
curl -L -o data/osm/hokkaido-latest.osm.pbf https://download.geofabrik.de/asia/japan/hokkaido-latest.osm.pbf
# Evidence per road segment (<= 200 m), one JSON line each
uv run python scripts/build_evidence.py --pbf data/osm/hokkaido-latest.osm.pbf \
  --jartic data/raw/typeD_hokkaido.csv --out data/build/hokkaido.ndjson
# Decide with limes-core and write the SQLite (R*Tree) the apps read
(cd ../core && cargo build --release -p limes-cli)
../core/target/release/limes-cli build-db --out data/build/hokkaido.sqlite \
  --meta prefecture=hokkaido --meta version=2026-09.20261109 \
  --meta jartic_month=2026-09 --meta osm_date=2026-11-08 < data/build/hokkaido.ndjson
# Validation gate: exits 1 when the build must not be published
uv run python scripts/gate.py hokkaido --csv data/raw/typeD_hokkaido.csv \
  --db data/build/hokkaido.sqlite --release-meta data/raw/typeD_hokkaido.meta.json \
  --previous data/published/stats/hokkaido.json --limes-cli ../core/target/release/limes-cli \
  --stats-out data/dist/stats/hokkaido.json --report data/build/hokkaido.gate.md
# Speed-line vector tiles for the speed map (PMTiles, z5-14)
../core/target/release/limes-cli tiles --db data/build/hokkaido.sqlite --out data/build/hokkaido.pmtiles
# Compress for publishing and add the entry (with the tiles) to data/dist/manifest.json
../core/target/release/limes-cli package --db data/build/hokkaido.sqlite   --tiles data/build/hokkaido.pmtiles --out-dir data/dist
```

`--bbox west,south,east,north` limits `build_evidence` to a test area.

The gate fails the build when any of these does not hold (thresholds in `limes_pipeline/gate.py`; provisional until a few monthly releases have been compared):

| Check | Condition |
| --- | --- |
| JARTIC format | 170 header columns, no short rows, every row version `k_2.1`, no undecodable bytes, no duplicate unique keys (all 47 prefectures met these in the 2026-09 release) |
| Speed regulations | At least one 112 row; missing, unparsable, out-of-Japan or one-point coordinates in at most 1% of them |
| Database | Meta `prefecture` matches, `version` is set, `jartic_month` equals the release's target month; at least one segment |
| Month over month | JARTIC rows, codes 112/114/15/17/20, segments and stage-1 segments each within ±10% of the last published build (±20 for small counts); skipped on the first build |
| Decisions | `limes-cli golden` passes |

The stats written by `--stats-out` are published with the build and become `--previous` for the next one.

`version` (`[A-Za-z0-9._-]`) names the build; the app downloads a prefecture again when the manifest's version differs from the one it holds. `package` writes `<prefecture>-<version>.sqlite.zst` (zstd level 19 by default; Hokkaido 208 MB -> 44 MB) with its size, sha256 and decompressed size in the manifest. Upload the `.zst` files first and `manifest.json` last.

## Daily release job

`.github/workflows/data-release.yml` runs every day at 06:30 JST (and by hand with `force` / `only`). It downloads `state.json`, `manifest.json` and `stats/` from the R2 bucket, then:

```sh
uv run python scripts/release.py plan --published data/published
uv run python scripts/release.py build --published data/published --dist data/dist \
  --limes-cli ../core/target/release/limes-cli
```

`plan` reads the current release from `opendata.json` and picks the prefectures in `prefectures.json` that were not built from it. `build` fetches the JARTIC ZIP (kept under `archive/jartic/<release>/` because JARTIC removes old releases), downloads the Geofabrik extract, builds the evidence and database, runs the gate and packages what passed into `data/dist`. A prefecture that fails keeps its published version, goes to `data/work/failures.md` (posted to one open GitHub issue) and is tried again the next day. The job uploads the databases, stats and archive first, then `manifest.json`, then `state.json`, and finally deletes old databases and tiles (`release.py prune`): per prefecture it keeps the version in the manifest and the one before it, which an app may still be fetching with the previous manifest. Keys other than `<prefecture>-<version>.sqlite.zst` and `.pmtiles` (the archive, `map/`) are never deleted.

The speed tiles have one layer, `speed`, with `speed`, `conf` (high/mid/low), `class` (motorway, trunk, primary, secondary, tertiary, minor, service) and `td` = 1 when the speed depends on date or time. Major roads appear from z5-z10 by class, local roads from z12 and service roads at z14 (overzoomed beyond). Consecutive segments with the same properties are joined, so features carry no id: the app looks up the segment under a tap in its database. Hokkaido: 24.5 MB, about 3 s.

Bucket layout:

| Key | Content |
| --- | --- |
| `manifest.json` | Prefecture databases the apps read (`Cache-Control: no-cache`) |
| `<prefecture>-<version>.sqlite.zst` | Database; `version` is `<JARTIC month>.<UTC build time>` |
| `<prefecture>-<version>.pmtiles` | Speed-line tiles of the same build (`tiles` in the manifest entry) |
| `stats/<prefecture>.json` | Gate stats of the published build |
| `state.json` | JARTIC release each prefecture was built from |
| `archive/jartic/<release>/typeD_<prefecture>.zip` | Original JARTIC ZIPs |

Repository settings: secrets `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` (an R2 API token with Object Read & Write on the bucket) and variable `R2_BUCKET`.

Only Hokkaido is listed in `prefectures.json`: its Geofabrik extract is exactly one prefecture, and the evidence build does not yet clip other regions to prefecture boundaries.
