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
