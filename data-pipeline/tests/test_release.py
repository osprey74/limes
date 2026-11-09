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


def test_prune_handles_tiles_like_databases():
    keys = [f"hokkaido-2026-0{m}.20261{m}011830.{ext}" for m in (6, 7, 8) for ext in ("sqlite.zst", "pmtiles")]
    manifest = {"prefectures": {"hokkaido": {
        "path": "hokkaido-2026-08.202618011830.sqlite.zst",
        "tiles": {"path": "hokkaido-2026-08.202618011830.pmtiles"},
    }}}
    assert release.prune(keys, manifest) == [
        "hokkaido-2026-06.202616011830.pmtiles",
        "hokkaido-2026-06.202616011830.sqlite.zst",
    ]


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




CONFIG = {
    "hokkaido": {"iso": "JP-01", "osm_region": "hokkaido"},
    "aomori": {"iso": "JP-02", "osm_region": "tohoku"},
    "iwate": {"iso": "JP-03", "osm_region": "tohoku"},
}


@pytest.fixture
def config(monkeypatch):
    original = release.read_json
    monkeypatch.setattr(release, "read_json",
                        lambda path, default: CONFIG if path == release.CONFIG else original(path, default))


def test_build_groups_by_region_and_keeps_going(tmp_path, monkeypatch, config):
    published, dist, work = tmp_path / "published", tmp_path / "dist", tmp_path / "work"
    published.mkdir()
    (published / "manifest.json").write_text('{"format": 1}', encoding="utf-8")
    release.write_json(work / "plan.json", {"release": ENTRY, "prefectures": ["hokkaido", "aomori", "iwate"],
                                            "regions": ["hokkaido", "tohoku"]})
    loaded, built = [], []

    def load_region(region, work_):
        loaded.append(region)
        if region == "hokkaido":
            raise RuntimeError("download failed")
        return ("pbf", ["ways"], "boundaries")

    def build_one(prefecture, iso, region, *rest):
        built.append((prefecture, iso, region[1]))
        if prefecture == "aomori":
            return False, "# Gate: aomori: FAIL\n"
        return True, f"# Gate: {prefecture}: PASS\n"

    monkeypatch.setattr(release, "load_region", load_region)
    monkeypatch.setattr(release, "build_one", build_one)
    args = ["build", "--published", str(published), "--dist", str(dist), "--work", str(work),
            "--limes-cli", "limes-cli"]
    assert release.main(args) == 0
    assert loaded == ["hokkaido", "tohoku"]  # each region read once
    assert built == [("aomori", "JP-02", ["ways"]), ("iwate", "JP-03", ["ways"])]
    assert json.loads((dist / "manifest.json").read_text(encoding="utf-8")) == {"format": 1}
    assert release.read_json(work / "built.json", None) == {"regions": ["hokkaido", "tohoku"], "passed": ["iwate"]}
    failures = (work / "failures.md").read_text(encoding="utf-8")
    assert "hokkaido" in failures and "download failed" in failures and "aomori: FAIL" in failures

    loaded.clear()
    assert release.main(args + ["--region", "tohoku"]) == 0
    assert loaded == ["tohoku"]
    assert release.read_json(work / "built.json", None)["regions"] == ["tohoku"]


def _part(parts, region, passed, manifest, state, files=(), failures=None):
    part = parts / f"part-{region}"
    release.write_json(part / "work" / "built.json", {"regions": [region], "passed": passed})
    release.write_json(part / "dist" / "manifest.json", manifest)
    release.write_json(part / "dist" / "state.json", state)
    for name in files:
        (part / "dist" / name).parent.mkdir(parents=True, exist_ok=True)
        (part / "dist" / name).write_text(name, encoding="utf-8")
    if failures:
        (part / "work" / "failures.md").write_text(failures, encoding="utf-8")


def entry(version):
    return {"path": f"x-{version}.sqlite.zst"}


def test_merge_takes_only_what_each_job_built(tmp_path):
    published, parts, dist = tmp_path / "published", tmp_path / "parts", tmp_path / "dist"
    release.write_json(published / "manifest.json", {"format": 1, "generated_at": "old",
                                                     "prefectures": {"hokkaido": entry("h1"), "aomori": entry("a1")}})
    release.write_json(published / "state.json", {"format": 1, "prefectures": {"aomori": {"version": "a1"}}})
    # The tohoku job started from the published manifest; aomori failed, iwate passed.
    _part(parts, "tohoku", ["iwate"],
          {"format": 1, "prefectures": {"hokkaido": entry("h1"), "aomori": entry("a1"), "iwate": entry("i2")}},
          {"format": 1, "prefectures": {"aomori": {"version": "a1"}, "iwate": {"version": "i2"}}},
          files=["iwate-i2.sqlite.zst", "archive/jartic/r/typeD_aomori.zip"], failures="# Gate: aomori: FAIL\n")
    now = datetime(2026, 11, 9, 18, 30, tzinfo=timezone.utc)
    failures = release.merge(published, parts, dist, ["tohoku", "kanto"], now)

    manifest = release.read_json(dist / "manifest.json", None)
    assert manifest["generated_at"] == "2026-11-09T18:30:00Z"
    assert manifest["prefectures"] == {"hokkaido": entry("h1"), "aomori": entry("a1"), "iwate": entry("i2")}
    assert release.read_json(dist / "state.json", None)["prefectures"]["iwate"] == {"version": "i2"}
    assert (dist / "iwate-i2.sqlite.zst").exists() and (dist / "archive/jartic/r/typeD_aomori.zip").exists()
    assert "aomori: FAIL" in failures[0]
    assert "Build job failed: kanto" in failures[1]


def test_merge_first_publication(tmp_path):
    parts, dist = tmp_path / "parts", tmp_path / "dist"
    _part(parts, "tohoku", ["iwate"], {"format": 1, "prefectures": {"iwate": {"path": "i"}}},
          {"format": 1, "prefectures": {"iwate": {"version": "i"}}})
    now = datetime(2026, 11, 9, tzinfo=timezone.utc)
    assert release.merge(tmp_path / "none", parts, dist, ["tohoku"], now) == []
    assert release.read_json(dist / "manifest.json", None)["prefectures"] == {"iwate": {"path": "i"}}
