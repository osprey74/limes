"""Phase 0: fetch every prefecture's JARTIC regulation data and tabulate one row each.

Measures data size and how many prefectures carry the evidence Limes needs
(center lines, lanes, road type codes, route names). CSVs are deleted after
inspection unless --keep is given; per-prefecture results are cached as JSON
so an interrupted run resumes.
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import date
from pathlib import Path

from . import fetch, jartic
from .inspect import EMPTY, SOURCE_URL, inspect

# Regulation codes that hint at a center line or lanes, besides 15 and 20.
EXTRA_CODES = {"16": "中央線の変移", "17": "はみ出し禁止", "119": "通行帯等組合せ"}


def summarize(meta: dict, report) -> dict:
    targets = {}
    for code, stats in report.targets.items():
        targets[code] = {
            "count": stats.count,
            "roadTypeFilled": stats.count - stats.road_types.get(EMPTY, 0),
            "routeNameFilled": stats.route_name_filled,
            "timeConditioned": stats.time_conditioned,
            "vehicleConditioned": stats.vehicle_conditioned,
            "undefinedWeekday": stats.undefined_weekday,
            "unclearVehicle": stats.unclear_vehicle,
        }
    return {
        "prefecture": meta["prefecture"],
        "csvName": meta["csvName"],
        "targetMonth": meta["targetMonth"],
        "zipBytes": meta["zipBytes"],
        "csvBytes": meta["csvBytes"],
        "rows": report.rows,
        "versions": dict(report.versions),
        "mojibakeRows": report.mojibake_rows,
        "duplicateKeys": report.duplicate_keys,
        "targets": targets,
        "extra": {code: report.codes.get(code, 0) for code in EXTRA_CODES},
        "noOvertakingSides": dict(report.no_overtaking_sides),
    }


def survey_one(slug: str, out_dir: Path, entry: dict, keep: bool) -> dict:
    cache = out_dir / f"{slug}.summary.json"
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    meta = fetch.fetch(slug, out_dir, entry)
    csv_path = out_dir / meta["csvPath"]
    summary = summarize(meta, inspect(csv_path))
    cache.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    if not keep:
        csv_path.unlink()
        (out_dir / f"typeD_{slug}.zip").unlink()
    return summary


def _pct(part: int, whole: int) -> str:
    return f"{part / whole * 100:.0f}%" if whole else "—"


def _mb(n: int) -> str:
    return f"{n / 1_000_000:.1f}"


def render_markdown(summaries: list[dict], release: dict, used_on: date | None = None) -> str:
    used_on = used_on or date.today()
    total_zip = sum(s["zipBytes"] for s in summaries)
    total_csv = sum(s["csvBytes"] for s in summaries)
    total_rows = sum(s["rows"] for s in summaries)
    out = [
        "# JARTIC 交通規制情報 全国集計",
        "",
        f"- 対象月：{release.get('targetMonth', '—')}（公開日 {release.get('releaseDay', '—')}）",
        f"- 都道府県数：{len(summaries)}",
        f"- 合計：ZIP {_mb(total_zip)} MB、CSV {_mb(total_csv)} MB、{total_rows:,} 行",
        "",
        "## 中央線・車両通行帯・最高速度の件数",
        "",
        "旧フォーマットからの機械変換（バージョン「K_2.1注」）かどうかは CSV には記録されず、"
        "公開ごとの「作成基準日等データ」PDF にのみ記載される。",
        "",
        "| 都道府県 | 行数 | 15 中央線 | 20 通行帯 | 17 はみ出し禁止 | 16 中央線変移 | 119 通行帯組合せ"
        " | 112 速度(区間) | 113 可変 | 114 速度(区域) |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for s in summaries:
        t, e = s["targets"], s["extra"]
        out.append(
            f"| {s['csvName'].split('_')[0]} | {s['rows']:,} | {t['15']['count']:,}"
            f" | {t['20']['count']:,} | {e['17']:,} | {e['16']:,} | {e['119']:,} | {t['112']['count']:,}"
            f" | {t['113']['count']:,} | {t['114']['count']:,} |"
        )
    out += [
        "",
        "## 17 はみ出し禁止の片側・両側コード（NO.136）",
        "",
        "共通コード：1＝無し、2＝片側、3＝両側。片側の規制はコードの登録が必須のため、空欄は「片側ではない」と解釈できる。",
        "",
        "| 都道府県 | 件数 | 空欄 | コード別 |",
        "| --- | ---: | ---: | --- |",
    ]
    for s in summaries:
        sides = s["noOvertakingSides"]
        coded = "、".join(f"{k}: {v:,}" for k, v in sorted(sides.items()) if k != EMPTY) or "—"
        out.append(f"| {s['csvName'].split('_')[0]} | {s['extra']['17']:,} | {sides.get(EMPTY, 0):,} | {coded} |")
    out += [
        "",
        "## 最高速度(区間) 112 の属性充足率と条件",
        "",
        "時間帯条件は通年・終日・仕様外の曜日コードを除く。車両条件は普通乗用車が対象に含まれない指定"
        "（「その他」のみで規制条件が空欄のものは「車両不明確」に分けて数える）。",
        "",
        "| 都道府県 | 道路種別コード | 路線名 | 時間帯条件 | 車両条件 | 車両不明確 | 仕様外の曜日コード | ZIP MB | CSV MB | 文字化け行 | キー重複 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for s in summaries:
        t = s["targets"]["112"]
        out.append(
            f"| {s['csvName'].split('_')[0]} | {_pct(t['roadTypeFilled'], t['count'])}"
            f" | {_pct(t['routeNameFilled'], t['count'])} | {_pct(t['timeConditioned'], t['count'])}"
            f" | {_pct(t['vehicleConditioned'], t['count'])} | {_pct(t['unclearVehicle'], t['count'])}"
            f" | {_pct(t['undefinedWeekday'], t['count'])}"
            f" | {_mb(s['zipBytes'])} | {_mb(s['csvBytes'])}"
            f" | {s['mojibakeRows']:,} | {s['duplicateKeys']:,} |"
        )
    out += [
        "",
        "---",
        "",
        f"出典：「交通規制情報」（公益財団法人日本道路交通情報センター）（<{SOURCE_URL}>）"
        f"（{used_on.year}年{used_on.month}月{used_on.day}日に利用）を加工して作成",
        "",
    ]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=Path("data/survey"))
    parser.add_argument("--report", type=Path, required=True, help="Markdown output path")
    parser.add_argument("--keep", action="store_true", help="keep downloaded ZIP/CSV files")
    parser.add_argument("--delay", type=float, default=2.0, help="seconds between downloads")
    args = parser.parse_args(argv)

    entry = fetch.current_release()
    summaries = []
    for slug in fetch.prefecture_slugs(entry):
        cached = (args.out_dir / f"{slug}.summary.json").exists()
        summaries.append(survey_one(slug, args.out_dir, entry, args.keep))
        print(f"{slug}: {summaries[-1]['rows']:,} rows", flush=True)
        if not cached:
            time.sleep(args.delay)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(render_markdown(summaries, entry), encoding="utf-8")


if __name__ == "__main__":
    main()
