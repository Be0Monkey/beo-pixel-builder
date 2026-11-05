"""Miniatures persistantes : agrandissement entier (pixels nets), réduction douce."""

from pathlib import Path

from PIL import Image

THUMB_BOX = 96


def make_thumbnail(src: Path, dst: Path, box: int = THUMB_BOX) -> None:
    with Image.open(src) as im:
        im = im.convert("RGBA")
        w, h = im.size
        if w <= 0 or h <= 0:
            raise ValueError("image vide")
        if w > box or h > box:
            scale = min(box / w, box / h)
            im = im.resize((max(1, round(w * scale)), max(1, round(h * scale))), Image.Resampling.BOX)
        else:
            factor = max(1, min(box // w, box // h))
            if factor > 1:
                im = im.resize((w * factor, h * factor), Image.Resampling.NEAREST)
        dst.parent.mkdir(parents=True, exist_ok=True)
        im.save(dst, "PNG")
