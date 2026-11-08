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
ALL_DAY_END = {"", "2400"}
# Vehicle code category A: 1 = 車両 (all vehicles), 10 = 自動車 (all motor vehicles).
# Either alone does not narrow the regulation for a car driver.
ALL_VEHICLES_A = {"1", "10"}

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
    """True when a period, weekday or time window other than 0:00-24:00 is set."""
    for period_start, period_end, time_start, time_end, weekday, *_ in _blocks(row):
        if period_start or period_end or weekday:
            return True
        if time_start not in ALL_DAY_START or time_end not in ALL_DAY_END:
            return True
    return False


def has_vehicle_condition(row: list[str]) -> bool:
    """True when the regulation targets specific vehicles rather than all vehicles."""
    for *_, a, b, c, d in _blocks(row):
        if not (a or b or c or d):
            continue
        if a in ALL_VEHICLES_A and not (b or c or d):
            continue
        return True
    return False
