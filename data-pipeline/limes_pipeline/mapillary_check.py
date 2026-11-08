"""Phase 0: collect Mapillary street-level images for ways flagged by mesh_check.

`collect` reads mesh_check's result.geojson, picks the review ways (A: 30/low on
a GSI width class of 5.5 m or more, B: unknown, C: 30/low on a narrower class),
samples groups larger than --max-per-group, looks up nearby images through the
Mapillary Graph API and writes a local HTML page for judging by eye whether
each way has a center line. Judgments are kept in the browser and exported as
JSON; `summarize` turns that JSON into a length-weighted estimate per group,
scaled up to the whole group when it was sampled.

Needs a client token in MAPILLARY_TOKEN (read scope only). Images are CC BY-SA
and the thumbnail URLs are signed and expire, so the page stays local
(data/ is gitignored) and is only used for this check.
"""

from __future__ import annotations

import argparse
import html
import json
import math
import os
import random
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from shapely import STRtree
from shapely.geometry import LineString, Point

from . import aerial
from .mesh_check import WIDE_CLASSES, LocalProjection, angle_between, bearing

GRAPH_URL = "https://graph.mapillary.com/images"
VIEWER_URL = "https://www.mapillary.com/app/?pKey={id}"
FIELDS = "id,captured_at,compass_angle,computed_compass_angle,geometry,is_pano,thumb_1024_url"
SAMPLE_FRACTIONS = (0.2, 0.5, 0.8)
SEARCH_HALF_DEG = 0.0004  # about 30 m east-west, 45 m north-south at 43°N
MAX_DISTANCE_M = 20.0  # image position to way
ALONG_ROAD_DEG = 35.0  # camera heading within this of the road bearing (either direction)
NEAREST_MARGIN_M = 1.0  # image may be at most this much farther from the way than from any other road
IMAGES_PER_WAY = 4
VERDICTS = {"center": "中央線あり", "lanes": "車線境界線のみ（一方通行）", "none": "中央線なし", "unclear": "判別不可"}
GROUPS = {
    "A": "30（low）・地理院幅員 5.5 m 以上",
    "B": "不明",
    "C": "30（low）・地理院幅員 5.5 m 未満",
}
MAX_PER_GROUP = 60


@dataclass
class ReviewWay:
    group: str  # key of GROUPS
    osm_id: int
    highway: str
    name: str
    width: str
    length_m: float
    line: list[tuple[float, float]]
    images: list[dict] = field(default_factory=list)
    oneway: str = ""
    lanes: str = ""


def review_ways(result: dict, proj: LocalProjection) -> list[ReviewWay]:
    ways = []
    for f in result["features"]:
        p = f["properties"]
        if p["speed"] == 30 and p["confidence"] == "low" and p["width"] in WIDE_CLASSES:
            group = "A"
        elif p["speed"] is None:
            group = "B"
        elif p["speed"] == 30 and p["confidence"] == "low":
            group = "C"
        else:
            continue
        line = [tuple(c) for c in f["geometry"]["coordinates"]]
        length = LineString([proj(*c) for c in line]).length
        ways.append(ReviewWay(group, p["osm_id"], p["highway"], p["name"] or "", p["width"], length, line))
    return ways


def sample_ways(ways: list[ReviewWay], max_per_group: int, seed: int) -> tuple[list[ReviewWay], dict]:
    """Simple random sample per group; returns the sample and each group's full size."""
    rng = random.Random(seed)
    population, sampled = {}, []
    for group in GROUPS:
        members = [w for w in ways if w.group == group]
        population[group] = {"ways": len(members), "length_m": sum(w.length_m for w in members)}
        sampled += members if len(members) <= max_per_group else rng.sample(members, max_per_group)
    return sampled, population


def _get_json(url: str, token: str, retries: int = 3) -> dict:
    request = urllib.request.Request(url, headers={"Authorization": f"OAuth {token}"})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.load(response)
        except urllib.error.HTTPError as e:
            if e.code < 500 or attempt == retries - 1:
                raise
            time.sleep(2 * (attempt + 1))
    raise AssertionError("unreachable")


def fetch_images(lon: float, lat: float, token: str, cache: Path) -> list[dict]:
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    bbox = f"{lon - SEARCH_HALF_DEG},{lat - SEARCH_HALF_DEG},{lon + SEARCH_HALF_DEG},{lat + SEARCH_HALF_DEG}"
    query = urllib.parse.urlencode({"fields": FIELDS, "bbox": bbox, "limit": 100})
    try:
        data = _get_json(f"{GRAPH_URL}?{query}", token).get("data", [])
    except urllib.error.HTTPError as e:
        print(f"  {lon:.5f},{lat:.5f}: HTTP {e.code}, skipped", file=sys.stderr)
        return []
    cache.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    time.sleep(0.2)
    return data


class OtherRoads:
    """All OSM highway ways of the area (service roads included), for the nearest-road check."""

    def __init__(self, osm: dict, proj: LocalProjection):
        self.ids, lines = [], []
        for e in osm["elements"]:
            if e["type"] == "way" and len(e.get("geometry", [])) >= 2:
                self.ids.append(e["id"])
                lines.append(LineString([proj(g["lon"], g["lat"]) for g in e["geometry"]]))
        self.lines = lines
        self.tree = STRtree(lines)

    def nearest_distance(self, point: Point, exclude: int) -> float:
        best = math.inf
        for i in self.tree.query(point.buffer(MAX_DISTANCE_M + NEAREST_MARGIN_M)):
            if self.ids[i] != exclude:
                best = min(best, self.lines[i].distance(point))
        return best


def pick_images(way: ReviewWay, candidates: list[dict], proj: LocalProjection,
                others: OtherRoads | None = None) -> list[dict]:
    """Images taken on this way: no other road closer, and the camera looks along it unless 360°."""
    line_m = LineString([proj(*c) for c in way.line])
    road_bearing = bearing(line_m)
    scored = {}
    for img in candidates:
        point = Point(proj(*img["geometry"]["coordinates"]))
        distance = line_m.distance(point)
        if distance > MAX_DISTANCE_M:
            continue
        if others and distance > others.nearest_distance(point, way.osm_id) + NEAREST_MARGIN_M:
            continue  # taken on a neighbouring road
        heading = img.get("computed_compass_angle", img.get("compass_angle"))
        along = (heading is not None and
                 min(angle_between(road_bearing, heading), angle_between(road_bearing, heading + 180)) <= ALONG_ROAD_DEG)
        if not (along or img.get("is_pano")):
            continue
        position = line_m.project(point) / max(line_m.length, 1.0)
        scored[img["id"]] = (distance, position, img)
    chosen = []
    for fraction in SAMPLE_FRACTIONS:
        remaining = [s for s in scored.values() if s[2]["id"] not in {c["id"] for c in chosen}]
        if not remaining:
            break
        best = min(remaining, key=lambda s: (abs(s[1] - fraction), s[0]))
        chosen.append(best[2])
    leftovers = sorted((s for s in scored.values() if s[2]["id"] not in {c["id"] for c in chosen}),
                       key=lambda s: s[0])
    chosen += [s[2] for s in leftovers[: IMAGES_PER_WAY - len(chosen)]]
    return [{
        "id": img["id"],
        "url": img.get("thumb_1024_url"),
        "captured": date.fromtimestamp(img["captured_at"] / 1000).isoformat() if img.get("captured_at") else "",
        "pano": bool(img.get("is_pano")),
    } for img in chosen]


def collect(result_path: Path, token: str, work: Path, max_per_group: int = MAX_PER_GROUP,
            seed: int = 0) -> tuple[list[ReviewWay], dict]:
    result = json.loads(result_path.read_text(encoding="utf-8"))
    coords = [c for f in result["features"] for c in f["geometry"]["coordinates"]]
    proj = LocalProjection(sum(c[0] for c in coords) / len(coords), sum(c[1] for c in coords) / len(coords))
    cache_dir = work / "mapillary"
    cache_dir.mkdir(parents=True, exist_ok=True)
    ways, population = sample_ways(review_ways(result, proj), max_per_group, seed)
    osm = json.loads((work / "osm.json").read_text(encoding="utf-8"))
    others = OtherRoads(osm, proj)
    tags = {e["id"]: e.get("tags", {}) for e in osm["elements"]}
    aerial_dir = work / "aerial"
    aerial_dir.mkdir(exist_ok=True)
    for i, way in enumerate(ways, 1):
        way.oneway = tags.get(way.osm_id, {}).get("oneway", "")
        way.lanes = tags.get(way.osm_id, {}).get("lanes", "")
        line = LineString(way.line)
        candidates = {}
        for fraction in SAMPLE_FRACTIONS:
            pt = line.interpolate(fraction, normalized=True)
            cache = cache_dir / f"{pt.x:.5f}_{pt.y:.5f}.json"
            for img in fetch_images(pt.x, pt.y, token, cache):
                candidates[img["id"]] = img
        way.images = pick_images(way, list(candidates.values()), proj, others)
        midpoint = line.interpolate(0.5, normalized=True).coords[0]
        aerial.crop(way.line, midpoint, work.parent.parent / "gsi_photo").save(aerial_dir / f"{way.osm_id}.jpg", quality=88)
        print(f"[{i}/{len(ways)}] {way.group} way {way.osm_id}: {len(candidates)} nearby, {len(way.images)} picked")
    return ways, population


# --- review page --------------------------------------------------------------

PAGE_STYLE = """
:root { color-scheme: light dark; --bg:#fff; --fg:#1a1a1a; --muted:#666; --line:#ddd; --accent:#2563eb; }
@media (prefers-color-scheme: dark) { :root { --bg:#111317; --fg:#e8e8e8; --muted:#9aa0a6; --line:#2a2e35; --accent:#7aa7ff; } }
body { margin:0; padding:16px; background:var(--bg); color:var(--fg); font-family:"Noto Sans JP",system-ui,sans-serif; }
header { position:sticky; top:0; background:var(--bg); padding:8px 0; border-bottom:1px solid var(--line); z-index:1; }
section { border-bottom:1px solid var(--line); padding:16px 0; }
h2 { font-size:16px; margin:0 0 4px; }
.meta { color:var(--muted); font-size:13px; margin-bottom:8px; }
.imgs { display:flex; gap:8px; overflow-x:auto; }
.imgs figure { margin:0; flex:0 0 auto; }
.imgs img { height:240px; border-radius:4px; display:block; }
.aerial { width:100%; max-width:1544px; display:block; margin-bottom:8px; }
figcaption { font-size:12px; color:var(--muted); }
.verdict label { margin-right:16px; cursor:pointer; }
button { padding:6px 14px; }
a { color:var(--accent); }
.none { color:var(--muted); }
"""

PAGE_SCRIPT = """
const KEY = "limes-mapillary-review:" + document.body.dataset.area;
let saved = {};
try { saved = JSON.parse(localStorage.getItem(KEY) || "{}"); } catch (e) {}
function refresh() {
  const done = document.querySelectorAll("section[data-id]").length;
  const answered = Object.keys(saved).length;
  document.getElementById("progress").textContent = `${answered} / ${done} 判定済み`;
}
document.querySelectorAll("section[data-id]").forEach(sec => {
  const id = sec.dataset.id;
  sec.querySelectorAll("input").forEach(input => {
    if (saved[id] === input.value) input.checked = true;
    input.addEventListener("change", () => {
      saved[id] = input.value;
      try { localStorage.setItem(KEY, JSON.stringify(saved)); } catch (e) {}
      refresh();
    });
  });
});
document.getElementById("export").addEventListener("click", () => {
  const blob = new Blob([JSON.stringify(saved, null, 2)], {type: "application/json"});
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "judgments.json";
  a.click();
});
refresh();
"""


def render_page(ways: list[ReviewWay], area: str, judged: dict[str, str] | None = None) -> str:
    """Ways already in `judged` are left off the page."""
    e = html.escape
    ways = [w for w in ways if str(w.osm_id) not in (judged or {})]
    sections = []
    for way in sorted(ways, key=lambda w: (w.group, -w.length_m)):
        lon, lat = LineString(way.line).interpolate(0.5, normalized=True).coords[0]
        osm = f"https://www.openstreetmap.org/way/{way.osm_id}"
        # Google Maps URLs (https://developers.google.com/maps/documentation/urls/get-started)
        satellite = f"https://www.google.com/maps/@?api=1&map_action=map&center={lat:.6f},{lon:.6f}&zoom=20&basemap=satellite"
        heading = bearing(LineString(LocalProjection(lon, lat)(*c) for c in way.line))
        street = f"https://www.google.com/maps/@?api=1&map_action=pano&viewpoint={lat:.6f},{lon:.6f}&heading={heading:.0f}"
        photo = f'<img class="aerial" src="aerial/{way.osm_id}.jpg" loading="lazy" alt="航空写真 way {way.osm_id}">'
        if way.images:
            figures = "".join(
                f'<figure><a href="{e(VIEWER_URL.format(id=img["id"]))}" target="_blank" rel="noopener">'
                f'<img src="{e(img["url"] or "")}" loading="lazy" alt="Mapillary {e(img["id"])}"></a>'
                f'<figcaption>{e(img["captured"])}{" ・360°" if img["pano"] else ""}</figcaption></figure>'
                for img in way.images)
            body = f'{photo}<div class="imgs">{figures}</div>'
        else:
            body = f'{photo}<p class="none">近くに路面画像がありません。</p>'
        radios = "".join(
            f'<label><input type="radio" name="v{way.osm_id}" value="{key}"> {label}</label>'
            for key, label in VERDICTS.items())
        sections.append(
            f'<section data-id="{way.osm_id}"><h2>要確認 {way.group}（{e(GROUPS[way.group])}）：{e(way.name or "（名称なし）")}</h2>'
            f'<div class="meta">{e(way.highway)}{"・一方通行" if way.oneway in ("yes", "-1") else ""}'
            f'{f"・車線数 {e(way.lanes)}" if way.lanes else ""}・地理院幅員 {e(way.width)}・{way.length_m:.0f} m・'
            f'<a href="{osm}" target="_blank" rel="noopener">OSM way {way.osm_id}</a>・'
            f'<a href="{e(satellite)}" target="_blank" rel="noopener">Google マップ（航空写真）</a>・'
            f'<a href="{e(street)}" target="_blank" rel="noopener">ストリートビュー</a></div>'
            f'{body}<div class="verdict">{radios}</div></section>')
    return (
        '<!doctype html><html lang="ja"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>Limes 路面画像確認</title><style>{PAGE_STYLE}</style></head><body data-area="{e(area)}">'
        f'<header><strong>Limes 要確認道路の路面画像確認（{e(area)}）</strong>　<span id="progress"></span>　'
        '<button id="export">判定を書き出す（judgments.json）</button></header>'
        f'{"".join(sections)}'
        '<p class="meta">左：航空写真、右：同じ写真に OSM の道路を描き込んだもの（丸は中間地点）。'
        f'{aerial.ATTRIBUTION}（https://maps.gsi.go.jp/development/ichiran.html）。'
        '画像：Mapillary（CC BY-SA 4.0、撮影者に帰属）。地図データ：© OpenStreetMap contributors。</p>'
        f'<script>{PAGE_SCRIPT}</script></body></html>')


# --- summary ------------------------------------------------------------------

def _cell(members: list[dict]) -> str:
    return f"{len(members)} 本 / {sum(w['length_m'] for w in members) / 1000:.1f} km" if members else "—"


def summarize(ways: list[dict], population: dict, judgments: dict[str, str], area: str) -> str:
    """Every way has a GSI aerial crop; some also have Mapillary street-level images."""
    keys = [*VERDICTS, "pending"]
    labels = {**VERDICTS, "pending": "未判定"}
    out = [f"# Phase 0 要確認道路の路面画像確認（{area}）", "",
           "| 区分 | 対象（全体） | 確認した本数 |", "| --- | --- | ---: |"]
    for group, label in GROUPS.items():
        pop = population.get(group, {"ways": 0, "length_m": 0.0})
        checked = sum(1 for w in ways if w["group"] == group)
        note = "（無作為抽出）" if checked < pop["ways"] else ""
        out.append(f"| {group} {label} | {pop['ways']} 本 / {pop['length_m'] / 1000:.1f} km | {checked} 本{note} |")
    out += ["", "| 区分 | 判定材料 | " + " | ".join(labels[k] for k in keys) + " | 中央線ありの割合（延長） |",
            "| --- | --- | " + " | ".join("---:" for _ in keys) + " | ---: |"]
    for group in GROUPS:
        members = [w for w in ways if w["group"] == group]
        if not members:
            continue
        for source, subset in (("路面画像あり", [w for w in members if w["images"]]),
                               ("航空写真のみ", [w for w in members if not w["images"]]),
                               ("計", members)):
            buckets = {k: [w for w in subset if judgments.get(str(w["osm_id"]), "pending") == k] for k in keys}
            judged = sum(w["length_m"] for k in ("center", "lanes", "none") for w in buckets[k])
            share = f"{sum(w['length_m'] for w in buckets['center']) / judged:.0%}" if judged else "—"
            out.append(f"| {group} | {source} | " + " | ".join(_cell(buckets[k]) for k in keys) + f" | {share} |")
    out += ["", "割合は判定できた（中央線あり／車線境界線のみ／なし）延長に対する値。抽出した区分は、この割合を区分全体の延長に当てはめて推定する。"]
    out += ["", f"{aerial.ATTRIBUTION}（<https://maps.gsi.go.jp/development/ichiran.html>）。"
            "画像：Mapillary（CC BY-SA 4.0）。地図データ：© OpenStreetMap contributors（ODbL）。", ""]
    return "\n".join(out)


def _load_judgments(paths: list[Path]) -> dict[str, str]:
    merged = {}
    for path in paths:
        merged.update(json.loads(path.read_text(encoding="utf-8")))
    return merged


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    c = sub.add_parser("collect", help="find images and write the review page")
    c.add_argument("--work", type=Path, required=True, help="mesh_check area directory (has result.geojson)")
    c.add_argument("--area", required=True, help="area name shown on the page and the report")
    c.add_argument("--max-per-group", type=int, default=MAX_PER_GROUP)
    c.add_argument("--seed", type=int, default=0)
    c.add_argument("--judged", type=Path, nargs="*", default=[], help="earlier judgments.json; those ways are not shown again")
    s = sub.add_parser("summarize", help="turn exported judgments into a report")
    s.add_argument("--work", type=Path, required=True)
    s.add_argument("--judgments", type=Path, nargs="+", required=True, help="one or more exported judgments.json")
    s.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)

    ways_path = args.work / "mapillary_ways.json"
    if args.command == "collect":
        token = os.environ.get("MAPILLARY_TOKEN")
        if not token:
            parser.error("set MAPILLARY_TOKEN to a Mapillary client token")
        judged = _load_judgments(args.judged)
        ways, population = collect(args.work / "result.geojson", token, args.work, args.max_per_group, args.seed)
        ways_path.write_text(json.dumps({"area": args.area, "population": population, "ways": [w.__dict__ for w in ways]},
                                        ensure_ascii=False), encoding="utf-8")
        page = args.work / "mapillary_review.html"
        page.write_text(render_page(ways, args.area, judged), encoding="utf-8")
        print(f"{sum(1 for w in ways if w.images)} / {len(ways)} ways have images; open {page}")
    else:
        data = json.loads(ways_path.read_text(encoding="utf-8"))
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(summarize(data["ways"], data["population"], _load_judgments(args.judgments), data["area"]),
                               encoding="utf-8")
        print(f"wrote {args.report}")


if __name__ == "__main__":
    main()
