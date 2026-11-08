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
