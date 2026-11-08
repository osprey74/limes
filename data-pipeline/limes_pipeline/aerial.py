"""GSI aerial photo crops (全国最新写真（シームレス）) for judging road markings by eye.

Tiles: https://maps.gsi.go.jp/development/ichiran.html (出典明記で利用可).
Each crop is centered on a way's midpoint and drawn twice side by side: the
plain photo, and the same photo with the OSM way traced on it, so the trace
never hides the markings being judged.
"""

from __future__ import annotations

import math
import urllib.error
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw

TILE_URL = "https://cyberjapandata.gsi.go.jp/xyz/seamlessphoto/{z}/{x}/{y}.jpg"
ZOOM = 18  # highest zoom offered; about 0.44 m/px at 43°N
TILE = 256
CROP_PX = 384  # source pixels per side, about 170 m at 43°N
SCALE = 2
TRACE = (255, 0, 200)
USER_AGENT = "limes-pipeline (+https://github.com/osprey74/limes)"
ATTRIBUTION = "航空写真：国土地理院 全国最新写真（シームレス）"


def world_px(lon: float, lat: float, z: int = ZOOM) -> tuple[float, float]:
    n = 2**z * TILE
    return (lon + 180) / 360 * n, (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n


def tile(x: int, y: int, cache_dir: Path) -> Image.Image:
    path = cache_dir / str(ZOOM) / str(x) / f"{y}.jpg"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        request = urllib.request.Request(TILE_URL.format(z=ZOOM, x=x, y=y), headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                path.write_bytes(response.read())
        except urllib.error.HTTPError as e:
            if e.code != 404:
                raise
            return Image.new("RGB", (TILE, TILE), (64, 64, 64))  # no photo for this tile
    return Image.open(path).convert("RGB")


def crop(line: list[tuple[float, float]], center: tuple[float, float], cache_dir: Path) -> Image.Image:
    """Plain photo on the left, photo with the way traced on the right."""
    cx, cy = world_px(*center)
    x0, y0 = cx - CROP_PX / 2, cy - CROP_PX / 2
    photo = Image.new("RGB", (CROP_PX, CROP_PX))
    for tx in range(int(x0 // TILE), int((x0 + CROP_PX) // TILE) + 1):
        for ty in range(int(y0 // TILE), int((y0 + CROP_PX) // TILE) + 1):
            photo.paste(tile(tx, ty, cache_dir), (round(tx * TILE - x0), round(ty * TILE - y0)))
    photo = photo.resize((CROP_PX * SCALE, CROP_PX * SCALE), Image.LANCZOS)
    traced = photo.copy()
    draw = ImageDraw.Draw(traced)
    points = [((px - x0) * SCALE, (py - y0) * SCALE) for px, py in (world_px(*c) for c in line)]
    draw.line(points, fill=TRACE, width=3)
    mx, my = (cx - x0) * SCALE, (cy - y0) * SCALE
    draw.ellipse((mx - 10, my - 10, mx + 10, my + 10), outline=TRACE, width=3)
    out = Image.new("RGB", (photo.width * 2 + 8, photo.height), (255, 255, 255))
    out.paste(photo, (0, 0))
    out.paste(traced, (photo.width + 8, 0))
    return out
