"""Éclairage et ombres SIMULÉS pour l'aperçu (jamais écrits dans les sprites : non destructif).

Modèle simple : couleur finale = base × (ambiance + lumière × max(0, N·L)) + émission.
N vient de la carte de normales (`_n`), l'émission de la carte `_e` du kit. Les ombres sont des
silhouettes aplaties et inclinées posées au sol. C'est une approximation, pas le rendu de Blender.
"""

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

from sbs.domain.scene import Instance
from sbs.services.library import Library

MAX_PIXELS = 16_000_000


@dataclass
class LightSettings:
    azimuth: float = 135.0     # degrés : 0 = lumière venant de la droite, 90 = du haut de l'écran
    elevation: float = 45.0    # degrés au-dessus de l'horizon (5 à 85)
    intensity: float = 0.8
    ambient: float = 0.55
    light_color: tuple[int, int, int] = (255, 240, 210)
    ambient_color: tuple[int, int, int] = (190, 200, 255)
    emission: float = 1.0
    shadows: bool = True
    shadow_opacity: float = 0.35
    flip_green: bool = True    # cartes de normales « Y vers le haut » (Blender / OpenGL)

    def validate(self) -> None:
        for name, v, lo, hi in (("azimut", self.azimuth, 0, 360), ("élévation", self.elevation, 5, 85),
                                ("intensité", self.intensity, 0, 3), ("ambiance", self.ambient, 0, 2),
                                ("émission", self.emission, 0, 3), ("opacité des ombres", self.shadow_opacity, 0, 1)):
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not (lo <= v <= hi):
                raise ValueError(f"{name} : un nombre de {lo} à {hi}")
        for name, c in (("couleur de la lumière", self.light_color), ("couleur d'ambiance", self.ambient_color)):
            if len(c) != 3 or not all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 255 for v in c):
                raise ValueError(f"{name} : trois entiers de 0 à 255")

    def light_vector(self) -> tuple[float, float, float]:
        az, el = math.radians(self.azimuth), math.radians(self.elevation)
        return math.cos(el) * math.cos(az), -math.cos(el) * math.sin(az), math.sin(el)  # y écran vers le bas


def shade_sprite(base: Image.Image, normal: Image.Image | None, emission: Image.Image | None,
                 s: LightSettings) -> Image.Image:
    """Image éclairée (même taille, alpha de la base conservé)."""
    b = np.asarray(base.convert("RGBA"), dtype=np.float32)
    rgb, alpha = b[..., :3], b[..., 3:]
    if normal is not None and normal.size == base.size:
        n = np.asarray(normal.convert("RGB"), dtype=np.float32) / 255.0 * 2.0 - 1.0
        if s.flip_green:
            n[..., 1] = -n[..., 1]
        length = np.linalg.norm(n, axis=-1, keepdims=True)
        n = np.where(length > 1e-3, n / np.maximum(length, 1e-3), np.array([0, 0, 1], dtype=np.float32))
    else:
        n = np.zeros(b.shape[:2] + (3,), dtype=np.float32)
        n[..., 2] = 1.0
    lx, ly, lz = s.light_vector()
    diffuse = np.clip(n[..., 0] * lx + n[..., 1] * ly + n[..., 2] * lz, 0, 1)[..., None]
    light = np.array(s.light_color, dtype=np.float32) / 255.0 * s.intensity
    amb = np.array(s.ambient_color, dtype=np.float32) / 255.0 * s.ambient
    out = rgb * (amb + light * diffuse)
    if emission is not None and emission.size == base.size and s.emission > 0:
        e = np.asarray(emission.convert("RGBA"), dtype=np.float32)
        glow = e[..., :3] * (e[..., 3:] / 255.0) * s.emission
        out = out + glow * (alpha / 255.0)
    out = np.clip(out, 0, 255)
    return Image.fromarray(np.concatenate([out, alpha], axis=-1).astype(np.uint8), "RGBA")


def shadow_image(alpha: Image.Image, pivot: tuple[int, int], s: LightSettings) -> tuple[Image.Image, tuple[int, int]]:
    """Ombre au sol : la partie au-dessus du pivot, inclinée à l'opposé de la lumière et aplatie.
    Renvoie (image L, décalage de son coin haut-gauche par rapport à celui du sprite)."""
    w, h = alpha.size
    px, py = pivot
    az = math.radians(s.azimuth)
    length = min(1.5, 0.6 / math.tan(math.radians(max(s.elevation, 5))) + 0.2)
    cx, cy = -math.cos(az) * length, math.sin(az) * 0.35 * length  # vers où tombe un point de hauteur h
    cy = max(-0.6, min(0.6, cy))
    mask = alpha.convert("L").crop((0, 0, w, max(0, min(h, py + 1))))  # au-dessus du pivot seulement
    if mask.height == 0 or mask.getbbox() is None:
        return Image.new("L", (1, 1), 0), (0, 0)
    pad_x = int(math.ceil(mask.height * abs(cx))) + 2
    pad_y = int(math.ceil(mask.height * abs(cy))) + 2
    ow, oh = w + 2 * pad_x, mask.height + 2 * pad_y
    # sortie (x', y') -> entrée (x, y) ; x' = x + (py - y) * cx, y' = y + (py - y) * cy
    e = 1.0 / (1.0 - cy)
    f = -cy * py * e
    ox, oy = pad_x, pad_y
    # coordonnées de sortie relatives au sprite : X = x' - ox, Y = y' - oy
    a, b_, c = 1.0, cx * e, cx * (f - oy * e) - cx * py - ox
    d, e2, f2 = 0.0, e, f - oy * e
    out = mask.transform((ow, oh), Image.Transform.AFFINE, (a, b_, c, d, e2, f2), Image.Resampling.NEAREST)
    return out, (-ox, -oy)


@dataclass
class LitItem:
    base: Image.Image
    normal: Image.Image | None
    emission: Image.Image | None
    x: int  # coin haut-gauche dans la scène
    y: int
    pivot: tuple[int, int]


def load_items(instances: list[Instance], library: Library) -> tuple[list[LitItem], list[str]]:
    items: list[LitItem] = []
    skipped: list[str] = []
    cache: dict[tuple[str, str | None], tuple] = {}

    def opened(rel: Path | None):
        if rel is None:
            return None
        try:
            with Image.open(rel) as im:
                return im.convert("RGBA")
        except OSError:
            return None

    for inst in instances:
        key = (inst.asset_uuid, inst.variant)
        if key not in cache:
            asset = library.get(inst.asset_uuid)
            base = opened(library.abs_path(asset.image_for(inst.variant))) if asset else None
            if asset is None or base is None:
                cache[key] = None
                skipped.append(asset.source_id if asset else inst.asset_uuid)
            else:
                cache[key] = (base,
                              opened(library.abs_path(asset.normal_path)) if asset.normal_path else None,
                              opened(library.abs_path(asset.emission_path)) if asset.emission_path else None,
                              (asset.pivot_x, asset.pivot_y))
        got = cache[key]
        if got is not None:
            items.append(LitItem(got[0], got[1], got[2], inst.x - got[3][0], inst.y - got[3][1], got[3]))
    return items, skipped


def background_image(kind: str, size: tuple[int, int]) -> Image.Image:
    """Fond de l'aperçu : « transparent » ou un préréglage ; jamais enregistré dans les sprites."""
    from sbs.services.backgrounds import make_background
    return make_background(kind, size)


def render_lit(items: list[LitItem], s: LightSettings, background: str = "transparent",
               scale: int = 1, margin: int = 16) -> tuple[Image.Image, tuple[int, int]]:
    """Scène éclairée. Renvoie (image, coin haut-gauche en coordonnées de scène)."""
    s.validate()
    if isinstance(scale, bool) or not isinstance(scale, int) or not (1 <= scale <= 8):
        raise ValueError("agrandissement : un entier de 1 à 8")
    if not items:
        raise ValueError("la scène est vide")
    shadows = []
    if s.shadows and s.shadow_opacity > 0:
        for it in items:
            sh, (dx, dy) = shadow_image(it.base.getchannel("A"), it.pivot, s)
            if sh.getbbox() is not None:
                shadows.append((sh, it.x + dx, it.y + dy))
    boxes = [(it.x, it.y, it.x + it.base.width, it.y + it.base.height) for it in items]
    boxes += [(x, y, x + sh.width, y + sh.height) for sh, x, y in shadows]
    left, top = min(b[0] for b in boxes) - margin, min(b[1] for b in boxes) - margin
    right, bottom = max(b[2] for b in boxes) + margin, max(b[3] for b in boxes) + margin
    w, h = right - left, bottom - top
    if w * h * scale * scale > MAX_PIXELS:
        raise ValueError("image trop grande pour l'aperçu : réduis la scène ou l'agrandissement")
    canvas = background_image(background, (w, h)) if background != "transparent" else Image.new("RGBA", (w, h))
    black = Image.new("RGBA", (1, 1), (0, 0, 0, 255))
    for sh, x, y in shadows:
        layer = Image.new("RGBA", sh.size, (0, 0, 0, 0))
        layer.paste(black.resize(sh.size), (0, 0), sh.point(lambda v: int(v * s.shadow_opacity)))
        canvas.alpha_composite(layer, (x - left, y - top))
    for it in items:
        canvas.alpha_composite(shade_sprite(it.base, it.normal, it.emission, s), (it.x - left, it.y - top))
    if scale > 1:
        canvas = canvas.resize((w * scale, h * scale), Image.Resampling.NEAREST)
    return canvas, (left, top)


def compare_images(a: Image.Image, b: Image.Image) -> dict:
    """Écart moyen entre deux images (après mise à la même taille du plus petit) : outil de comparaison."""
    w, h = min(a.width, b.width), min(a.height, b.height)
    x = np.asarray(a.convert("RGB").crop((0, 0, w, h)), dtype=np.float32)
    y = np.asarray(b.convert("RGB").crop((0, 0, w, h)), dtype=np.float32)
    mean_abs = float(np.abs(x - y).mean())
    return {"mean_abs_diff": mean_abs, "mean_luma_a": float(x.mean()), "mean_luma_b": float(y.mean()),
            "similarity": 1.0 - mean_abs / 255.0}
