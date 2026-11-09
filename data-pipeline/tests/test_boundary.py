import osmium
from osmium.osm.mutable import Node, Relation, Way

from limes_pipeline import boundary


def write_pbf(path, relations):
    """A square (nodes 1-4, way 10) and a boundary relation per (id, tags)."""
    writer = osmium.SimpleWriter(str(path))
    for i, (lon, lat) in enumerate([(140, 38), (141, 38), (141, 39), (140, 39)], start=1):
        writer.add_node(Node(id=i, location=(lon, lat)))
    writer.add_way(Way(id=10, nodes=[1, 2, 3, 4, 1]))
    for rid, tags in relations:
        writer.add_relation(Relation(id=rid, members=[("w", 10, "outer")],
                                     tags={"type": "boundary", "boundary": "administrative", **tags}))
    writer.close()


def test_extract_prefecture_boundaries(tmp_path):
    pbf = tmp_path / "region.osm.pbf"
    write_pbf(pbf, [
        (100, {"admin_level": "4", "ISO3166-2": "JP-04"}),
        (101, {"admin_level": "7", "ISO3166-2": "JP-04-100"}),  # a city
        (102, {"admin_level": "4"}),  # no code
    ])
    found = boundary.extract(pbf)
    assert list(found) == ["JP-04"]
    assert found["JP-04"].bounds == (140.0, 38.0, 141.0, 39.0)
