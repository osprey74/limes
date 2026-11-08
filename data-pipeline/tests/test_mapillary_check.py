from limes_pipeline.mapillary_check import OtherRoads, ReviewWay, pick_images, render_page, review_ways, sample_ways, summarize
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
    assert [(w.group, w.osm_id) for w in ways] == [("A", 1), ("C", 2), ("B", 3)]
    assert 200 < ways[0].length_m < 240


def test_sample_ways_caps_each_group_and_keeps_population():
    ways = [ReviewWay("C", i, "residential", "", "3m-5.5m未満", 100.0, LINE) for i in range(10)]
    ways.append(ReviewWay("A", 99, "residential", "", "5.5m-13m未満", 50.0, LINE))
    sampled, population = sample_ways(ways, 4, seed=1)
    assert sum(w.group == "C" for w in sampled) == 4
    assert sum(w.group == "A" for w in sampled) == 1
    assert population["C"] == {"ways": 10, "length_m": 1000.0}
    assert population["B"] == {"ways": 0, "length_m": 0}


def test_render_page_skips_judged_ways():
    ways = [ReviewWay("A", 1, "residential", "", "5.5m-13m未満", 100, LINE),
            ReviewWay("C", 2, "residential", "", "3m未満", 100, LINE)]
    page = render_page(ways, "札幌", {"1": "center"})
    assert 'data-id="2"' in page and 'data-id="1"' not in page
    assert 'data-area="札幌"' in page
    assert "map_action=map&amp;center=43.091000,141.350000&amp;zoom=20&amp;basemap=satellite" in page
    assert "map_action=pano&amp;viewpoint=43.091000,141.350000&amp;heading=0" in page


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
    assert picked == ["along"]  # cross-looking and far images are dropped


def test_pick_images_drops_images_taken_on_a_neighbouring_road():
    way = ReviewWay("C", 1, "residential", "", "3m未満", 220, LINE)
    # A motorway 12 m east of the way, running parallel.
    osm = {"elements": [
        {"type": "way", "id": 1, "geometry": [{"lon": c[0], "lat": c[1]} for c in LINE]},
        {"type": "way", "id": 2, "geometry": [{"lon": 141.35015, "lat": 43.0900}, {"lon": 141.35015, "lat": 43.0920}]},
    ]}
    others = OtherRoads(osm, PROJ)
    candidates = [
        image("on_motorway", 141.35014, 43.0910, 0),
        image("on_way", 141.35001, 43.0912, 0),
    ]
    assert [p["id"] for p in pick_images(way, candidates, PROJ, others)] == ["on_way"]


def test_summarize_weights_by_length():
    ways = [
        {"group": "A", "osm_id": 1, "length_m": 300, "images": [{}]},
        {"group": "A", "osm_id": 2, "length_m": 100, "images": [{}]},
        {"group": "A", "osm_id": 3, "length_m": 50, "images": []},
    ]
    population = {"A": {"ways": 3, "length_m": 450}, "C": {"ways": 10, "length_m": 900}}
    report = summarize(ways, population, {"1": "center", "2": "none", "3": "center"}, "札幌")
    assert "| A 30（low）・地理院幅員 5.5 m 以上 | 3 本 / 0.5 km | 3 本 |" in report
    assert "| C 30（low）・地理院幅員 5.5 m 未満 | 10 本 / 0.9 km | 0 本（無作為抽出） |" in report
    assert "| A | 路面画像 | 1 本 / 0.3 km | 1 本 / 0.1 km | — | — | 75% |" in report
    assert "| A | 衛星写真 | 1 本 / 0.1 km | — | — | — | 100% |" in report
    assert "| A | 計 | 2 本 / 0.3 km | 1 本 / 0.1 km | — | — | 78% |" in report
