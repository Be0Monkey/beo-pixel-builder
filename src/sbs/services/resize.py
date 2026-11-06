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


def warp_wall_piece(src: Image.Image, width: int, s_left: float, s_right: float, drop: int):
    """Déforme un module en « tranche de mur » en perspective, voisin le plus proche (pixels nets, aucune couleur
    inventée). Chaque colonne a sa hauteur (de s_left à s_right fois la hauteur d'origine) et son bas décalé
    (de 0 à `drop`). Renvoie (image RGBA, pivot) ; le pivot est le coin bas-gauche, sur la ligne du sol."""
    import numpy as np
    src = src.convert("RGBA")
    w0, h0 = src.size
    if width < 1 or width > MAX_SIDE:
        raise ValueError("largeur de pièce invalide")
    t = (np.arange(width) + 0.5) / width
    s = s_left + (s_right - s_left) * t
    height = h0 * s  # hauteur de chaque colonne
    bottom = drop * t  # bas de chaque colonne, par rapport au coin bas-gauche (y vers le bas)
    top_c = bottom - height
    top = int(np.floor(top_c.min()))
    bot = int(np.ceil(max(bottom.max(), 0.0)))
    out_h = max(1, bot - top)
    if out_h > MAX_SIDE:
        raise ValueError(f"mur trop haut ({out_h} px ; maximum {MAX_SIDE})")
    rows = top + np.arange(out_h) + 0.5
    v = (rows[:, None] - top_c[None, :]) / height[None, :]
    mask = (v >= 0) & (v < 1)
    ys = np.clip(np.floor(v * h0).astype(int), 0, h0 - 1)
    xs = np.clip((np.arange(width) * w0 // width), 0, w0 - 1)
    arr = np.asarray(src)
    out = arr[ys, xs[None, :]].copy()
    out[~mask] = 0
    return Image.fromarray(out, "RGBA"), (0, -top)


def create_wall_piece(library: Library, asset_uuid: str, width: int, s_left: float, s_right: float,
                      drop: int, label_text: str = ""):
    """Nouveau module « tranche de mur » (voir warp_wall_piece). Réutilise un module identique. (module, créé?)"""
    import hashlib

    from sbs.services.batch_import import find_local_by_sha
    asset = library.get(asset_uuid)
    if asset is None:
        raise ValueError("ce module est absent de la bibliothèque")
    try:
        src = Image.open(io.BytesIO(library.image_bytes(asset_uuid)))
        src.load()
    except (OSError, LibraryError, ValueError) as exc:
        raise ValueError(f"image du module illisible : {exc}") from exc
    img, pivot = warp_wall_piece(src, width, s_left, s_right, drop)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    png = buf.getvalue()
    existing = find_local_by_sha(library, hashlib.sha256(png).hexdigest())
    if existing is not None:
        found = library.get(existing)
        if found is not None and (found.pivot_x, found.pivot_y) == pivot:
            return found, False
    try:
        new = library.create_asset(f"{asset.name} perspective {label_text}".strip(), png, pivot, asset.category)
        if asset.tags:
            library.set_tags(new.uuid, asset.tags)
        return library.get(new.uuid), True
    except (LibraryError, ValueError) as exc:
        raise ValueError(str(exc)) from exc
