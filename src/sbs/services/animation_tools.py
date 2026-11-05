"""Animations ↔ bibliothèque : images d'une animation, export en planche, import d'une planche."""

import io
from pathlib import Path

from PIL import Image

from sbs.domain.animation import Animation, Frame
from sbs.domain.ids import new_id
from sbs.services.library import Library, LibraryError
from sbs.services.spritesheet import FrameImage, SheetError, export_sheet, read_meta, slice_sheet


def frame_images(library: Library, anim: Animation) -> list[FrameImage]:
    out = []
    for f in anim.frames:
        asset = library.get(f.asset_uuid)
        if asset is None:
            raise SheetError("une image de l'animation n'est plus dans la bibliothèque")
        try:
            with Image.open(io.BytesIO(library.image_bytes(f.asset_uuid, f.variant))) as im:
                out.append(FrameImage(im.convert("RGBA"), (asset.pivot_x, asset.pivot_y), f.hold))
        except (OSError, LibraryError) as exc:
            raise SheetError(f"image illisible ({asset.name}) : {exc}") from exc
    return out


def export_animation(library: Library, anim: Animation, png_path: Path, columns: int | None = None) -> dict:
    return export_sheet(png_path, frame_images(library, anim), columns, anim.fps, anim.loop, anim.name)


def import_sheet(library: Library, png_path: Path, name: str, cell: tuple[int, int] | None = None,
                 count: int | None = None) -> Animation:
    """Découpe une planche et crée un module « local » par image (pivot bas-centre, ou celui de la
    planche exportée par cette appli). Si la planche a un .json voisin valide, il fournit case et cadence."""
    meta = read_meta(png_path)
    if cell is None:
        if meta is None:
            raise SheetError("indique la taille d'une case (pas de fichier .json voisin)")
        cell = (meta["cell"][0], meta["cell"][1])
    cells = slice_sheet(png_path, cell[0], cell[1], count if count is not None else (
        len(meta["frames"]) if meta and isinstance(meta.get("frames"), list) else None))
    pivot = (meta["pivot"][0], meta["pivot"][1]) if meta and isinstance(meta.get("pivot"), list) \
        and len(meta["pivot"]) == 2 and all(isinstance(v, int) for v in meta["pivot"]) \
        else (cell[0] // 2, cell[1] - 1)
    pivot = (min(max(pivot[0], 0), cell[0]), min(max(pivot[1], 0), cell[1]))
    name = " ".join(name.split()) or "animation"
    created: list[str] = []
    frames: list[Frame] = []
    try:
        for i, im in enumerate(cells):
            buf = io.BytesIO()
            im.save(buf, format="PNG")
            asset = library.create_asset(f"{name}_{i + 1:02d}", buf.getvalue(), pivot, "animations")
            created.append(asset.uuid)
            hold = 1
            if meta and isinstance(meta.get("frames"), list) and i < len(meta["frames"]):
                h = meta["frames"][i].get("hold") if isinstance(meta["frames"][i], dict) else 1
                hold = h if isinstance(h, int) and not isinstance(h, bool) and 1 <= h <= 100 else 1
            frames.append(Frame(asset.uuid, None, hold))
    except Exception:
        for u in created:  # rien de laissé à moitié
            library.delete_asset(u)
        raise
    fps = meta.get("fps", 8) if meta else 8
    loop = meta.get("loop", True) if meta else True
    return Animation(new_id(), name[:80], fps if isinstance(fps, int) and 1 <= fps <= 60 else 8,
                     loop if isinstance(loop, bool) else True, frames)
