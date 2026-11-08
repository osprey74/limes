from shapely.geometry import LineString

from limes_pipeline.mesh_check import (
    Evidence,
    LocalProjection,
    analyze,
    angle_between,
    decide,
    lonlat_to_tile,
    tile_to_lonlat,
)


def test_tile_round_trip():
    x, y = lonlat_to_tile(141.35, 43.09)
    west, north = tile_to_lonlat(x, y)
    east, south = tile_to_lonlat(x + 1, y + 1)
    assert west <= 141.35 < east and south < 43.09 <= north


def test_decision_order():
    assert decide(Evidence("residential", {}, regulated_speed=40, regulated_source="JARTIC 112")).speed == 40
    assert decide(Evidence("motorway", {})).speed == 100
    assert decide(Evidence("primary", {}, dual_carriageway=True)).stage == "4 中央分離帯"
    assert decide(Evidence("residential", {}, jartic_center=True)).confidence == "high"
    d = decide(Evidence("tertiary", {"lanes": "2"}))
    assert (d.speed, d.confidence) == (60, "mid")
    # lanes=2 on a one-way road is not evidence of a center line
    assert decide(Evidence("tertiary", {"lanes": "2", "oneway": "yes"})).speed is None
    assert decide(Evidence("track", {})).confidence == "mid"
    assert decide(Evidence("residential", {"lane_markings": "no"})).confidence == "mid"
    d = decide(Evidence("residential", {}))
    assert (d.speed, d.confidence) == (30, "low")
    assert decide(Evidence("secondary", {})).speed is None


def test_angle_between_wraps():
    assert angle_between(350, 10) == 20
    assert angle_between(0, 180) == 180


def _way(osm_id, coords, **tags):
    return {"type": "way", "id": osm_id, "tags": {"highway": "residential", **tags},
            "geometry": [{"lon": lon, "lat": lat} for lon, lat in coords]}


def test_analyze_matches_jartic_and_gsi():
    proj = LocalProjection(141.35, 43.09)
    lon0, lat0 = proj.inverse(0, 0)
    lon1, lat1 = proj.inverse(200, 0)
    lon2, lat2 = proj.inverse(0, 100)
    lon3, lat3 = proj.inverse(200, 100)
    osm = {"elements": [
        _way(1, [(lon0, lat0), (lon1, lat1)]),
        _way(2, [(lon2, lat2), (lon3, lat3)]),
        _way(3, [(lon0, lat0), (lon2, lat2)], highway="service"),
    ]}
    # 112 at 40 km/h drawn 5 m off way 1
    lon_a, lat_a = proj.inverse(0, 5)
    lon_b, lat_b = proj.inverse(200, 5)
    regulations = [{"code": "112", "geometry": "2", "sections": [[(lon_a, lat_a), (lon_b, lat_b)]], "speed": "40"}]
    gsi = [{"geometry": {"type": "LineString", "coordinates": [[lon2, lat2], [lon3, lat3]]},
            "properties": {"rnkWidth": "5.5m-13m未満"}}]

    results, skipped = analyze(osm, gsi, regulations, proj)

    by_id = {w.osm_id: w for w in results}
    assert skipped == 1
    assert by_id[1].decision.speed == 40
    assert by_id[2].decision.speed == 30
    assert by_id[2].width_class == "5.5m-13m未満"
    assert abs(by_id[1].length_m - LineString([(0, 0), (200, 0)]).length) < 1
