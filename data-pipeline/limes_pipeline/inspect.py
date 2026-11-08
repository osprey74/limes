"""Phase 0: summarize a JARTIC regulation CSV into a Markdown report.

Counts the regulation types Limes relies on (15/20/112/113/114), how well the
road type (NO.32) and route name (NO.33) columns are filled, and basic
coordinate quality.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field as dc_field
from datetime import date
from pathlib import Path

from . import jartic
from .jartic import Col

JAPAN_BBOX = (122.0, 20.0, 154.0, 46.0)
EMPTY = "(空欄)"
SOURCE_URL = "https://www.jartic.or.jp/service/opendata/"


@dataclass
class CodeStats:
    count: int = 0
    geometry_types: Counter = dc_field(default_factory=Counter)
    update_classes: Counter = dc_field(default_factory=Counter)
    road_types: Counter = dc_field(default_factory=Counter)
    route_name_filled: int = 0
    speeds: Counter = dc_field(default_factory=Counter)
    zone30: Counter = dc_field(default_factory=Counter)
    variable_speed: Counter = dc_field(default_factory=Counter)
    lane_count_filled: int = 0
    center_line_filled: int = 0
    time_conditioned: int = 0
    vehicle_conditioned: int = 0
    undefined_weekday: int = 0
    unclear_vehicle: int = 0
    coords_empty: int = 0
    coords_invalid: int = 0
    outside_japan: int = 0
    outside_bbox: int = 0
    short_lines: int = 0
    open_polygons: int = 0
    points: int = 0


@dataclass
class Report:
    header_columns: int = 0
    rows: int = 0
    short_rows: int = 0
    versions: Counter = dc_field(default_factory=Counter)
    codes: Counter = dc_field(default_factory=Counter)
    code_names: dict[str, Counter] = dc_field(default_factory=lambda: defaultdict(Counter))
    # 片側・両側コード (NO.136) of code 17; blank means not registered as one side.
    no_overtaking_sides: Counter = dc_field(default_factory=Counter)
    mojibake_rows: int = 0
    duplicate_keys: int = 0
    targets: dict[str, CodeStats] = dc_field(
        default_factory=lambda: {code: CodeStats() for code in jartic.TARGET_CODES}
    )


def _inside(lon: float, lat: float, bbox: tuple[float, float, float, float]) -> bool:
    return bbox[0] <= lon <= bbox[2] and bbox[1] <= lat <= bbox[3]


def _check_coords(row: list[str], stats: CodeStats, bbox: tuple[float, float, float, float] | None) -> None:
    text = jartic.field(row, Col.COORDS)
    if not text:
        stats.coords_empty += 1
        return
    try:
        sections = jartic.parse_coords(text)
    except ValueError:
        stats.coords_invalid += 1
        return
    points = [p for section in sections for p in section]
    stats.points += len(points)
    if any(not _inside(lon, lat, JAPAN_BBOX) for lon, lat in points):
        stats.outside_japan += 1
    elif bbox and any(not _inside(lon, lat, bbox) for lon, lat in points):
        stats.outside_bbox += 1
    geometry = jartic.field(row, Col.GEOMETRY_TYPE)
    if geometry == "2" and any(len(s) < 2 for s in sections):
        stats.short_lines += 1
    if geometry == "3" and any(len(s) < 4 or s[0] != s[-1] for s in sections):
        stats.open_polygons += 1


def inspect(path: Path, bbox: tuple[float, float, float, float] | None = None) -> Report:
    header, rows = jartic.open_rows(path)
    report = Report(header_columns=len(header))
    seen_keys: set[str] = set()
    for row in rows:
        report.rows += 1
        if len(row) < jartic.EXPECTED_COLUMNS:
            report.short_rows += 1
        if any("�" in value for value in row):
            report.mojibake_rows += 1
        report.versions[jartic.field(row, Col.VERSION) or EMPTY] += 1
        code = jartic.field(row, Col.REGULATION_CODE) or EMPTY
        report.codes[code] += 1
        report.code_names[code][jartic.field(row, Col.REGULATION_NAME) or EMPTY] += 1
        if code == jartic.NO_OVERTAKING_CROSSING:
            report.no_overtaking_sides[jartic.field(row, Col.SIDE) or EMPTY] += 1
        key = jartic.field(row, Col.UNIQUE_KEY)
        if key:
            if key in seen_keys:
                report.duplicate_keys += 1
            seen_keys.add(key)

        stats = report.targets.get(code)
        if stats is None:
            continue
        stats.count += 1
        stats.geometry_types[jartic.field(row, Col.GEOMETRY_TYPE) or EMPTY] += 1
        stats.update_classes[jartic.field(row, Col.UPDATE_CLASS) or EMPTY] += 1
        stats.road_types[jartic.field(row, Col.ROAD_TYPE) or EMPTY] += 1
        if jartic.field(row, Col.ROUTE_NAME):
            stats.route_name_filled += 1
        if code in ("112", "113", "114"):
            stats.speeds[jartic.field(row, Col.SPEED) or EMPTY] += 1
        if code == "114":
            stats.zone30[jartic.field(row, Col.ZONE30) or EMPTY] += 1
        if code == "113":
            stats.variable_speed[jartic.field(row, Col.VARIABLE_SPEED) or EMPTY] += 1
        if jartic.field(row, Col.LANE_COUNT):
            stats.lane_count_filled += 1
        if jartic.field(row, Col.CENTER_LINE):
            stats.center_line_filled += 1
        if jartic.has_time_condition(row):
            stats.time_conditioned += 1
        if jartic.has_vehicle_condition(row):
            stats.vehicle_conditioned += 1
        if jartic.has_undefined_weekday(row):
            stats.undefined_weekday += 1
        if jartic.has_unclear_vehicle(row):
            stats.unclear_vehicle += 1
        _check_coords(row, stats, bbox)
    return report


def _pct(part: int, whole: int) -> str:
    return f"{part / whole * 100:.1f}%" if whole else "—"


def _sort_key(value: str) -> tuple[int, float, str]:
    try:
        return (0, float(value), "")
    except ValueError:
        return (1, 0.0, value)


def _counter_table(title: str, counter: Counter, total: int, labels: dict[str, str] | None = None) -> list[str]:
    lines = [f"| {title} | 件数 | 割合 |", "| --- | ---: | ---: |"]
    for value in sorted(counter, key=_sort_key):
        label = f"{value}（{labels[value]}）" if labels and value in labels else value
        lines.append(f"| {label} | {counter[value]:,} | {_pct(counter[value], total)} |")
    return lines


def render_markdown(report: Report, source_name: str, meta: dict | None = None, used_on: date | None = None) -> str:
    used_on = used_on or date.today()
    out: list[str] = [f"# JARTIC 交通規制情報 集計レポート：{source_name}", ""]
    if meta:
        out += [f"- 対象月：{meta.get('targetMonth', '—')}", f"- 公開日：{meta.get('releaseDay', '—')}"]
    out += [
        f"- ヘッダ項目数：{report.header_columns}（期待値 {jartic.EXPECTED_COLUMNS}）",
        f"- データ行数：{report.rows:,}",
        f"- 項目数不足の行：{report.short_rows:,}",
        f"- 文字化け（デコード不能バイト）を含む行：{report.mojibake_rows:,}",
        f"- ユニークキー重複：{report.duplicate_keys:,}",
        "",
        "## フォーマットバージョン",
        "",
        *_counter_table("バージョン", report.versions, report.rows),
        "",
        "## Limes が使う規制種別",
        "",
        "| コード | 種別 | 件数 | 道路種別コード充足率 | 路線名充足率 | 時間帯条件あり | 車両条件あり |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for code, name in jartic.TARGET_CODES.items():
        s = report.targets[code]
        road_filled = s.count - s.road_types.get(EMPTY, 0)
        out.append(
            f"| {code} | {name} | {s.count:,} | {_pct(road_filled, s.count)} | {_pct(s.route_name_filled, s.count)}"
            f" | {_pct(s.time_conditioned, s.count)} | {_pct(s.vehicle_conditioned, s.count)} |"
        )
    out += [
        "",
        "## 座標品質（Limes が使う規制種別）",
        "",
        "| コード | 座標なし | 解析不能 | 日本域外の点を含む | 指定範囲外の点を含む | 2点未満の線 | 閉じていない面 | 総点数 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for code in jartic.TARGET_CODES:
        s = report.targets[code]
        out.append(
            f"| {code} | {s.coords_empty:,} | {s.coords_invalid:,} | {s.outside_japan:,} | {s.outside_bbox:,}"
            f" | {s.short_lines:,} | {s.open_polygons:,} | {s.points:,} |"
        )

    for code, name in jartic.TARGET_CODES.items():
        s = report.targets[code]
        if not s.count:
            continue
        out += ["", f"## {code} {name} の内訳", ""]
        out += _counter_table("点・線・面", s.geometry_types, s.count, jartic.GEOMETRY_TYPES) + [""]
        out += _counter_table("道路種別コード", s.road_types, s.count, jartic.ROAD_TYPES) + [""]
        out += _counter_table("データ更新区分コード", s.update_classes, s.count, {"3": "廃止"})
        if s.speeds:
            out += [""] + _counter_table("速度(km/h)", s.speeds, s.count)
        if s.zone30:
            out += [""] + _counter_table("ゾーン30指定コード", s.zone30, s.count, {"1": "ゾーン30", "2": "ゾーン30プラス"})
        if s.variable_speed:
            out += [""] + _counter_table("最高速度可変区分コード", s.variable_speed, s.count)
        if code == "20":
            out += ["", f"- 車両通行帯数（NO.141）記入率：{_pct(s.lane_count_filled, s.count)}"]
        if code == "15":
            out += ["", f"- 中央線の指定（NO.144）記入率：{_pct(s.center_line_filled, s.count)}"]

    out += [
        "",
        "## 全規制種別の件数（上位30）",
        "",
        "| コード | 県別規制種別名称（最頻） | 件数 |",
        "| --- | --- | ---: |",
    ]
    for code, count in report.codes.most_common(30):
        name = report.code_names[code].most_common(1)[0][0]
        out.append(f"| {code} | {name} | {count:,} |")
    out += [
        "",
        "---",
        "",
        f"出典：「交通規制情報」（公益財団法人日本道路交通情報センター）（{SOURCE_URL}）"
        f"（{used_on.year}年{used_on.month}月{used_on.day}日に利用）を加工して作成",
        "",
    ]
    return "\n".join(out)


def _parse_bbox(text: str) -> tuple[float, float, float, float]:
    values = tuple(float(v) for v in text.split(","))
    if len(values) != 4:
        raise argparse.ArgumentTypeError("bbox must be minlon,minlat,maxlon,maxlat")
    return values  # type: ignore[return-value]


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path, help="JARTIC k_2.1 CSV (Shift-JIS)")
    parser.add_argument("--out", type=Path, help="Markdown report path (default: stdout)")
    parser.add_argument("--meta", type=Path, help="metadata JSON written by fetch_jartic")
    parser.add_argument("--bbox", type=_parse_bbox, help="expected area: minlon,minlat,maxlon,maxlat")
    args = parser.parse_args(argv)

    meta = json.loads(args.meta.read_text(encoding="utf-8")) if args.meta else None
    name = meta.get("csvName", args.csv.name) if meta else args.csv.name
    markdown = render_markdown(inspect(args.csv, args.bbox), name, meta)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(markdown, encoding="utf-8")
    else:
        print(markdown)


if __name__ == "__main__":
    main()
