"""Redimensionner un module en gardant des pixels nets : facteurs ENTIERS uniquement (voisin le plus proche).

Agrandir : ×2…×8 (chaque pixel devient un bloc). Réduire : ÷2…÷4, seulement si la taille est divisible
(sinon l'image serait déformée). Le résultat est un NOUVEAU module de la bibliothèque : l'original n'est
jamais modifié. Pivot et ancrages sont recalculés ; les variantes et cartes de relief/émission ne sont pas reprises.
"""

import io

from PIL import Image

from sbs.domain.asset import Anchor
from sbs.services.library import Library, LibraryError

MAX_SIDE = 4096
FACTORS: tuple[tuple[str, int], ...] = (
    ("down", 4), ("down", 3), ("down", 2), ("up", 2), ("up", 3), ("up", 4), ("up", 6), ("up", 8),
)


def label(mode: str, k: int) -> str:
    return f"×{k}" if mode == "up" else f"÷{k}"


def _check(mode: str, k: int) -> None:
    if mode not in ("up", "down") or isinstance(k, bool) or not isinstance(k, int) or not 2 <= k <= 8:
        raise ValueError("facteur invalide : entier de 2 à 8, en agrandissant (×) ou en réduisant (÷)")


def target_size(width: int, height: int, mode: str, k: int) -> tuple[int, int]:
    _check(mode, k)
    if mode == "up":
        nw, nh = width * k, height * k
        if nw > MAX_SIDE or nh > MAX_SIDE:
            raise ValueError(f"résultat trop grand ({nw}×{nh} ; maximum {MAX_SIDE}×{MAX_SIDE})")
        return nw, nh
    if width % k or height % k:
        raise ValueError(f"réduire par {k} exige une taille divisible par {k} ({width}×{height} ne l'est pas)")
    return width // k, height // k


def map_coord(p: int, dim: int, new_dim: int, mode: str, k: int) -> int:
    """Nouvelle coordonnée d'un pivot/ancrage. Un point posé sur le dernier pixel (ex. le bas du sprite)
    reste sur le dernier pixel ; un point au bord extérieur reste au bord."""
    if mode == "up":
        if p >= dim:
            return new_dim
        if p == dim - 1:
            return new_dim - 1
        return p * k + k // 2
    return min(p // k, new_dim)


def resize_image(img: Image.Image, mode: str, k: int) -> Image.Image:
    nw, nh = target_size(img.width, img.height, mode, k)
    return img.convert("RGBA").resize((nw, nh), Image.Resampling.NEAREST)


def create_resized(library: Library, asset_uuid: str, mode: str, k: int):
    """Crée et renvoie le nouveau module. Lève ValueError (message clair) ; ne laisse rien en cas d'échec."""
    asset = library.get(asset_uuid)
    if asset is None:
        raise ValueError("ce module est absent de la bibliothèque")
    try:
        src = Image.open(io.BytesIO(library.image_bytes(asset_uuid)))
        src.load()
    except (OSError, LibraryError, ValueError) as exc:
        raise ValueError(f"image du module illisible : {exc}") from exc
    out = resize_image(src, mode, k)
    buf = io.BytesIO()
    out.save(buf, "PNG")
    pivot = (map_coord(asset.pivot_x, asset.width, out.width, mode, k),
             map_coord(asset.pivot_y, asset.height, out.height, mode, k))
    name = f"{asset.name} {label(mode, k)}"
    new = None
    try:
        new = library.create_asset(name, buf.getvalue(), pivot, asset.category)
        if asset.anchors:
            anchors = [Anchor(a.name, map_coord(a.x, asset.width, out.width, mode, k),
                              map_coord(a.y, asset.height, out.height, mode, k)) for a in asset.anchors]
            new = library.update_geometry(new.uuid, pivot, anchors, revision=1)
        if asset.tags:
            library.set_tags(new.uuid, asset.tags)
        return library.get(new.uuid)
    except (LibraryError, ValueError) as exc:
        if new is not None:
            library.delete_asset(new.uuid)
        raise ValueError(str(exc)) from exc


def create_scaled(library: Library, asset_uuid: str, factor: float):
    """Version réduite d'un module (facteur 0,1 à 1) en voisin le plus proche, pour simuler l'éloignement.
    Réutilise un module identique déjà présent. Renvoie (module, créé?). Lève ValueError."""
    from sbs.services.batch_import import find_local_by_sha
    asset = library.get(asset_uuid)
    if asset is None:
        raise ValueError("ce module est absent de la bibliothèque")
    if isinstance(factor, bool) or not isinstance(factor, (int, float)) or not 0.1 <= factor <= 1.0:
        raise ValueError("l'échelle doit être comprise entre 10 % et 100 %")
    if factor == 1.0:
        return asset, False
    try:
        src = Image.open(io.BytesIO(library.image_bytes(asset_uuid)))
        src.load()
    except (OSError, LibraryError, ValueError) as exc:
        raise ValueError(f"image du module illisible : {exc}") from exc
    nw, nh = max(1, round(asset.width * factor)), max(1, round(asset.height * factor))
    out = src.convert("RGBA").resize((nw, nh), Image.Resampling.NEAREST)
    buf = io.BytesIO()
    out.save(buf, "PNG")
    png = buf.getvalue()

    def scale_pt(p: int, dim: int, new_dim: int) -> int:
        if p >= dim:
            return new_dim
        if p == dim - 1:
            return new_dim - 1  # le bas / le bord reste le bas / le bord
        return min(new_dim - 1, round(p * factor))
    pivot = (scale_pt(asset.pivot_x, asset.width, nw), scale_pt(asset.pivot_y, asset.height, nh))
    import hashlib
    existing = find_local_by_sha(library, hashlib.sha256(png).hexdigest())
    if existing is not None:
        found = library.get(existing)
        if found is not None and (found.pivot_x, found.pivot_y) == pivot:
            return found, False
    name = f"{asset.name} {round(factor * 100)}%"
    new = None
    try:
        new = library.create_asset(name, png, pivot, asset.category)
        if asset.anchors:
            anchors = [Anchor(a.name, scale_pt(a.x, asset.width, nw), scale_pt(a.y, asset.height, nh))
                       for a in asset.anchors]
            new = library.update_geometry(new.uuid, pivot, anchors, revision=1)
        if asset.tags:
            library.set_tags(new.uuid, asset.tags)
        return library.get(new.uuid), True
    except (LibraryError, ValueError) as exc:
        if new is not None:
            library.delete_asset(new.uuid)
        raise ValueError(str(exc)) from exc
