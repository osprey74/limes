"""Readers for JARTIC traffic regulation CSV (extended standard format k_2.1).

Spec: https://www.jartic.or.jp/d/opendata/typeD_kisei_73_k_2.1.pdf
Column numbers below are the 1-based item numbers (項目NO) from the spec.
"""

from __future__ import annotations

import csv
from collections.abc import Iterator
from pathlib import Path

ENCODING = "cp932"
EXPECTED_COLUMNS = 170
EXPECTED_VERSION = "k_2.1"


class Col:
    VERSION = 1
    PREFECTURE = 2
    REGULATION_CODE = 12
    GEOMETRY_TYPE = 13
    REGULATION_NAME = 14
    UPDATE_CLASS = 20
    UNIQUE_KEY = 21
    COORDS = 24
    EXCLUDED_COORDS = 30
    ROAD_TYPE = 32
    ROUTE_NAME = 33
    SIDE = 136
    SPEED = 138
    ZONE30 = 139
    VARIABLE_SPEED = 140
    LANE_COUNT = 141
    CENTER_LINE = 144


# Condition blocks 1-5 (対象期間・時間・曜日・車両), 9 columns each from NO.41.
# Within a block: period start/end, time start/end, weekday, vehicles A-D.
CONDITION_START = 41
CONDITION_BLOCKS = 5
CONDITION_WIDTH = 9
ALL_DAY_START = {"", "0", "0000"}
# "0"-"0" appears in unused blocks (e.g. Aichi), so an end of 0 also means unset.
ALL_DAY_END = {"", "2400", "0", "0000"}
ALL_YEAR_START = {"", "101", "0101"}
ALL_YEAR_END = {"", "1231"}
# 共通コード「曜日コード」. Some prefectures use values outside this set (e.g. 9).
WEEKDAY_CODES = {"1", "2", "3", "4", "5", "6", "99"}
# Vehicle codes (共通コード「対象コード」) are bit flags written as decimal digits,
# one category per column (A-D); several targets are summed. In category A the
# lowest five digits are 車両, 自動車, 乗用, 普乗 and 普通, each of which includes an
# ordinary passenger car. Some prefectures fill unused categories with 0.
ORDINARY_CAR_A_DIGITS = 5
VEHICLE_D_OTHER = "100000000000000"  # その他: details only in 規制条件 (NO.131), often blank
NO_VEHICLE = {"", "0"}

TARGET_CODES = {
    "15": "中央線",
    "20": "車両通行帯",
    "112": "最高速度(区間)",
    "113": "最高速度可変(区間)",
    "114": "最高速度(区域)",
}
GEOMETRY_TYPES = {"1": "点", "2": "線", "3": "面"}
ROAD_TYPES = {"1": "一般道", "2": "高速自動車国道", "3": "自動車専用道路", "99": "その他"}
UPDATE_CLASS_ABOLISHED = "3"
# 追越しのための右側部分はみ出し通行禁止. Marked on both sides it doubles as the
# center line marking (警察庁「交通規制基準」第10 中央線 留意事項1).
NO_OVERTAKING_CROSSING = "17"

Coords = list[list[tuple[float, float]]]


def field(row: list[str], no: int) -> str:
    return row[no - 1].strip() if no <= len(row) else ""


def open_rows(path: Path, encoding: str = ENCODING) -> tuple[list[str], Iterator[list[str]]]:
    """Return (header, row iterator). Undecodable bytes become U+FFFD so they can be counted."""
    f = open(path, encoding=encoding, errors="replace", newline="")
    reader = csv.reader(f)
    header = next(reader)

    def rows() -> Iterator[list[str]]:
        with f:
            yield from reader

    return header, rows()


def parse_coords(text: str) -> Coords:
    """Parse "lon lat;lon lat/lon lat;..." into sections of (lon, lat) points.

    Raises ValueError on malformed points.
    """
    if not text.strip():
        return []
    sections: Coords = []
    for section in text.split("/"):
        points = []
        for point in section.split(";"):
            point = point.strip()
            if not point:
                continue
            lon, lat = point.split()
            points.append((float(lon), float(lat)))
        if points:
            sections.append(points)
    return sections


def _blocks(row: list[str]) -> Iterator[list[str]]:
    for block in range(CONDITION_BLOCKS):
        base = CONDITION_START + block * CONDITION_WIDTH
        yield [field(row, base + off) for off in range(CONDITION_WIDTH)]


def has_time_condition(row: list[str]) -> bool:
    """True when a period other than all year, a defined weekday code or a time window
    other than 0:00-24:00 is set."""
    for period_start, period_end, time_start, time_end, weekday, *_ in _blocks(row):
        if period_start not in ALL_YEAR_START or period_end not in ALL_YEAR_END:
            return True
        if weekday in WEEKDAY_CODES:
            return True
        if time_start not in ALL_DAY_START or time_end not in ALL_DAY_END:
            return True
    return False


def has_undefined_weekday(row: list[str]) -> bool:
    return any(block[4] and block[4] not in WEEKDAY_CODES for block in _blocks(row))


def covers_ordinary_car(code_a: str) -> bool:
    return code_a not in NO_VEHICLE and "1" in code_a[-ORDINARY_CAR_A_DIGITS:]


def _vehicle_blocks(row: list[str]) -> Iterator[tuple[str, str, str, str]]:
    for *_, a, b, c, d in _blocks(row):
        if any(v not in NO_VEHICLE for v in (a, b, c, d)):
            yield a, b, c, d


def has_unclear_vehicle(row: list[str]) -> bool:
    """Only category D その他 is set and 規制条件 is blank, so the target is unknown."""
    return not field(row, 131) and any(
        a in NO_VEHICLE and b in NO_VEHICLE and c in NO_VEHICLE and d == VEHICLE_D_OTHER
        for a, b, c, d in _vehicle_blocks(row)
    )


def has_vehicle_condition(row: list[str]) -> bool:
    """True when a target block leaves out ordinary passenger cars (clear cases only)."""
    if has_unclear_vehicle(row):
        return False
    return any(not covers_ordinary_car(a) for a, _, _, _ in _vehicle_blocks(row))
