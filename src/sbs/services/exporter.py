"""Export PNG RGBA natif, calculé avec Pillow (indépendant de Qt, donc comparable pixel à pixel).

Règles : les instances sont fournies DANS L'ORDRE DE DESSIN (SceneModel.draw_instances(), qui
exclut déjà les étages/calques masqués), transparence conservée, aucune interpolation
(agrandissement par facteur entier, voisin le plus proche), grilles et repères jamais exportés,
écriture atomique (le fichier précédent reste intact en cas d'échec).
"""

import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from sbs.domain.scene import Instance
from sbs.services.library import Library

MAX_PIXELS = 64_000_000
MAX_SCALE = 16


class ExportError(Exception):
    """Message destiné à l'utilisateur."""


@dataclass
class ExportResult:
    path: Path | None
    width: int
    height: int
    origin: tuple[int, int]  # coin haut-gauche de l'image exportée, en coordonnées de scène
    scale: int
    count: int
    skipped: list[str] = field(default_factory=list)  # modules dont l'image est absente/illisible


def render_scene(
    instances: list[Instance],
    library: Library,
    rect: tuple[int, int, int, int] | None = None,
    scale: int = 1,
) -> tuple[Image.Image, ExportResult]:
    if isinstance(scale, bool) or not isinstance(scale, int) or not 1 <= scale <= MAX_SCALE:
        raise ExportError(f"facteur d'agrandissement invalide (entier de 1 à {MAX_SCALE})")
    placed: list[tuple[Image.Image, int, int]] = []
    skipped: list[str] = []
    assets: dict[str, object] = {}  # un module est lu une seule fois, même utilisé 1000 fois
    images: dict[Path, Image.Image | None] = {}
    for inst in instances:
        if inst.asset_uuid not in assets:
            assets[inst.asset_uuid] = library.get(inst.asset_uuid)
        asset = assets[inst.asset_uuid]
        if asset is None:
            skipped.append(inst.asset_uuid)
            continue
        path = library.abs_path(asset.image_for(inst.variant))
        if path not in images:
            try:
                with Image.open(path) as im:
                    images[path] = im.convert("RGBA")
            except (OSError, UnidentifiedImageError):
                images[path] = None
        img = images[path]
        if img is None:
            skipped.append(asset.source_id)
            continue
        placed.append((img, inst.x - asset.pivot_x, inst.y - asset.pivot_y))
    if not placed:
        raise ExportError("Rien à exporter : aucune image n'est disponible.")

    if rect is None:
        rx = min(ox for _, ox, _ in placed)
        ry = min(oy for _, _, oy in placed)
        rw = max(ox + im.width for im, ox, _ in placed) - rx
        rh = max(oy + im.height for im, _, oy in placed) - ry
    else:
        rx, ry, rw, rh = rect
        if any(isinstance(v, bool) or not isinstance(v, int) for v in rect) or rw <= 0 or rh <= 0:
            raise ExportError("rectangle d'export invalide (largeur et hauteur > 0, entiers)")
    if rw * rh * scale * scale > MAX_PIXELS:
        raise ExportError("image exportée trop grande (limite : 64 millions de pixels)")

    canvas = Image.new("RGBA", (rw, rh), (0, 0, 0, 0))
    for img, ox, oy in placed:
        x0, y0 = max(ox, rx), max(oy, ry)
        x1, y1 = min(ox + img.width, rx + rw), min(oy + img.height, ry + rh)
        if x1 <= x0 or y1 <= y0:
            continue
        part = img.crop((x0 - ox, y0 - oy, x1 - ox, y1 - oy))
        canvas.alpha_composite(part, (x0 - rx, y0 - ry))
    if scale > 1:
        canvas = canvas.resize((rw * scale, rh * scale), Image.Resampling.NEAREST)
    return canvas, ExportResult(None, canvas.width, canvas.height, (rx, ry), scale,
                                len(placed), skipped)


def export_png(
    path: Path,
    instances: list[Instance],
    library: Library,
    rect: tuple[int, int, int, int] | None = None,
    scale: int = 1,
) -> ExportResult:
    path = Path(path)
    image, result = render_scene(instances, library, rect, scale)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
        os.close(fd)
        try:
            image.save(tmp, format="PNG")
            os.replace(tmp, path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
    except OSError as exc:
        raise ExportError(f"écriture impossible : {exc}. Le fichier précédent n'a pas été modifié.") from exc
    result.path = path
    return result
