from shapely.geometry import LineString, Polygon

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


def test_way_is_split_and_regulation_matched_per_piece():
    # 50 km/h along the southern half only (offset 5 m east).
    half = [(141.35006, 43.0900), (141.35006, 43.0920)]
    out = run([regulation("112", 50, lines=[half])], [Way(1, "secondary", {}, ROAD)])
    assert [s["seq"] for s in out] == [0, 1, 2]
    assert out[0]["regulations"][0]["speed"] == 50
    assert out[2]["regulations"] == []
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
