from PIL import Image

from limes_pipeline import aerial

LINE = [(141.3500, 43.0900), (141.3500, 43.0920)]


def test_crop_places_plain_and_traced_photos_side_by_side(tmp_path):
    # Pre-fill the tile cache with plain grey tiles so no request is made.
    cx, cy = aerial.world_px(141.35, 43.091)
    half = aerial.CROP_PX / 2
    for tx in range(int((cx - half) // aerial.TILE), int((cx + half) // aerial.TILE) + 1):
        for ty in range(int((cy - half) // aerial.TILE), int((cy + half) // aerial.TILE) + 1):
            path = tmp_path / str(aerial.ZOOM) / str(tx) / f"{ty}.jpg"
            path.parent.mkdir(parents=True, exist_ok=True)
            Image.new("RGB", (aerial.TILE, aerial.TILE), (128, 128, 128)).save(path)

    out = aerial.crop(LINE, (141.35, 43.091), tmp_path)

    side = aerial.CROP_PX * aerial.SCALE
    assert out.size == (side * 2 + 8, side)
    middle = (side // 2, side // 2 + 40)  # on the way, just off the midpoint circle
    assert out.getpixel(middle)[0] < 200  # plain photo untouched
    assert out.getpixel((side + 8 + middle[0], middle[1])) == aerial.TRACE
