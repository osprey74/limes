"""Download one prefecture's JARTIC regulation data using the site's index JSON.

The open data page is built from https://www.jartic.or.jp/d/opendata/opendata.json,
which lists the current release (target month, release day, per-prefecture ZIP links).
Old releases disappear when a new one is published.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

INDEX_URL = "https://www.jartic.or.jp/d/opendata/opendata.json"
BASE_URL = "https://www.jartic.or.jp/d/opendata"
REGULATION_TYPE = "typeD"
USER_AGENT = "limes-pipeline (+https://github.com/osprey74/limes)"
ZIP_UTF8_FLAG = 0x800


def _get(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()


def parse_index(data: bytes) -> list[dict]:
    return json.loads(data.decode("utf-8-sig"))


def regulation_entry(index: list[dict]) -> dict:
    for entry in index:
        if entry.get("type") == REGULATION_TYPE:
            return entry
    raise LookupError(f"{REGULATION_TYPE} not found in index")


def prefecture_link(entry: dict, prefecture: str) -> str:
    suffix = f"/typeD_{prefecture}.zip"
    for target in entry.get("targetList", []):
        if target.get("link", "").endswith(suffix):
            return target["link"]
    available = sorted(PurePosixPath(t["link"]).stem.removeprefix("typeD_") for t in entry.get("targetList", []))
    raise LookupError(f"prefecture {prefecture!r} not found; available: {', '.join(available)}")


def zip_member_name(info: zipfile.ZipInfo) -> str:
    """ZIP names without the UTF-8 flag are Shift-JIS; Python decodes them as cp437."""
    if info.flag_bits & ZIP_UTF8_FLAG:
        return info.filename
    return info.filename.encode("cp437").decode("cp932")


def extract_csv(zip_path: Path, out_dir: Path) -> tuple[Path, str]:
    """Extract the single CSV as <out_dir>/<zip stem>.csv; return it with its original name."""
    with zipfile.ZipFile(zip_path) as archive:
        members = [i for i in archive.infolist() if zip_member_name(i).lower().endswith(".csv")]
        if len(members) != 1:
            raise ValueError(f"expected one CSV in {zip_path.name}, found {len(members)}")
        original = PurePosixPath(zip_member_name(members[0])).name
        target = out_dir / f"{zip_path.stem}.csv"
        target.write_bytes(archive.read(members[0]))
    return target, original


def fetch(prefecture: str, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    entry = regulation_entry(parse_index(_get(INDEX_URL)))
    link = prefecture_link(entry, prefecture)
    data = _get(BASE_URL + link)
    zip_path = out_dir / PurePosixPath(link).name
    zip_path.write_bytes(data)
    csv_path, original = extract_csv(zip_path, out_dir)
    meta = {
        "prefecture": prefecture,
        "targetMonth": entry.get("targetMonth"),
        "releaseDay": entry.get("releaseDay"),
        "link": BASE_URL + link,
        "zipSha256": hashlib.sha256(data).hexdigest(),
        "csvName": original,
        "csvPath": csv_path.name,
    }
    (out_dir / f"{zip_path.stem}.meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return meta


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prefecture", help="slug used in the ZIP name, e.g. hokkaido, tokyo, gumma")
    parser.add_argument("--out-dir", type=Path, default=Path("data/raw"))
    args = parser.parse_args(argv)
    meta = fetch(args.prefecture, args.out_dir)
    print(json.dumps(meta, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
