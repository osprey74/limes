"""Prefecture boundaries (OSM admin_level=4, tagged ISO3166-2=JP-xx) from a
Geofabrik region extract, so a region can be split into prefecture databases.

A prefecture's boundary assembles from the region extract it belongs to (all
47 checked against Geofabrik's region polygons, 2026-11-09); neighbours across
a region edge come out incomplete and are skipped.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import osmium
import shapely
from shapely.geometry import mapping, shape


def extract(pbf: Path) -> dict[str, shapely.Geometry]:
    """ISO 3166-2 code -> boundary (lon/lat) of every prefecture that assembles."""
    found = {}
    factory = osmium.geom.WKBFactory()
    processor = osmium.FileProcessor(str(pbf)).with_areas(
        osmium.filter.TagFilter(("boundary", "administrative"))
    )
    for obj in processor:
        if not obj.is_area() or obj.tags.get("admin_level") != "4":
            continue
        iso = obj.tags.get("ISO3166-2", "")
        if iso.startswith("JP-"):
            found[iso] = shapely.from_wkb(factory.create_multipolygon(obj))  # hex string
    return found


def write(boundaries: dict[str, shapely.Geometry], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    features = [
        {"type": "Feature", "properties": {"iso": iso}, "geometry": mapping(geom)}
        for iso, geom in sorted(boundaries.items())
    ]
    out.write_text(json.dumps({"type": "FeatureCollection", "features": features}), encoding="utf-8")


def read(path: Path, iso: str) -> shapely.Geometry:
    data = json.loads(path.read_text(encoding="utf-8"))
    for feature in data["features"]:
        if feature["properties"]["iso"] == iso:
            return shape(feature["geometry"])
    found = ", ".join(f["properties"]["iso"] for f in data["features"])
    raise LookupError(f"{iso} not in {path.name} (found: {found or 'none'})")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pbf", type=Path, required=True, help="Geofabrik region extract")
    parser.add_argument("--out", type=Path, required=True, help="GeoJSON of the prefectures found")
    args = parser.parse_args(argv)
    boundaries = extract(args.pbf)
    write(boundaries, args.out)
    print(f"{', '.join(sorted(boundaries)) or 'no prefectures'} -> {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
