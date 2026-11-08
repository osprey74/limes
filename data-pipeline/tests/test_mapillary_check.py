from limes_pipeline.mapillary_check import ReviewWay, pick_images, review_ways, summarize
from limes_pipeline.mesh_check import LocalProjection

PROJ = LocalProjection(141.35, 43.09)
LINE = [(141.3500, 43.0900), (141.3500, 43.0920)]  # about 220 m due north


def feature(osm_id, speed, confidence, width):
    return {"geometry": {"type": "LineString", "coordinates": LINE},
            "properties": {"osm_id": osm_id, "highway": "residential", "name": None, "width": width,
                           "speed": speed, "confidence": confidence}}


def test_review_ways_selects_groups():
    result = {"features": [
        feature(1, 30, "low", "5.5m-13m未満"),
        feature(2, 30, "low", "3m-5.5m未満"),
        feature(3, None, None, "(該当なし)"),
        feature(4, 60, "high", "5.5m-13m未満"),
    ]}
    ways = review_ways(result, PROJ)
    assert [(w.group, w.osm_id) for w in ways] == [("A", 1), ("B", 3)]
    assert 200 < ways[0].length_m < 240


def image(id_, lon, lat, heading, pano=False):
    return {"id": id_, "geometry": {"coordinates": [lon, lat]}, "compass_angle": heading,
            "is_pano": pano, "captured_at": 1_700_000_000_000, "thumb_1024_url": f"https://x/{id_}"}


def test_pick_images_prefers_along_road_and_drops_far_ones():
    way = ReviewWay("A", 1, "residential", "", "5.5m-13m未満", 220, LINE)
    candidates = [
        image("side", 141.35001, 43.0910, 90),      # looking across the road
        image("along", 141.35001, 43.0911, 182),    # looking down the road (southbound)
        image("far", 141.3510, 43.0910, 0),         # about 80 m off the road
    ]
    picked = [p["id"] for p in pick_images(way, candidates, PROJ)]
    assert picked[0] == "along"
    assert "far" not in picked


def test_summarize_weights_by_length():
    ways = [
        {"group": "A", "osm_id": 1, "length_m": 300, "images": [{}]},
        {"group": "A", "osm_id": 2, "length_m": 100, "images": [{}]},
        {"group": "A", "osm_id": 3, "length_m": 50, "images": []},
    ]
    report = summarize(ways, {"1": "center", "2": "none", "3": "center"})
    assert "| A | 路面画像 | 1 本 / 0.3 km | 1 本 / 0.1 km | — | — | 75% |" in report
    assert "| A | 衛星写真 | 1 本 / 0.1 km | — | — | — | 100% |" in report
    assert "| A | 計 | 2 本 / 0.3 km | 1 本 / 0.1 km | — | — | 78% |" in report
