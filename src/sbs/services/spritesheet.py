"""Planches d'images (spritesheets) : export et découpe. Indépendant de Qt et de la bibliothèque."""

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

MAX_SHEET = 8192
FORMAT = "sbs-spritesheet"


class SheetError(Exception):
    pass


@dataclass
class FrameImage:
    image: Image.Image
    pivot: tuple[int, int]
    hold: int = 1


def cell_layout(frames: list[FrameImage]) -> tuple[int, int, int, int]:
    """(largeur de case, hauteur de case, pivot x, pivot y dans la case) : les pivots sont alignés."""
    if not frames:
        raise SheetError("aucune image à exporter")
    left = max(f.pivot[0] for f in frames)
    top = max(f.pivot[1] for f in frames)
    right = max(f.image.width - f.pivot[0] for f in frames)
    bottom = max(f.image.height - f.pivot[1] for f in frames)
    return left + right, top + bottom, left, top


def _write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def build_sheet(frames: list[FrameImage], columns: int | None = None) -> tuple[Image.Image, dict]:
    cw, ch, px, py = cell_layout(frames)
    n = len(frames)
    cols = n if columns is None else columns
    if isinstance(cols, bool) or not isinstance(cols, int) or not (1 <= cols <= n):
        raise SheetError(f"colonnes : un entier de 1 à {n}")
    rows = -(-n // cols)
    if cols * cw > MAX_SHEET or rows * ch > MAX_SHEET:
        raise SheetError(f"planche trop grande ({cols * cw}×{rows * ch}) : {MAX_SHEET} px au maximum par côté")
    sheet = Image.new("RGBA", (cols * cw, rows * ch), (0, 0, 0, 0))
    for i, f in enumerate(frames):
        x, y = (i % cols) * cw + px - f.pivot[0], (i // cols) * ch + py - f.pivot[1]
        sheet.alpha_composite(f.image.convert("RGBA"), (x, y))
    meta = {"format": FORMAT, "version": 1, "cell": [cw, ch], "columns": cols, "rows": rows,
            "pivot": [px, py], "frames": [{"index": i, "hold": f.hold} for i, f in enumerate(frames)]}
    return sheet, meta


def export_sheet(png_path: Path, frames: list[FrameImage], columns: int | None, fps: int, loop: bool,
                 name: str) -> dict:
    """Écrit la planche PNG et son fichier .json voisin (mêmes noms). Renvoie les métadonnées."""
    import io
    sheet, meta = build_sheet(frames, columns)
    meta.update({"name": name, "fps": fps, "loop": loop})
    buf = io.BytesIO()
    sheet.save(buf, format="PNG")
    png_path = Path(png_path)
    _write_atomic(png_path, buf.getvalue())
    _write_atomic(png_path.with_suffix(".json"), json.dumps(meta, indent=1, ensure_ascii=False).encode("utf-8"))
    return meta


def read_meta(png_path: Path) -> dict | None:
    """Métadonnées voisines (.json) si elles existent et sont valides ; sinon None."""
    try:
        meta = json.loads(Path(png_path).with_suffix(".json").read_text(encoding="utf-8"))
        cell = meta["cell"]
        if meta.get("format") != FORMAT or not all(isinstance(v, int) and 1 <= v <= 512 for v in cell):
            return None
        return meta
    except (OSError, ValueError, KeyError, TypeError):
        return None


def slice_sheet(png_path: Path, cell_w: int, cell_h: int, count: int | None = None) -> list[Image.Image]:
    """Découpe une planche en cases (de gauche à droite, de haut en bas).
    Sans `count`, les cases entièrement transparentes à la fin sont ignorées."""
    for name, v in (("largeur", cell_w), ("hauteur", cell_h)):
        if isinstance(v, bool) or not isinstance(v, int) or not (1 <= v <= 512):
            raise SheetError(f"{name} d'une case : un entier de 1 à 512")
    try:
        with Image.open(png_path) as im:
            if im.width > MAX_SHEET or im.height > MAX_SHEET:
                raise SheetError(f"image trop grande : {MAX_SHEET} px au maximum par côté")
            sheet = im.convert("RGBA")
    except (OSError, SyntaxError) as exc:
        raise SheetError(f"image illisible : {exc}") from exc
    cols, rows = sheet.width // cell_w, sheet.height // cell_h
    if cols < 1 or rows < 1:
        raise SheetError("la case est plus grande que l'image")
    cells = [sheet.crop((c * cell_w, r * cell_h, (c + 1) * cell_w, (r + 1) * cell_h))
             for r in range(rows) for c in range(cols)]
    if count is None:
        while len(cells) > 1 and cells[-1].getbbox() is None:
            cells.pop()
    else:
        if isinstance(count, bool) or not isinstance(count, int) or not (1 <= count <= cols * rows):
            raise SheetError(f"nombre d'images : de 1 à {cols * rows}")
        cells = cells[:count]
    if len(cells) > 256:
        raise SheetError("256 images au maximum")
    return cells
