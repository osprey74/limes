import json
from datetime import datetime, timezone

import osmium
import pytest

from limes_pipeline import release

ENTRY = {
    "type": "typeD",
    "targetMonth": "2026年09月",
    "releaseDay": "2026年11月01日",
    "targetList": [
        {"link": "/202611010000/typeD_hokkaido.zip"},
        {"link": "/202611010000/typeD_aomori.zip"},
    ],
}


def test_release_id():
    assert release.release_id(ENTRY) == "202611010000"
    with pytest.raises(LookupError):
        release.release_id({"targetList": []})


def test_plan_builds_what_is_not_from_this_release():
    state = {"prefectures": {"hokkaido": {"release": "202611010000"}, "aomori": {"release": "202610010000"}}}
    assert release.plan(ENTRY, state, ["hokkaido", "aomori"]) == ["aomori"]
    assert release.plan(ENTRY, {}, ["hokkaido", "aomori"]) == ["hokkaido", "aomori"]
    assert release.plan(ENTRY, state, ["hokkaido"], force=True) == ["hokkaido"]
    # Not in this release (e.g. a prefecture missing from opendata.json).
    assert release.plan(ENTRY, {}, ["tokyo"]) == []


def test_build_version():
    now = datetime(2026, 11, 9, 18, 30, tzinfo=timezone.utc)
    assert release.build_version("2026-09", now) == "2026-09.202611091830"


def test_prune_keeps_current_and_the_one_before():
    keys = [
        "hokkaido-2026-07.202609011830.sqlite.zst",
        "hokkaido-2026-08.202610011830.sqlite.zst",
        "hokkaido-2026-09.202611011830.sqlite.zst",  # in use
        "hokkaido-2026-09.202611021830.sqlite.zst",  # newer, never in the manifest
        "aomori-2026-08.202610011830.sqlite.zst",
        "aomori-2026-09.202611011830.sqlite.zst",  # in use
        "tokyo-2026-08.202610011830.sqlite.zst",  # not in the manifest
        "map/japan.pmtiles",
        "manifest.json",
    ]
    manifest = {"prefectures": {
        "hokkaido": {"path": "hokkaido-2026-09.202611011830.sqlite.zst"},
        "aomori": {"path": "aomori-2026-09.202611011830.sqlite.zst"},
    }}
    assert release.prune(keys, manifest) == ["hokkaido-2026-07.202609011830.sqlite.zst"]
    assert release.prune(keys, {}) == []


def test_prune_command_reads_the_listing(tmp_path, capsys):
    objects, manifest = tmp_path / "objects.json", tmp_path / "manifest.json"
    keys = [f"hokkaido-2026-0{m}.20261{m}011830.sqlite.zst" for m in (6, 7, 8)]
    release.write_json(objects, {"Contents": [{"Key": k} for k in keys]})
    release.write_json(manifest, {"prefectures": {"hokkaido": {"path": keys[2]}}})
    assert release.main(["prune", "--objects", str(objects), "--manifest", str(manifest)]) == 0
    assert capsys.readouterr().out.split() == [keys[0]]
    # An empty bucket lists no Contents at all, or prints nothing.
    objects.write_text("", encoding="utf-8")
    assert release.main(["prune", "--objects", str(objects), "--manifest", str(manifest)]) == 0
    assert capsys.readouterr().out == ""
    release.write_json(objects, {})
    assert release.main(["prune", "--objects", str(objects), "--manifest", str(tmp_path / "none.json")]) == 0
    assert capsys.readouterr().out == ""


def test_osm_date(tmp_path):
    pbf = tmp_path / "x.osm.pbf"
    header = osmium.io.Header()
    header.set("osmosis_replication_timestamp", "2026-11-07T21:21:36Z")
    writer = osmium.SimpleWriter(str(pbf), header=header)
    writer.add_node(osmium.osm.mutable.Node(id=1, location=(141.35, 43.09)))
    writer.close()
    assert release.osm_date(pbf) == "2026-11-07"


def test_build_keeps_going_after_a_failure(tmp_path, monkeypatch):
    published, dist, work = tmp_path / "published", tmp_path / "dist", tmp_path / "work"
    published.mkdir()
    (published / "manifest.json").write_text('{"format": 1}', encoding="utf-8")
    release.write_json(work / "plan.json", {"release": ENTRY, "prefectures": ["aomori", "hokkaido"]})
    monkeypatch.setattr(release, "read_json", _config_reader(release.read_json))
    built = []

    def fake_build_one(prefecture, region, entry, published_, dist_, work_, cli, now):
        built.append(prefecture)
        if prefecture == "aomori":
            raise RuntimeError("download failed")
        return True, "# Gate: hokkaido: PASS\n"

    monkeypatch.setattr(release, "build_one", fake_build_one)
    args = ["build", "--published", str(published), "--dist", str(dist), "--work", str(work),
            "--limes-cli", "limes-cli"]
    assert release.main(args) == 0
    assert built == ["aomori", "hokkaido"]
    assert json.loads((dist / "manifest.json").read_text(encoding="utf-8")) == {"format": 1}
    failures = (work / "failures.md").read_text(encoding="utf-8")
    assert "aomori" in failures and "download failed" in failures

    monkeypatch.setattr(release, "build_one", lambda p, *a: (True, f"# Gate: {p}: PASS\n"))
    assert release.main(args) == 0
    assert not (work / "failures.md").exists()


def _config_reader(original):
    def read_json(path, default):
        if path == release.CONFIG:
            return {"hokkaido": {"osm_region": "hokkaido"}, "aomori": {"osm_region": "tohoku"}}
        return original(path, default)

    return read_json
