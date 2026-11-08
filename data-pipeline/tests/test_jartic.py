import csv
import io
import json
import zipfile
from datetime import date

import pytest

from limes_pipeline import fetch, jartic
from limes_pipeline.inspect import inspect, render_markdown
from limes_pipeline.jartic import Col


def make_row(**values: str) -> list[str]:
    row = [""] * jartic.EXPECTED_COLUMNS
    row[Col.VERSION - 1] = "k_2.1"
    for name, value in values.items():
        row[getattr(Col, name) - 1] = value
    return row


def write_csv(path, rows: list[list[str]]) -> None:
    buffer = io.StringIO()
    writer = csv.writer(buffer, quoting=csv.QUOTE_ALL, lineterminator="\r\n")
    writer.writerow([f"項目{i}" for i in range(1, jartic.EXPECTED_COLUMNS + 1)])
    writer.writerows(rows)
    path.write_bytes(buffer.getvalue().encode("cp932"))


def test_parse_coords_sections_and_points():
    assert jartic.parse_coords("141.1 43.1;141.2 43.2/141.3 43.3;141.4 43.4") == [
        [(141.1, 43.1), (141.2, 43.2)],
        [(141.3, 43.3), (141.4, 43.4)],
    ]
    assert jartic.parse_coords("") == []
    with pytest.raises(ValueError):
        jartic.parse_coords("141.1;43.1")


def test_all_day_and_all_vehicles_are_not_conditions():
    row = make_row()
    row[43 - 1], row[44 - 1] = "0", "2400"  # block 1, 0:00-24:00
    row[46 - 1] = "1"  # 車両
    row[55 - 1] = "10"  # block 2, 自動車
    assert not jartic.has_time_condition(row)
    assert not jartic.has_vehicle_condition(row)


def test_condition_detection_looks_at_every_block():
    row = make_row()
    row[52 - 1], row[53 - 1] = "700", "900"  # block 2, 7:00-9:00
    assert jartic.has_time_condition(row)
    row = make_row()
    row[81 - 1] = "1111100"  # block 5, weekday
    assert jartic.has_time_condition(row)
    row = make_row()
    row[85 - 1] = "1"  # block 5, vehicle D
    assert jartic.has_vehicle_condition(row)
    row = make_row()
    row[46 - 1], row[48 - 1] = "1", "10"  # 車両 combined with a category C code
    assert jartic.has_vehicle_condition(row)


def test_inspect_counts_targets_and_quality(tmp_path):
    rows = [
        make_row(REGULATION_CODE="112", GEOMETRY_TYPE="2", ROAD_TYPE="1", ROUTE_NAME="国道36号",
                 SPEED="50", UNIQUE_KEY="A", COORDS="141.35 43.06;141.36 43.07"),
        make_row(REGULATION_CODE="112", GEOMETRY_TYPE="2", SPEED="40", UNIQUE_KEY="B",
                 COORDS="141.35 43.06"),  # single-point line
        make_row(REGULATION_CODE="114", GEOMETRY_TYPE="3", SPEED="30", ZONE30="1", UNIQUE_KEY="C",
                 COORDS="141.1 43.1;141.2 43.1;141.2 43.2;141.1 43.1"),
        make_row(REGULATION_CODE="15", GEOMETRY_TYPE="2", UNIQUE_KEY="D", COORDS="0 0;1 1"),
        make_row(REGULATION_CODE="20", GEOMETRY_TYPE="2", UNIQUE_KEY="D", LANE_COUNT="2",
                 COORDS="141.1 43.1;141.2 43.2"),
        make_row(REGULATION_CODE="1", GEOMETRY_TYPE="2", UNIQUE_KEY="E", COORDS="bad"),
    ]
    path = tmp_path / "pref.csv"
    write_csv(path, rows)

    report = inspect(path, bbox=(139.0, 41.0, 149.0, 46.0))

    assert report.header_columns == 170
    assert report.rows == 6
    assert report.duplicate_keys == 1
    assert report.mojibake_rows == 0
    s112 = report.targets["112"]
    assert s112.count == 2
    assert s112.road_types == {"1": 1, "(空欄)": 1}
    assert s112.route_name_filled == 1
    assert s112.speeds == {"50": 1, "40": 1}
    assert s112.short_lines == 1
    assert report.targets["114"].open_polygons == 0
    assert report.targets["114"].zone30 == {"1": 1}
    assert report.targets["15"].outside_japan == 1
    assert report.targets["20"].lane_count_filled == 1

    markdown = render_markdown(report, "test.csv", {"targetMonth": "2026年09月"}, used_on=date(2026, 11, 8))
    assert "| 112 | 最高速度(区間) | 2 | 50.0% | 50.0% |" in markdown
    assert "2026年11月8日に利用" in markdown


def test_inspect_counts_undecodable_bytes(tmp_path):
    path = tmp_path / "broken.csv"
    write_csv(path, [make_row(REGULATION_CODE="112")])
    path.write_bytes(path.read_bytes() + b'"\x85\xff"\r\n')
    assert inspect(path).mojibake_rows == 1


def test_index_lookup():
    index = fetch.parse_index(json.dumps([
        {"type": "typeB", "targetList": []},
        {"type": "typeD", "targetMonth": "2026年09月", "targetList": [
            {"id": "R01", "link": "/202611010000/typeD_hokkaido.zip"},
            {"id": "R10", "link": "/202611010000/typeD_gumma.zip"},
        ]},
    ], ensure_ascii=False).encode("utf-8"))
    entry = fetch.regulation_entry(index)
    assert fetch.prefecture_link(entry, "gumma") == "/202611010000/typeD_gumma.zip"
    with pytest.raises(LookupError, match="hokkaido, gumma|gumma, hokkaido"):
        fetch.prefecture_link(entry, "gunma")


def test_extract_csv_decodes_shift_jis_member_name(tmp_path):
    # JARTIC's ZIPs store Shift-JIS names without the UTF-8 flag. zipfile always
    # writes non-ASCII names as UTF-8, so write a same-length ASCII placeholder
    # and patch the raw name bytes (local header and central directory).
    raw_name = "typeD_hokkaido/北海道警_202609_k_2.1.csv".encode("cp932")
    placeholder = b"typeD_hokkaido/" + b"X" * 8 + b"_202609_k_2.1.csv"
    assert len(placeholder) == len(raw_name)
    zip_path = tmp_path / "typeD_hokkaido.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr(placeholder.decode("ascii"), b"data")
    zip_path.write_bytes(zip_path.read_bytes().replace(placeholder, raw_name))
    csv_path, original = fetch.extract_csv(zip_path, tmp_path)
    assert original == "北海道警_202609_k_2.1.csv"
    assert csv_path == tmp_path / "typeD_hokkaido.csv"
    assert csv_path.read_bytes() == b"data"
