"""Prefecture boundaries (OSM admin_level=4, tagged ISO3166-2=JP-xx), so a
region extract can be split into prefecture databases.

Take them from the whole-Japan extract: a region extract cuts off boundary
ways outside its polygon (Tokyo, Okayama and Fukuoka have sea boundaries
beyond theirs, 2026-11-09). A boundary with any member way or node missing is
skipped. Only the boundary ways' nodes are kept in memory, so the 2.6 GB Japan
extract reads in three passes (relations, ways, nodes) without a location index.
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
    # Pass 1: the prefecture relations and their member ways by role.
    relations: dict[str, dict[str, list[int]]] = {}
    for r in osmium.FileProcessor(str(pbf), osmium.osm.RELATION).with_filter(
        osmium.filter.TagFilter(("boundary", "administrative"))
    ):
        iso = r.tags.get("ISO3166-2", "")
        if r.tags.get("admin_level") == "4" and iso.startswith("JP-"):
            roles: dict[str, list[int]] = {"outer": [], "inner": []}
            for m in r.members:
                if m.type == "w" and m.role in roles:
                    roles[m.role].append(m.ref)
            relations[iso] = roles
    wanted = {w for roles in relations.values() for ids in roles.values() for w in ids}

    # Pass 2: those ways' node lists.
    ways: dict[int, list[int]] = {}
    for w in osmium.FileProcessor(str(pbf), osmium.osm.WAY):
        if w.id in wanted:
            ways[w.id] = [n.ref for n in w.nodes]
    needed = {n for nodes in ways.values() for n in nodes}

    # Pass 3: only their nodes' locations.
    locations: dict[int, tuple[float, float]] = {}
    for n in osmium.FileProcessor(str(pbf), osmium.osm.NODE):
        if n.id in needed:
            locations[n.id] = (n.location.lon, n.location.lat)

    found = {}
    for iso, roles in relations.items():
        lines: dict[str, list[shapely.LineString]] = {}
        try:
            for role, ids in roles.items():
                lines[role] = [shapely.LineString([locations[n] for n in ways[w]]) for w in ids]
        except KeyError:
            continue  # a member way or node is outside this extract
        if area := assemble(lines["outer"], lines["inner"]):
            found[iso] = area
    return found


def assemble(outer: list[shapely.LineString], inner: list[shapely.LineString]) -> shapely.Geometry | None:
    """Polygon from the member ways' lines, or None when the outer rings do not close."""
    polygons, cuts, dangles, invalid = shapely.polygonize_full(outer)
    if polygons.is_empty or not (cuts.is_empty and dangles.is_empty and invalid.is_empty):
        return None
    area = shapely.union_all(list(polygons.geoms))
    if inner:
        holes = shapely.polygonize(inner)
        if not holes.is_empty:
            area = area.difference(shapely.union_all(list(holes.geoms)))
    return area


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
    parser.add_argument("--pbf", type=Path, required=True, help="Geofabrik extract (japan-latest for all 47)")
    parser.add_argument("--out", type=Path, required=True, help="GeoJSON of the prefectures found")
    args = parser.parse_args(argv)
    boundaries = extract(args.pbf)
    write(boundaries, args.out)
    print(f"{', '.join(sorted(boundaries)) or 'no prefectures'} -> {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
