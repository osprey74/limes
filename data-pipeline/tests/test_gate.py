import csv
import io
import json
import sqlite3

from limes_pipeline import gate, jartic
from limes_pipeline.jartic import Col

LINE = "141.35 43.09;141.351 43.091"


def make_row(key: str, code: str, coords: str = LINE, version: str = "k_2.1") -> list[str]:
    row = [""] * jartic.EXPECTED_COLUMNS
    row[Col.VERSION - 1] = version
    row[Col.UNIQUE_KEY - 1] = key
    row[Col.REGULATION_CODE - 1] = code
    row[Col.GEOMETRY_TYPE - 1] = "2"
    row[Col.COORDS - 1] = coords
    return row


def write_csv(path, rows, columns=jartic.EXPECTED_COLUMNS) -> None:
    buffer = io.StringIO()
    writer = csv.writer(buffer, quoting=csv.QUOTE_ALL, lineterminator="\r\n")
    writer.writerow([f"項目{i}" for i in range(1, columns + 1)])
    writer.writerows(rows)
    path.write_bytes(buffer.getvalue().encode("cp932"))


def write_db(path, meta: dict, stages: list[int]) -> None:
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    con.execute("CREATE TABLE segments (id INTEGER PRIMARY KEY, stage INTEGER NOT NULL)")
    con.executemany("INSERT INTO meta VALUES (?, ?)", meta.items())
    con.executemany("INSERT INTO segments (stage) VALUES (?)", [(s,) for s in stages])
    con.commit()
    con.close()


META = {"prefecture": "hokkaido", "version": "2026-09.1", "jartic_month": "2026-09"}
RELEASE = {"targetMonth": "2026年09月"}


def build(tmp_path, rows, meta=META, stages=(1, 5, 7)):
    csv_path, db_path = tmp_path / "x.csv", tmp_path / "x.sqlite"
    write_csv(csv_path, rows)
    db_path.unlink(missing_ok=True)
    write_db(db_path, meta, list(stages))
    return gate.jartic_stats(csv_path), gate.db_stats(db_path)


def failures(checks):
    return [c.name for c in checks if not c.ok]


def test_first_build_passes_without_previous(tmp_path):
    rows = [make_row(f"k{i}", "112") for i in range(30)] + [make_row("c1", "17")]
    csv_stats, db_stats = build(tmp_path, rows)
    checks = gate.evaluate("hokkaido", csv_stats, db_stats, None, RELEASE)
    assert failures(checks) == []
    assert csv_stats["codes"] == {"112": 30, "114": 0, "15": 0, "17": 1, "20": 0}
    assert db_stats["stages"] == {"1": 1, "5": 1, "7": 1}


def test_format_and_quality_failures(tmp_path):
    rows = [make_row("k1", "112", version="k_2.0"), make_row("k1", "112", coords="")]
    rows += [make_row(f"k{i}", "112") for i in range(2, 10)]
    csv_stats, db_stats = build(tmp_path, rows, meta={**META, "prefecture": "aomori"})
    got = failures(gate.evaluate("hokkaido", csv_stats, db_stats, None, {"targetMonth": "2026年10月"}))
    assert got == [
        "format version",
        "duplicate unique keys",
        "112 coordinate problems",
        "database prefecture",
        "database jartic_month",
    ]


def test_header_and_missing_speed_regulations(tmp_path):
    csv_path = tmp_path / "x.csv"
    write_csv(csv_path, [make_row("k1", "17")[:169]], columns=169)
    write_db(tmp_path / "x.sqlite", {"prefecture": "hokkaido"}, [])
    checks = gate.evaluate(
        "hokkaido", gate.jartic_stats(csv_path), gate.db_stats(tmp_path / "x.sqlite"), None
    )
    assert failures(checks) == [
        "header columns",
        "short rows",
        "speed regulations (112)",
        "database version",
        "database segments",
    ]


def test_month_over_month_change(tmp_path):
    rows = [make_row(f"k{i}", "112") for i in range(300)]
    csv_stats, db_stats = build(tmp_path, rows, stages=[1] * 300 + [7] * 700)
    previous = {"jartic": csv_stats, "db": db_stats}

    # -10% of 300 is allowed; the floor (20) does not apply above 200.
    csv_stats, db_stats = build(tmp_path, rows[:270], stages=[1] * 300 + [7] * 700)
    assert failures(gate.evaluate("hokkaido", csv_stats, db_stats, previous)) == []

    csv_stats, db_stats = build(tmp_path, rows[:269], stages=[1] * 200 + [7] * 600)
    assert failures(gate.evaluate("hokkaido", csv_stats, db_stats, previous)) == [
        "JARTIC rows",
        "code 112",
        "segments",
        "segments at stage 1 (regulated)",
    ]


def test_accept_stage1_lets_only_the_stage1_change_pass(tmp_path):
    rows = [make_row(f"k{i}", "112") for i in range(300)]
    csv_stats, db_stats = build(tmp_path, rows, stages=[1] * 300 + [7] * 700)
    previous = {"jartic": csv_stats, "db": db_stats}

    csv_stats, db_stats = build(tmp_path, rows[:269], stages=[1] * 200 + [7] * 800)
    checks = gate.evaluate("hokkaido", csv_stats, db_stats, previous, accept_stage1=True)
    assert failures(checks) == ["JARTIC rows", "code 112"]
    stage1 = next(c for c in checks if c.name == "segments at stage 1 (regulated)")
    assert "accepted" in stage1.detail


def test_small_counts_use_the_floor():
    assert gate._change("x", 25, 5).ok
    assert not gate._change("x", 26, 5).ok
    assert gate._change("x", 0, None).ok


def test_target_month():
    assert gate.target_month({"targetMonth": "2026年09月"}) == "2026-09"
    assert gate.target_month({"targetMonth": "2026年9月"}) == "2026-09"
    assert gate.target_month({}) is None


def test_main_writes_stats_and_exit_code(tmp_path):
    write_csv(tmp_path / "x.csv", [make_row("k1", "112")])
    write_db(tmp_path / "x.sqlite", META, [1])
    args = ["hokkaido", "--csv", str(tmp_path / "x.csv"), "--db", str(tmp_path / "x.sqlite")]
    stats = tmp_path / "stats.json"
    report = tmp_path / "gate.md"
    assert gate.main(args + ["--stats-out", str(stats), "--report", str(report)]) == 0
    assert json.loads(stats.read_text(encoding="utf-8"))["jartic"]["codes"]["112"] == 1
    assert "PASS" in report.read_text(encoding="utf-8")

    previous = tmp_path / "prev.json"
    data = json.loads(stats.read_text(encoding="utf-8"))
    data["db"]["segments"] = 100
    previous.write_text(json.dumps(data), encoding="utf-8")
    code = gate.main(
        args + ["--previous", str(previous), "--stats-out", str(stats), "--report", str(report)]
    )
    assert code == 1
    assert "**FAIL**" in report.read_text(encoding="utf-8")
