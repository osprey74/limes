import osmium
import shapely
from osmium.osm.mutable import Node, Relation, Way

from limes_pipeline import boundary

# Nodes 1-4: a 1° square; 5-8: a small square inside it; 9-10: east of the big one.
NODES = {1: (140, 38), 2: (141, 38), 3: (141, 39), 4: (140, 39),
         5: (140.4, 38.4), 6: (140.6, 38.4), 7: (140.6, 38.6), 8: (140.4, 38.6),
         9: (142, 38), 10: (142, 39)}


def write_pbf(path, relations, ways=None):
    """`relations`: (id, tags, [(way id, role)]); `ways`: way id -> node ids."""
    ways = ways or {10: [1, 2, 3], 11: [3, 4, 1], 12: [5, 6, 7, 8, 5]}
    writer = osmium.SimpleWriter(str(path))
    for i, location in NODES.items():
        writer.add_node(Node(id=i, location=location))
    for wid, nodes in ways.items():
        writer.add_way(Way(id=wid, nodes=nodes))
    for rid, tags, members in relations:
        writer.add_relation(Relation(id=rid, members=[("w", w, role) for w, role in members],
                                     tags={"type": "boundary", "boundary": "administrative", **tags}))
    writer.close()


def pref(iso):
    return {"admin_level": "4", "ISO3166-2": iso}


def test_extract_prefecture_boundaries(tmp_path):
    pbf = tmp_path / "region.osm.pbf"
    outer = [(10, "outer"), (11, "outer")]  # the square in two ways
    write_pbf(pbf, [
        (100, pref("JP-04"), outer),
        (101, {"admin_level": "7", "ISO3166-2": "JP-04-100"}, outer),  # a city
        (102, {"admin_level": "4"}, outer),  # no code
        (103, pref("JP-05"), outer + [(12, "inner")]),  # with an enclave
    ])
    found = boundary.extract(pbf)
    assert sorted(found) == ["JP-04", "JP-05"]
    assert found["JP-04"].bounds == (140.0, 38.0, 141.0, 39.0)
    assert round(found["JP-04"].area, 6) == 1.0
    assert round(found["JP-05"].area, 6) == 0.96


def test_boundary_with_a_missing_way_is_skipped(tmp_path):
    pbf = tmp_path / "region.osm.pbf"
    # Way 11 is not in the extract (cut off at the region's edge).
    write_pbf(pbf, [(100, pref("JP-13"), [(10, "outer"), (11, "outer")])], ways={10: [1, 2, 3]})
    assert boundary.extract(pbf) == {}


def test_open_ring_is_skipped():
    line = shapely.LineString
    assert boundary.assemble([line([(140, 38), (141, 38), (141, 39)])], []) is None
    square = boundary.assemble([line([(140, 38), (141, 38), (141, 39), (140, 39), (140, 38)])], [])
    assert round(square.area, 6) == 1.0
