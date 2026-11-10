import pytest
import shapely
from shapely.geometry import LineString, Polygon

from limes_pipeline import boundary
from limes_pipeline.evidence import Matcher, Regulation, Way, segments, split

# A straight road running north from 141.35, 43.09 for about 450 m.
ROAD = [(141.35, 43.0900), (141.35, 43.0940)]


def regulation(code, speed=0, side="", key="k", lines=None, area=None, road_type=""):
    return Regulation(code=code, key=key, speed=speed, road_type=road_type, side=side,
                      conditions={"targets": [], "exclusions": [], "note": ""},
                      lines=[LineString(c) for c in (lines or [])], area=area)


def run(regulations, ways):
    return list(segments(ways, Matcher(regulations, ways)))


def test_split_into_equal_pieces():
    pieces = split(LineString([(0, 0), (450, 0)]))
    assert [round(p.length) for p in pieces] == [150, 150, 150]
    assert len(split(LineString([(0, 0), (200, 0)]))) == 1


def test_split_at_cut_points_first():
    pieces = split(LineString([(0, 0), (450, 0)]), cuts=[100, 105, 445])
    assert [round(p.length) for p in pieces] == [100, 175, 175]  # 105 and 445 are too close


def test_way_is_cut_where_a_regulation_ends():
    # 50 km/h on the southern 130 m only (offset 5 m east).
    part = [(141.35006, 43.0900), (141.35006, 43.0912)]
    out = run([regulation("112", 50, lines=[part])], [Way(1, "secondary", {}, ROAD)])
    assert out[0]["regulations"][0]["speed"] == 50
    assert 120 < out[0]["length_m"] < 140
    assert all(s["regulations"] == [] for s in out[1:])
    assert out[0]["coords"][0] == [141.35, 43.09]


def test_no_overtaking_counts_only_on_both_sides():
    line = [ROAD]
    both = run([regulation("17", side="3", lines=line)], [Way(1, "residential", {}, ROAD)])
    blank = run([regulation("17", side="", lines=line)], [Way(1, "residential", {}, ROAD)])
    one_side = run([regulation("17", side="2", lines=line)], [Way(1, "residential", {}, ROAD)])
    assert both[0]["center"] == ["jartic_no_overtaking"]
    assert blank[0]["center"] == ["jartic_no_overtaking"]
    assert one_side[0]["center"] == []


def test_zone_area_contains_midpoint_and_road_type_is_carried():
    zone = Polygon([(141.349, 43.089), (141.351, 43.089), (141.351, 43.095), (141.349, 43.095)])
    out = run([regulation("114", 30, area=zone)], [Way(1, "residential", {}, ROAD)])
    assert all(s["regulations"][0]["code"] == 114 for s in out)
    half_zone = Polygon([(141.349, 43.089), (141.351, 43.089), (141.351, 43.092), (141.349, 43.092)])
    out = run([regulation("114", 30, area=half_zone)], [Way(1, "residential", {}, ROAD)])
    inside = [s for s in out if s["regulations"]]
    assert 210 < sum(s["length_m"] for s in inside) < 235  # the zone edge is ~222 m north
    out = run([regulation("112", 80, lines=[ROAD], road_type="expressway")], [Way(1, "trunk", {}, ROAD)])
    assert out[0]["road_type"] == "expressway"


def test_osm_lane_evidence_and_separation():
    two_way = run([], [Way(1, "tertiary", {"lanes": "2"}, ROAD)])
    assert two_way[0]["center"] == ["osm_lanes"]
    one_way = run([], [Way(1, "tertiary", {"lanes": "2", "oneway": "yes"}, ROAD)])
    assert one_way[0]["center"] == []

    north = Way(1, "primary", {"oneway": "yes"}, ROAD)
    south = Way(2, "primary", {"oneway": "yes"}, [(141.3502, 43.0940), (141.3502, 43.0900)])  # ~16 m east
    out = run([], [north, south])
    assert all(s["separated"] for s in out)
    parallel = Way(3, "primary", {"oneway": "yes"}, [(141.3502, 43.0900), (141.3502, 43.0940)])
    assert not any(s["separated"] for s in run([], [north, parallel]))


def test_area_keeps_segments_whose_midpoint_is_inside():
    # ROAD splits into three ~150 m pieces; the area covers the southern ~200 m.
    area = Polygon([(141.34, 43.0800), (141.36, 43.0800), (141.36, 43.0918), (141.34, 43.0918)])
    shapely.prepare(area)
    ways = [Way(1, "secondary", {}, ROAD)]
    all_pieces = run([], ways)
    kept = list(segments(ways, Matcher([], ways), area))
    assert len(all_pieces) == 3
    assert [s["seq"] for s in kept] == [0]


def test_boundary_geojson_round_trip(tmp_path):
    square = Polygon([(140, 38), (141, 38), (141, 39), (140, 39)])
    boundary.write({"JP-04": square}, tmp_path / "b.geojson")
    assert boundary.read(tmp_path / "b.geojson", "JP-04").equals(square)
    with pytest.raises(LookupError, match="JP-04"):
        boundary.read(tmp_path / "b.geojson", "JP-05")


# Metres east of ROAD in degrees of longitude at 43.09°N.
def east(m):
    return m / (111_320 * 0.7302)


def shifted(m):
    return [(lon + east(m), lat) for lon, lat in ROAD]


def test_regulation_stays_on_the_road_it_follows():
    # An elevated expressway's 80 km/h line, 1 m off it; the road beneath runs
    # 10 m away, inside the match buffer.
    expressway = Way(1, "motorway", {"name": "札樽自動車道"}, ROAD)
    beneath = Way(2, "trunk", {"name": "札幌新道"}, shifted(10))
    out = run([regulation("112", 80, lines=[shifted(1)])], [expressway, beneath])
    speeds = {(s["osm_id"], tuple(r["speed"] for r in s["regulations"])) for s in out}
    assert speeds == {(1, (80,)), (2, ())}


def test_both_carriageways_of_one_road_keep_the_regulation():
    # A line drawn down the middle of a divided road: 8 m to either side.
    up = Way(1, "trunk", {"name": "札幌新道", "oneway": "yes"}, shifted(-8))
    down = Way(2, "trunk", {"name": "札幌新道", "oneway": "yes"}, shifted(8)[::-1])
    out = run([regulation("112", 60, lines=[ROAD])], [up, down])
    assert all(s["regulations"] and s["regulations"][0]["speed"] == 60 for s in out)
    assert {s["osm_id"] for s in out} == {1, 2}


def test_coarse_line_straying_over_the_road_beneath_stays_on_its_road():
    # The line follows the expressway but its middle third lies over the road
    # beneath (1 m from it), as JARTIC's coarse lines do in Sapporo.
    expressway = Way(1, "motorway", {"name": "札樽自動車道", "ref": "5"}, ROAD)
    beneath = Way(2, "trunk", {"name": "札幌新道", "ref": "5"}, shifted(10))
    line = [(141.35 + east(1), 43.0900), (141.35 + east(1), 43.0914), (141.35 + east(9), 43.0916),
            (141.35 + east(9), 43.0924), (141.35 + east(1), 43.0926), (141.35 + east(1), 43.0940)]
    out = run([regulation("112", 80, lines=[line])], [expressway, beneath])
    assert all(s["regulations"] for s in out if s["osm_id"] == 1)
    assert not any(s["regulations"] for s in out if s["osm_id"] == 2)
