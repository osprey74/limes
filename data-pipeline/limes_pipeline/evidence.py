"""Phase 1: per-segment evidence for a whole prefecture, for limes-cli to decide.

Reads an OSM extract (.osm.pbf) and the prefecture's JARTIC CSV, splits car
roads into segments of at most SEGMENT_M, and writes one JSON line per segment:
the OSM attributes, the geometry and the evidence fields of limes-core's
WayEvidence (regulations with their raw condition blocks, center-line evidence,
road type, separation). No decision is made here; `limes-cli build-db` does it.

Matching rules carried over from Phase 0 (docs/phase0/findings.md):
- ways are cut where a JARTIC line starts or ends (or crosses a 114 area's edge),
  so one OSM way can carry different speeds along its length
- a JARTIC line belongs to a segment when its ±MATCH_BUFFER_M buffer covers at
  least MATCH_COVERAGE of the segment, but only on the road it was drawn for:
  of parallel roads sharing a stretch of the line, the one covering most of
  the line keeps it, and a road clearly closer to a stretch takes it there.
  An elevated expressway's regulation so stays off the road beneath it
  (Sapporo Shindo under the Sasson Expressway, field test 2026-11-10). A 114
  area belongs to a segment when it contains the midpoint (minus NO.30)
- JARTIC 17 counts as a center line only with side code 3 (both) or blank
- separated: a one-way major road with an opposite one-way within DUAL_CARRIAGEWAY_M

With --boundary (a region extract split into prefectures), a segment belongs to
the prefecture that contains its midpoint, so each segment is in exactly one
prefecture's database; ways near the edge still serve as evidence (e.g. the
opposite carriageway) for the segments inside.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import osmium
import shapely
from shapely import STRtree
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import substring

from . import boundary, jartic
from .jartic import Col
from .mesh_check import (
    CAR_HIGHWAYS,
    DUAL_CARRIAGEWAY_M,
    MAJOR_HIGHWAYS,
    MATCH_BUFFER_M,
    MATCH_COVERAGE,
    LocalProjection,
    angle_between,
    bearing,
)

# highway=track (mostly unpaved farm and forest tracks) is left out (decided 2026-11-09):
# they are roads under 道路交通法第2条 when open to the public, but OSM can't tell, and
# they made up a fifth of Hokkaido's database. Paved farm roads are tagged as ordinary roads.
ROAD_HIGHWAYS = (CAR_HIGHWAYS - {"track"}) | {"service"}
def road_id(way: "Way") -> tuple[str, str]:
    """Ways of one road: same class (links with their road) and route number,
    or same name when unnumbered, so both carriageways count as one."""
    base = way.highway.removesuffix("_link")
    ref = way.tags.get("ref", "")
    return (base, "ref:" + ref) if ref else (base, "name:" + way.tags.get("name", ""))


def shared_length(line, area) -> float:
    """Length of `line` inside `area`. GEOS can reject a union of buffers as
    invalid (TopologyException, seen in Akita); then the repaired shapes,
    and last the shapes snapped to a 1 cm grid (all in metres), do."""
    try:
        return line.intersection(area).length
    except shapely.errors.GEOSException:
        pass
    try:
        return shapely.make_valid(line).intersection(shapely.make_valid(area)).length
    except shapely.errors.GEOSException:
        return shapely.intersection(line, area, grid_size=0.01).length


# A JARTIC line goes to another road instead when that road is this much
# closer on average (metres) and at most this share of the distance.
COMPETITOR_MARGIN_M = 3.0
COMPETITOR_RATIO = 0.6
SEGMENT_M = 200.0
MIN_PIECE_M = 10.0  # cut points closer than this to each other or to an end are dropped
TILE_ZOOM = 10  # about 30 km tiles; each gets its own local projection
SPEED_CODES = {"112", "113", "114"}
CENTER_CODES = {"15": "jartic_center_line", "20": "jartic_lanes", "17": "jartic_no_overtaking"}
NO_OVERTAKING_SIDES = {"", "3"}  # 3 = both sides; blank = not one-sided
ROAD_TYPES = {"2": "expressway", "3": "motor_road"}
ONEWAY = {"yes", "1", "-1"}
OSM_TAGS = ("name", "ref", "oneway", "lanes", "lane_markings", "motorroad", "maxspeed", "service")
BLOCK_FIELDS = ("period_start", "period_end", "time_start", "time_end", "weekday",
                "vehicle_a", "vehicle_b", "vehicle_c", "vehicle_d")
TARGET_START, EXCLUSION_START = 41, 86


# --- input -------------------------------------------------------------------

@dataclass
class Way:
    osm_id: int
    highway: str
    tags: dict[str, str]
    coords: list[tuple[float, float]]


def read_osm(pbf: Path) -> list[Way]:
    ways = []
    # Nodes must be read for the location cache; the tag filter then drops them.
    processor = (osmium.FileProcessor(str(pbf), osmium.osm.NODE | osmium.osm.WAY)
                 .with_locations()
                 .with_filter(osmium.filter.EntityFilter(osmium.osm.WAY))
                 .with_filter(osmium.filter.TagFilter(*(("highway", h) for h in sorted(ROAD_HIGHWAYS)))))
    for w in processor:
        if w.tags.get("area") == "yes":
            continue
        try:
            coords = [(n.lon, n.lat) for n in w.nodes]
        except osmium.InvalidLocationError:
            continue
        if len(coords) >= 2:
            tags = {k: w.tags[k] for k in OSM_TAGS if k in w.tags}
            ways.append(Way(w.id, w.tags["highway"], tags, coords))
    return ways


def _blocks(row: list[str], start: int) -> list[dict]:
    blocks = []
    for b in range(jartic.CONDITION_BLOCKS):
        base = start + b * jartic.CONDITION_WIDTH
        values = {name: jartic.field(row, base + i) for i, name in enumerate(BLOCK_FIELDS)}
        if any(values.values()):
            blocks.append(values)
    return blocks


@dataclass
class Regulation:
    code: str
    key: str
    speed: int
    road_type: str
    side: str
    conditions: dict
    lines: list[LineString]  # lon/lat
    area: shapely.Geometry | None  # lon/lat polygon minus excluded parts (114)


def read_jartic(csv_path: Path) -> list[Regulation]:
    regulations = []
    _, rows = jartic.open_rows(csv_path)
    for row in rows:
        code = jartic.field(row, Col.REGULATION_CODE)
        if code not in SPEED_CODES and code not in CENTER_CODES:
            continue
        if jartic.field(row, Col.UPDATE_CLASS) == jartic.UPDATE_CLASS_ABOLISHED:
            continue
        try:
            sections = jartic.parse_coords(jartic.field(row, Col.COORDS))
            excluded = jartic.parse_coords(jartic.field(row, Col.EXCLUDED_COORDS))
        except ValueError:
            continue
        speed = jartic.field(row, Col.SPEED)
        if code in SPEED_CODES and not speed.isdigit():
            continue
        lines, area = [], None
        if jartic.field(row, Col.GEOMETRY_TYPE) == "3":
            polygons = [Polygon(s) for s in sections if len(s) >= 4]
            if not polygons:
                continue
            area = shapely.union_all([shapely.make_valid(p) for p in polygons])
            holes = [shapely.make_valid(Polygon(s)) for s in excluded if len(s) >= 4]
            if holes:
                area = area.difference(shapely.union_all(holes))
        else:
            lines = [LineString(s) for s in sections if len(s) >= 2]
            if not lines:
                continue
        regulations.append(Regulation(
            code=code,
            key=jartic.field(row, Col.UNIQUE_KEY),
            speed=int(speed) if speed.isdigit() else 0,
            road_type=ROAD_TYPES.get(jartic.field(row, Col.ROAD_TYPE), ""),
            side=jartic.field(row, Col.SIDE),
            conditions={"targets": _blocks(row, TARGET_START), "exclusions": _blocks(row, EXCLUSION_START),
                        "note": jartic.field(row, 131)},
            lines=lines,
            area=area,
        ))
    return regulations


# --- matching ----------------------------------------------------------------

def tile_of(lon: float, lat: float, z: int = TILE_ZOOM) -> tuple[int, int]:
    n = 2**z
    x = int((lon + 180) / 360 * n)
    y = int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n)
    return x, y


def split(line: LineString, max_len: float = SEGMENT_M, cuts: list[float] | None = None) -> list[LineString]:
    """Cut at the given distances along the line (where a regulation starts or ends),
    then split each part into equal pieces no longer than max_len (projected meters)."""
    stops = [0.0]
    for d in sorted(cuts or []):
        if MIN_PIECE_M <= d <= line.length - MIN_PIECE_M and d - stops[-1] >= MIN_PIECE_M:
            stops.append(d)
    stops.append(line.length)
    pieces = []
    for start, end in zip(stops, stops[1:]):
        n = max(1, math.ceil((end - start) / max_len))
        step = (end - start) / n
        pieces += [substring(line, start + i * step, start + (i + 1) * step) for i in range(n)]
    return pieces


class Matcher:
    """Spatial indexes over the prefecture's regulations and one-way major roads (lon/lat)."""

    def __init__(self, regulations: list[Regulation], ways: list[Way]):
        self.line_owner, line_geoms = [], []
        self.area_owner, area_geoms = [], []
        for i, r in enumerate(regulations):
            if r.area is not None:
                self.area_owner.append(i)
                area_geoms.append(r.area)
            for line in r.lines:
                self.line_owner.append(i)
                line_geoms.append(line)
        self.regulations = regulations
        self.lines = line_geoms
        self.line_tree = STRtree(line_geoms)
        self.areas = area_geoms
        self.area_tree = STRtree(area_geoms)
        self.ways = ways
        self.way_lines = [LineString(w.coords) for w in ways]
        self.way_tree = STRtree(self.way_lines)
        # (line, road) pairs where the line belongs to a parallel road.
        self.foreign = {(j, rid) for j, line in enumerate(line_geoms) for rid in self.parallel_roads(line)}
        self.oneway_major = [w for w in ways if w.highway in MAJOR_HIGHWAYS and w.tags.get("oneway") in ONEWAY]
        self.oneway_lines = [LineString(w.coords) for w in self.oneway_major]
        self.oneway_tree = STRtree(self.oneway_lines)

    def cuts(self, line_ll: LineString, line: LineString, proj: LocalProjection) -> list[float]:
        """Distances along the way where a speed or center-line regulation begins or ends."""
        def m(lon, lat):
            return Point(proj(lon, lat))

        margin = (MATCH_BUFFER_M + 5) / 111_000 * 2
        search = box(*line_ll.bounds).buffer(margin)
        cuts = []
        for j in self.line_tree.query(search):
            ends = self.lines[j].coords
            for end in (ends[0], ends[-1]):
                point = m(*end)
                if line.distance(point) <= MATCH_BUFFER_M:
                    cuts.append(line.project(point))
        for j in self.area_tree.query(search):
            if self.regulations[self.area_owner[j]].code not in SPEED_CODES:
                continue
            crossing = line_ll.intersection(self.areas[j].boundary)
            for point in getattr(crossing, "geoms", [crossing]):
                # No crossing can come back as an empty point (seen in Aichi).
                if isinstance(point, Point) and not point.is_empty:
                    cuts.append(line.project(m(point.x, point.y)))
        return cuts

    def parallel_roads(self, line_ll: LineString) -> list[tuple[str, str]]:
        """Roads that share a stretch of this JARTIC line with the road covering
        most of it. One regulation is one road, so they do not get it."""
        c = line_ll.centroid
        proj = LocalProjection(c.x, c.y)

        def to_m(geom):
            return shapely.transform(geom, lambda a: np.column_stack(proj(a[:, 0], a[:, 1])))

        line_m = to_m(line_ll)
        if line_m.length == 0:
            return []
        margin = (MATCH_BUFFER_M + 5) / 111_000 * 2
        parts: dict[tuple[str, str], list] = {}
        for k in self.way_tree.query(line_ll, predicate="dwithin", distance=margin):
            part = line_m.intersection(to_m(self.way_lines[k]).buffer(MATCH_BUFFER_M))
            if part.length > 0:
                parts.setdefault(road_id(self.ways[k]), []).append(part)
        if len(parts) < 2:
            return []
        covered = {rid: shapely.union_all(p) for rid, p in parts.items()}
        primary = max(covered, key=lambda rid: covered[rid].length)
        main = covered[primary].buffer(1.0)
        return [rid for rid, g in covered.items()
                if rid != primary and shared_length(g, main) > 0.5 * g.length]

    def closer_road(self, way: Way, piece: LineString, line_m: LineString, search, to_m) -> bool:
        """True when another road follows this stretch of the JARTIC line
        clearly more closely than `piece` does (all in metres)."""
        near = line_m.intersection(piece.buffer(MATCH_BUFFER_M))
        if near.is_empty or near.length == 0:
            return False
        samples = [near.interpolate(f, normalized=True) for f in (0.1, 0.3, 0.5, 0.7, 0.9)]
        own = sum(piece.distance(p) for p in samples) / len(samples)
        identity = road_id(way)
        for k in self.way_tree.query(search):
            other = self.ways[k]
            if other.osm_id == way.osm_id or road_id(other) == identity:
                continue  # the same road, e.g. its other carriageway
            geom = to_m(self.way_lines[k])
            d = sum(geom.distance(p) for p in samples) / len(samples)
            if d < own - COMPETITOR_MARGIN_M and d < own * COMPETITOR_RATIO:
                return True
        return False

    def evidence(self, way: Way, piece: LineString, piece_ll: LineString, proj: LocalProjection) -> dict:
        def to_m(geom):
            return shapely.transform(geom, lambda c: np.column_stack(proj(c[:, 0], c[:, 1])))

        margin = (MATCH_BUFFER_M + 5) / 111_000 * 2  # degrees, generous at Japanese latitudes
        search = box(*piece_ll.bounds).buffer(margin)
        regulations, center, road_types = {}, set(), set()
        for j in self.line_tree.query(search):
            r = self.regulations[self.line_owner[j]]
            line_m = to_m(self.lines[j])
            if piece.intersection(line_m.buffer(MATCH_BUFFER_M)).length / piece.length < MATCH_COVERAGE:
                continue
            if (j, road_id(way)) in self.foreign or self.closer_road(way, piece, line_m, search, to_m):
                continue
            if r.code in SPEED_CODES:
                regulations[r.key or id(r)] = r
            elif r.code != "17" or r.side in NO_OVERTAKING_SIDES:
                center.add(CENTER_CODES[r.code])
            if r.road_type:
                road_types.add(r.road_type)
        mid_ll = piece_ll.interpolate(0.5, normalized=True)
        for j in self.area_tree.query(mid_ll):
            r = self.regulations[self.area_owner[j]]
            if r.code in SPEED_CODES and self.areas[j].contains(mid_ll):
                regulations[r.key or id(r)] = r

        tags = way.tags
        oneway = tags.get("oneway") in ONEWAY
        if tags.get("lane_markings") == "yes":
            center.add("osm_lane_markings")
        lanes = tags.get("lanes", "")
        if lanes.isdigit() and int(lanes) >= 2 and not oneway:
            center.add("osm_lanes")

        separated = False
        if oneway and way.highway in MAJOR_HIGHWAYS:
            mid = piece.interpolate(0.5, normalized=True)
            own = bearing(piece)
            for j in self.oneway_tree.query(Point(mid_ll).buffer(margin * 3)):
                other_way = self.oneway_major[j]
                if other_way.osm_id == way.osm_id:
                    continue
                other = to_m(self.oneway_lines[j])
                if other.distance(mid) <= DUAL_CARRIAGEWAY_M:
                    nearest = other.project(mid)
                    a = other.interpolate(max(0.0, nearest - 10))
                    b = other.interpolate(min(other.length, nearest + 10))
                    local = LineString([a, b]) if a.distance(b) > 0 else other
                    if angle_between(own, bearing(local)) >= 135:
                        separated = True
                        break

        return {
            "road_type": "expressway" if "expressway" in road_types else
                         "motor_road" if "motor_road" in road_types else "unknown",
            "motorroad": tags.get("motorroad") == "yes",
            "separated": separated,
            "no_lane_markings": tags.get("lane_markings") == "no",
            "regulations": [{"speed": r.speed, "code": int(r.code), "key": r.key, "conditions": r.conditions}
                            for r in regulations.values()],
            "center": sorted(center),
        }


def segments(ways: list[Way], matcher: Matcher, area: shapely.Geometry | None = None) -> Iterator[dict]:
    """Segments of the ways; with `area` (lon/lat, prepared), only those whose midpoint it contains."""
    by_tile: dict[tuple[int, int], list[Way]] = {}
    for w in ways:
        by_tile.setdefault(tile_of(*w.coords[len(w.coords) // 2]), []).append(w)
    for (tx, ty), tile_ways in sorted(by_tile.items()):
        n = 2**TILE_ZOOM
        lon0 = (tx + 0.5) / n * 360 - 180
        lat0 = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (ty + 0.5) / n))))
        proj = LocalProjection(lon0, lat0)
        for w in tile_ways:
            line = LineString([proj(*c) for c in w.coords])
            if line.length == 0:
                continue
            cuts = matcher.cuts(LineString(w.coords), line, proj)
            for seq, piece in enumerate(split(line, cuts=cuts)):
                piece_ll = LineString([proj.inverse(x, y) for x, y in piece.coords])
                if area is not None:
                    mid = piece_ll.interpolate(0.5, normalized=True)
                    if not shapely.contains_xy(area, mid.x, mid.y):
                        continue
                yield {
                    "osm_id": w.osm_id,
                    "seq": seq,
                    "highway": w.highway,
                    "name": w.tags.get("name", ""),
                    "ref": w.tags.get("ref", ""),
                    "oneway": w.tags.get("oneway", ""),
                    "maxspeed": w.tags.get("maxspeed", ""),
                    "length_m": round(piece.length, 1),
                    "coords": [[round(lon, 7), round(lat, 7)] for lon, lat in piece_ll.coords],
                    **matcher.evidence(w, piece, piece_ll, proj),
                }


def clip_to(ways: list[Way], area: shapely.Geometry) -> list[Way]:
    """Ways that come near the area (lon/lat); the margin keeps the opposite
    carriageway of a divided road on the border."""
    near = area.simplify(0.001).buffer(0.01)
    shapely.prepare(near)
    keep = shapely.intersects(near, [LineString(w.coords) for w in ways])
    return [w for w, k in zip(ways, keep) if k]


def write_segments(ways: list[Way], jartic_csv: Path, out_path: Path, area: shapely.Geometry | None = None) -> int:
    """Evidence NDJSON for the ways (only segments inside `area` when given); returns the count."""
    if area is not None:
        shapely.prepare(area)
        ways = clip_to(ways, area)
    print(f"{len(ways):,} OSM ways", file=sys.stderr)
    regulations = read_jartic(jartic_csv)
    print(f"{len(regulations):,} JARTIC regulations", file=sys.stderr)
    matcher = Matcher(regulations, ways)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with out_path.open("w", encoding="utf-8") as out:
        for record in segments(ways, matcher, area):
            out.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
            count += 1
            if count % 100_000 == 0:
                print(f"{count:,} segments", file=sys.stderr)
    print(f"{count:,} segments -> {out_path}", file=sys.stderr)
    return count


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--pbf", type=Path, required=True, help="OSM extract covering the prefecture")
    parser.add_argument("--jartic", type=Path, required=True, help="prefecture JARTIC CSV")
    parser.add_argument("--bbox", help="west,south,east,north: only roads in this box (for tests)")
    parser.add_argument("--boundary", type=Path, help="prefecture boundaries GeoJSON (scripts/boundaries.py)")
    parser.add_argument("--iso", help="prefecture to keep from --boundary, e.g. JP-04")
    parser.add_argument("--out", type=Path, required=True, help="NDJSON output")
    args = parser.parse_args(argv)
    if args.boundary and not args.iso:
        parser.error("--boundary needs --iso")

    ways = read_osm(args.pbf)
    if args.bbox:
        west, south, east, north = (float(v) for v in args.bbox.split(","))
        ways = [w for w in ways if any(west <= lon <= east and south <= lat <= north for lon, lat in w.coords)]
    area = boundary.read(args.boundary, args.iso) if args.boundary else None
    write_segments(ways, args.jartic, args.out, area)


if __name__ == "__main__":
    main()
