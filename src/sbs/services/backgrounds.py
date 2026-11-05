"""Fonds de prévisualisation (jamais enregistrés dans les sprites ni dans les projets)."""

import numpy as np
from PIL import Image

# nom -> (libellé, couleur haut, couleur bas)
BACKGROUNDS: dict[str, tuple[str, tuple[int, int, int], tuple[int, int, int]]] = {
    "ciel": ("Ciel", (120, 175, 230), (215, 232, 248)),
    "herbe": ("Herbe", (74, 128, 48), (92, 150, 58)),
    "terre": ("Terre", (150, 122, 84), (170, 140, 98)),
    "nuit": ("Nuit", (14, 18, 44), (42, 52, 96)),
    "gris": ("Gris neutre", (110, 110, 110), (110, 110, 110)),
}


def make_background(kind: str, size: tuple[int, int]) -> Image.Image:
    if kind not in BACKGROUNDS:
        raise ValueError(f"fond inconnu : {kind}")
    w, h = size
    if w < 1 or h < 1:
        raise ValueError("taille de fond invalide")
    _, top, bottom = BACKGROUNDS[kind]
    t = np.linspace(0.0, 1.0, h, dtype=np.float32)[:, None, None]
    row = np.array(top, dtype=np.float32) * (1 - t) + np.array(bottom, dtype=np.float32) * t
    arr = np.broadcast_to(row, (h, w, 3))
    return Image.fromarray(np.concatenate([arr, np.full((h, w, 1), 255, np.float32)], axis=-1).astype(np.uint8), "RGBA")
