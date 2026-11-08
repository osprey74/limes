"""Phase 0: apply the speed decision stages to OSM ways in a test area.

Overlays OSM ways (Overpass API), GSI road centerlines with width classes
(地理院 道路中心線 ベクトルタイル提供実験, experimental_rdcl) and JARTIC regulations,
then reports how much road length each decision stage settles and lists ways
worth checking on street-level imagery.

This is a throwaway estimate for Phase 0; the real decision logic lives in
limes-core (Rust).
"""

from __future__ import annotations

import argparse
import json
import math
import time
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import numpy as np
import shapely
from shapely import STRtree
from shapely.geometry import LineString, Polygon, mapping
from shapely.ops import unary_union

from . import jartic
from .jartic import Col

ZOOM = 16
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
GSI_RDCL_URL = "https://cyberjapandata.gsi.go.jp/xyz/experimental_rdcl/{z}/{x}/{y}.geojson"
USER_AGENT = "limes-pipeline (+https://github.com/osprey74/limes)"

CAR_HIGHWAYS = {
    "motorway", "motorway_link", "trunk", "trunk_link", "primary", "primary_link", "secondary",
    "secondary_link", "tertiary", "tertiary_link", "unclassified", "residential", "living_street", "track",
}
MAJOR_HIGHWAYS = {"trunk", "primary", "secondary", "tertiary"}
LOCAL_HIGHWAYS = {"residential", "unclassified", "living_street"}

MATCH_BUFFER_M = 12.0  # JARTIC line to OSM way
GSI_BUFFER_M = 8.0
MATCH_COVERAGE = 0.5
DUAL_CARRIAGEWAY_M = 45.0
WIDE_CLASSES = {"5.5m-13m未満", "13m-19.5m未満", "19.5m以上"}
NO_WIDTH = "(該当なし)"


# --- geometry helpers -------------------------------------------------------

def tile_to_lonlat(x: int, y: int, z: int = ZOOM) -> tuple[float, float]:
    n = 2**z
    lon = x / n * 360 - 180
    lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))
    return lon, lat


def lonlat_to_tile(lon: float, lat: float, z: int = ZOOM) -> tuple[int, int]:
    n = 2**z
    x = int((lon + 180) / 360 * n)
    y = int((1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * n)
    return x, y


class LocalProjection:
    """Equirectangular projection to meters around a reference point; fine for a few km."""

    def __init__(self, lon0: float, lat0: float):
        self.lon0, self.lat0 = lon0, lat0
        self.kx = 111_320 * math.cos(math.radians(lat0))
        self.ky = 110_540

    def __call__(self, lon, lat):
        return (lon - self.lon0) * self.kx, (lat - self.lat0) * self.ky

    def inverse(self, x, y):
        return x / self.kx + self.lon0, y / self.ky + self.lat0


def bearing(line: LineString) -> float:
    (x0, y0), (x1, y1) = line.coords[0], line.coords[-1]
    return math.degrees(math.atan2(x1 - x0, y1 - y0)) % 360


def angle_between(a: float, b: float) -> float:
    d = abs(a - b) % 360
    return min(d, 360 - d)


# --- data loading -----------------------------------------------------------

def _get(url: str, data: bytes | None = None) -> bytes:
    request = urllib.request.Request(url, data=data, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=180) as response:
        return response.read()


def fetch_osm(bbox: tuple[float, float, float, float], cache: Path) -> dict:
    if not cache.exists():
        west, south, east, north = bbox
        query = (
            f'[out:json][timeout:120];way["highway"~"^({"|".join(sorted(CAR_HIGHWAYS | {"service"}))})$"]'
            f"({south},{west},{north},{east});out tags geom;"
        )
        cache.write_bytes(_get(OVERPASS_URL, urllib.parse.urlencode({"data": query}).encode()))
    return json.loads(cache.read_text(encoding="utf-8"))


def fetch_gsi(tiles: list[tuple[int, int]], cache_dir: Path) -> list[dict]:
    features = []
    for x, y in tiles:
        cache = cache_dir / f"rdcl_{ZOOM}_{x}_{y}.geojson"
        if not cache.exists():
            try:
                cache.write_bytes(_get(GSI_RDCL_URL.format(z=ZOOM, x=x, y=y)))
            except urllib.error.HTTPError as error:
                if error.code != 404:  # 404 = no roads in the tile
                    raise
                cache.write_text('{"type":"FeatureCollection","features":[]}', encoding="utf-8")
            time.sleep(0.2)
        features += json.loads(cache.read_text(encoding="utf-8"))["features"]
    return features


def load_jartic(path: Path, bbox: tuple[float, float, float, float], codes: set[str]) -> list[dict]:
    west, south, east, north = bbox
    _, rows = jartic.open_rows(path)
    found = []
    for row in rows:
        code = jartic.field(row, Col.REGULATION_CODE)
        if code not in codes:
            continue
        try:
            sections = jartic.parse_coords(jartic.field(row, Col.COORDS))
        except ValueError:
            continue
        points = [p for s in sections for p in s]
        if not any(west <= lon <= east and south <= lat <= north for lon, lat in points):
            continue
        found.append({
            "code": code,
            "geometry": jartic.field(row, Col.GEOMETRY_TYPE),
            "sections": sections,
            "speed": jartic.field(row, Col.SPEED),
            "key": jartic.field(row, Col.UNIQUE_KEY),
        })
    return found


# --- decision ---------------------------------------------------------------

@dataclass
class Evidence:
    highway: str
    tags: dict
    regulated_speed: int | None = None  # 112 line or 114 area
    regulated_source: str = ""
    jartic_center: bool = False  # 20 or 17 line covers the way
    dual_carriageway: bool = False


@dataclass
class Decision:
    speed: int | None
    confidence: str  # high / mid / low / none
    stage: str
    reason: str


def decide(e: Evidence) -> Decision:
    tags = e.tags
    oneway = tags.get("oneway") in ("yes", "1", "-1")
    if e.regulated_speed:
        return Decision(e.regulated_speed, "high", "1 規制速度", e.regulated_source)
    if e.highway in ("motorway", "motorway_link"):
        return Decision(100, "high", "2 高速自動車国道", "OSM highway=motorway")
    if tags.get("motorroad") == "yes":
        return Decision(60, "high", "3 自動車専用道路", "OSM motorroad=yes")
    if e.dual_carriageway:
        return Decision(60, "high", "4 中央分離帯", "反対向き一方通行の対")
    if e.jartic_center:
        return Decision(60, "high", "5 中央線・通行帯", "JARTIC 20/17")
    if tags.get("lane_markings") == "yes":
        return Decision(60, "mid", "5 中央線・通行帯", "OSM lane_markings=yes")
    lanes = tags.get("lanes", "")
    if lanes.isdigit() and int(lanes) >= 2 and not oneway:
        return Decision(60, "mid", "5 中央線・通行帯", f"OSM lanes={lanes}")
    if e.highway == "track":
        return Decision(30, "mid", "6 農道・林道等", "OSM highway=track")
    if tags.get("lane_markings") == "no":
        return Decision(30, "mid", "7 生活道路", "OSM lane_markings=no")
    if e.highway in LOCAL_HIGHWAYS:
        return Decision(30, "low", "7 生活道路", f"OSM highway={e.highway}")
    return Decision(None, "none", "8 不明", f"OSM highway={e.highway} で証拠なし")


# --- analysis ---------------------------------------------------------------

@dataclass
class WayResult:
    osm_id: int
    highway: str
    name: str
    length_m: float
    width_class: str
    decision: Decision
    maxspeed: str = ""
    line_lonlat: list = field(default_factory=list)


def _coverage(line: LineString, tree: STRtree, buffers: list) -> tuple[float, int | None]:
    best, best_i = 0.0, None
    for i in tree.query(line):
        covered = line.intersection(buffers[i]).length / line.length
        if covered > best:
            best, best_i = covered, int(i)
    return best, best_i


def analyze(osm: dict, gsi: list[dict], regulations: list[dict], proj: LocalProjection) -> tuple[list[WayResult], int]:
    def to_m(geom):
        return shapely.transform(geom, lambda c: np.column_stack(proj(c[:, 0], c[:, 1])))

    speed_lines, speed_values, center_lines, areas = [], [], [], []
    for r in regulations:
        for section in r["sections"]:
            if r["geometry"] == "3" and len(section) >= 4:
                areas.append((to_m(Polygon(section)), int(r["speed"] or 0)))
            elif len(section) >= 2:
                geom = to_m(LineString(section)).buffer(MATCH_BUFFER_M)
                if r["code"] == "112":
                    speed_lines.append(geom)
                    speed_values.append(int(r["speed"] or 0))
                else:
                    center_lines.append(geom)
    speed_tree = STRtree(speed_lines)
    center_union = unary_union(center_lines) if center_lines else None

    gsi_buffers, gsi_widths = [], []
    for f in gsi:
        if f["geometry"]["type"] == "LineString" and len(f["geometry"]["coordinates"]) >= 2:
            gsi_buffers.append(to_m(LineString(f["geometry"]["coordinates"])).buffer(GSI_BUFFER_M))
            gsi_widths.append(f["properties"].get("rnkWidth") or NO_WIDTH)
    gsi_tree = STRtree(gsi_buffers)

    ways, skipped_service = [], 0
    for element in osm.get("elements", []):
        tags = element.get("tags", {})
        highway = tags.get("highway", "")
        if highway == "service":
            skipped_service += 1
            continue
        if highway not in CAR_HIGHWAYS or len(element.get("geometry", [])) < 2:
            continue
        coords = [(p["lon"], p["lat"]) for p in element["geometry"]]
        ways.append((element["id"], tags, highway, coords, to_m(LineString(coords))))

    oneway_major = [(i, w[4]) for i, w in enumerate(ways)
                    if w[2] in MAJOR_HIGHWAYS and w[1].get("oneway") in ("yes", "1")]

    results = []
    for index, (osm_id, tags, highway, coords, line) in enumerate(ways):
        if line.length == 0:
            continue
        evidence = Evidence(highway, tags)
        covered, i = _coverage(line, speed_tree, speed_lines)
        if covered >= MATCH_COVERAGE and speed_values[i]:
            evidence.regulated_speed, evidence.regulated_source = speed_values[i], "JARTIC 112"
        else:
            midpoint = line.interpolate(0.5, normalized=True)
            for polygon, speed in areas:
                if speed and polygon.contains(midpoint):
                    evidence.regulated_speed, evidence.regulated_source = speed, "JARTIC 114"
                    break
        if center_union is not None:
            evidence.jartic_center = line.intersection(center_union).length / line.length >= MATCH_COVERAGE
        if tags.get("oneway") in ("yes", "1") and highway in MAJOR_HIGHWAYS:
            mid = line.interpolate(0.5, normalized=True)
            evidence.dual_carriageway = any(
                j != index and other.distance(mid) <= DUAL_CARRIAGEWAY_M
                and angle_between(bearing(line), bearing(other)) >= 135
                for j, other in oneway_major
            )
        _, g = _coverage(line, gsi_tree, gsi_buffers)
        results.append(WayResult(
            osm_id=osm_id,
            highway=highway,
            name=tags.get("name") or tags.get("ref") or "",
            length_m=line.length,
            width_class=gsi_widths[g] if g is not None else NO_WIDTH,
            decision=decide(evidence),
            maxspeed=tags.get("maxspeed", ""),
            line_lonlat=coords,
        ))
    return results, skipped_service


# --- report -----------------------------------------------------------------

def _km(m: float) -> str:
    return f"{m / 1000:.1f}"


def _outcome(d: Decision) -> str:
    if d.speed is None:
        return "不明"
    return f"{d.speed}（{d.confidence}）"


def _way_table(ways: list[WayResult], limit: int = 15) -> list[str]:
    lines = ["| OSM way | 名称 | highway | 長さ m | 地理院幅員 | 判定 | 根拠 |", "| --- | --- | --- | ---: | --- | --- | --- |"]
    for w in sorted(ways, key=lambda w: -w.length_m)[:limit]:
        lines.append(
            f"| [{w.osm_id}](https://www.openstreetmap.org/way/{w.osm_id}) | {w.name or '—'} | {w.highway}"
            f" | {w.length_m:.0f} | {w.width_class} | {_outcome(w.decision)} | {w.decision.reason} |"
        )
    return lines


def render_markdown(results: list[WayResult], skipped_service: int, bbox, tiles, jartic_meta: dict,
                    regulations: list[dict], used_on: date | None = None) -> str:
    used_on = used_on or date.today()
    total = sum(w.length_m for w in results)
    by_stage, by_outcome = defaultdict(float), defaultdict(float)
    stage_ways = Counter()
    cross = defaultdict(lambda: defaultdict(float))
    widths = set()
    for w in results:
        by_stage[w.decision.stage] += w.length_m
        stage_ways[w.decision.stage] += 1
        by_outcome[_outcome(w.decision)] += w.length_m
        cross[_outcome(w.decision)][w.width_class] += w.length_m
        widths.add(w.width_class)
    width_order = ["3m未満", "3m-5.5m未満", "5.5m-13m未満", "13m-19.5m未満", "19.5m以上", NO_WIDTH]
    width_cols = [c for c in width_order if c in widths] + sorted(widths - set(width_order))

    reg_counts = Counter(r["code"] for r in regulations)
    out = [
        "# Phase 0 試験区域の判定試算",
        "",
        f"- 区域：経度 {bbox[0]:.5f}–{bbox[2]:.5f}、緯度 {bbox[1]:.5f}–{bbox[3]:.5f}"
        f"（ズーム{ZOOM}タイル x {tiles[0][0]}–{tiles[-1][0]}、y {tiles[0][1]}–{tiles[-1][1]}）",
        f"- OSM 道路：{len(results):,} way、{_km(total)} km（`highway=service` {skipped_service:,} way は対象外）",
        f"- JARTIC（{jartic_meta.get('targetMonth', '—')}）：区域にかかる 112 {reg_counts['112']:,} 件、114 {reg_counts['114']:,} 件、"
        f"20 {reg_counts['20']:,} 件、17 {reg_counts['17']:,} 件",
        f"- 照合条件：JARTIC 線の ±{MATCH_BUFFER_M:.0f} m に way 長の {MATCH_COVERAGE:.0%} 以上が入れば一致、"
        f"地理院中心線は ±{GSI_BUFFER_M:.0f} m で最も重なるもの",
        "",
        "## 判定段ごとの延長",
        "",
        "| 判定段 | way 数 | 延長 km | 割合 |",
        "| --- | ---: | ---: | ---: |",
    ]
    for stage in sorted(by_stage):
        out.append(f"| {stage} | {stage_ways[stage]:,} | {_km(by_stage[stage])} | {by_stage[stage] / total:.1%} |")
    out += [
        "",
        "## 判定結果 × 地理院の幅員区分（延長 km）",
        "",
        "| 判定（信頼度） | " + " | ".join(width_cols) + " | 計 |",
        "| --- | " + " | ".join("---:" for _ in width_cols) + " | ---: |",
    ]
    for outcome in sorted(by_outcome, key=lambda o: (o == "不明", o)):
        row = cross[outcome]
        out.append(f"| {outcome} | " + " | ".join(_km(row.get(c, 0)) for c in width_cols) + f" | {_km(by_outcome[outcome])} |")

    suspicious_30 = [w for w in results if w.decision.speed == 30 and w.decision.confidence == "low"
                     and w.width_class in WIDE_CLASSES]
    unknown = [w for w in results if w.decision.speed is None]
    mismatch = [w for w in results if w.decision.stage == "1 規制速度" and w.maxspeed.isdigit()
                and int(w.maxspeed) != w.decision.speed]
    out += [
        "",
        f"## 要確認 A：30（low）だが地理院幅員 5.5m 以上（{len(suspicious_30):,} way、"
        f"{_km(sum(w.length_m for w in suspicious_30))} km）",
        "",
        "中央線がある可能性があり、60 の取りこぼし候補。路面画像で中央線の有無を確認する。",
        "",
        *_way_table(suspicious_30),
        "",
        f"## 要確認 B：不明（{len(unknown):,} way、{_km(sum(w.length_m for w in unknown))} km）",
        "",
        "幹線系（trunk〜tertiary）で JARTIC にも OSM の車線情報にも証拠がない道路。",
        "",
        *_way_table(unknown),
        "",
        f"## 参考：JARTIC 規制速度と OSM `maxspeed` の不一致（{len(mismatch):,} way）",
        "",
        "マップマッチ誤りか、どちらかのデータの古さを示す。",
        "",
        *_way_table(mismatch),
        "",
        "---",
        "",
        "出典：",
        f"- 「交通規制情報」（公益財団法人日本道路交通情報センター）（<{jartic_meta.get('source', 'https://www.jartic.or.jp/service/opendata/')}>）"
        f"（{used_on.year}年{used_on.month}月{used_on.day}日に利用）を加工して作成",
        "- © OpenStreetMap contributors（ODbL）",
        "- 国土地理院 道路中心線（ベクトルタイル提供実験 experimental_rdcl）を加工して作成",
        "",
    ]
    return "\n".join(out)


def write_geojson(results: list[WayResult], path: Path) -> None:
    features = [{
        "type": "Feature",
        "geometry": mapping(LineString(w.line_lonlat)),
        "properties": {
            "osm_id": w.osm_id, "highway": w.highway, "name": w.name, "width": w.width_class,
            "speed": w.decision.speed, "confidence": w.decision.confidence,
            "stage": w.decision.stage, "reason": w.decision.reason,
        },
    } for w in results]
    path.write_text(json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False),
                    encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jartic", type=Path, required=True, help="JARTIC CSV covering the area")
    parser.add_argument("--jartic-meta", type=Path, help="metadata JSON written by fetch_jartic")
    parser.add_argument("--center", required=True, help="lon,lat of the area center")
    parser.add_argument("--tiles", type=int, default=6, help=f"area size in zoom-{ZOOM} tiles per side")
    parser.add_argument("--work-dir", type=Path, default=Path("data/mesh"))
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)

    lon, lat = (float(v) for v in args.center.split(","))
    cx, cy = lonlat_to_tile(lon, lat)
    x0, y0 = cx - args.tiles // 2, cy - args.tiles // 2
    tiles = [(x, y) for x in range(x0, x0 + args.tiles) for y in range(y0, y0 + args.tiles)]
    west, north = tile_to_lonlat(x0, y0)
    east, south = tile_to_lonlat(x0 + args.tiles, y0 + args.tiles)
    bbox = (west, south, east, north)

    work = args.work_dir / f"{ZOOM}_{x0}_{y0}_{args.tiles}"
    work.mkdir(parents=True, exist_ok=True)
    osm = fetch_osm(bbox, work / "osm.json")
    gsi = fetch_gsi(tiles, work)
    regulations = load_jartic(args.jartic, bbox, {"112", "114", "20", "17"})
    meta = json.loads(args.jartic_meta.read_text(encoding="utf-8")) if args.jartic_meta else {}

    proj = LocalProjection((west + east) / 2, (south + north) / 2)
    results, skipped = analyze(osm, gsi, regulations, proj)
    write_geojson(results, work / "result.geojson")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(render_markdown(results, skipped, bbox, tiles, meta, regulations), encoding="utf-8")
    print(f"{len(results)} ways; GeoJSON: {work / 'result.geojson'}")


if __name__ == "__main__":
    main()
