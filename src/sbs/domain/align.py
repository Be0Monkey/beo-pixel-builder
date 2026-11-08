"""Aligner et répartir : calcul pur des décalages (en pixels entiers) à appliquer à chaque élément.

Un élément = un rectangle (gauche, haut, droite, bas) : un objet seul ou l'ensemble d'un groupe.
"""

MODES = ("left", "hcenter", "right", "top", "vcenter", "bottom", "dist_h", "dist_v")

Box = tuple[int, int, int, int]


def align_shifts(boxes: list[Box], mode: str) -> list[tuple[int, int]]:
    if mode not in MODES:
        raise ValueError("mode d'alignement inconnu")
    n = len(boxes)
    if n < 2:
        raise ValueError("Sélectionne au moins deux objets (ou groupes) à aligner.")
    if mode in ("dist_h", "dist_v") and n < 3:
        raise ValueError("Répartir demande au moins trois objets (ou groupes).")
    left = min(b[0] for b in boxes)
    top = min(b[1] for b in boxes)
    right = max(b[2] for b in boxes)
    bottom = max(b[3] for b in boxes)
    out = [(0, 0)] * n
    if mode == "left":
        out = [(left - b[0], 0) for b in boxes]
    elif mode == "right":
        out = [(right - b[2], 0) for b in boxes]
    elif mode == "hcenter":
        out = [(round((left + right) / 2 - (b[0] + b[2]) / 2), 0) for b in boxes]
    elif mode == "top":
        out = [(0, top - b[1]) for b in boxes]
    elif mode == "bottom":
        out = [(0, bottom - b[3]) for b in boxes]
    elif mode == "vcenter":
        out = [(0, round((top + bottom) / 2 - (b[1] + b[3]) / 2)) for b in boxes]
    else:
        horizontal = mode == "dist_h"
        lo, hi = (0, 2) if horizontal else (1, 3)
        order = sorted(range(n), key=lambda i: boxes[i][lo] + boxes[i][hi])
        span = boxes[order[-1]][hi] - boxes[order[0]][lo]
        total = sum(boxes[i][hi] - boxes[i][lo] for i in order)
        gap = (span - total) / (n - 1)
        pos = boxes[order[0]][lo]
        for i in order:
            d = round(pos) - boxes[i][lo]
            out[i] = (d, 0) if horizontal else (0, d)
            pos += (boxes[i][hi] - boxes[i][lo]) + gap
    return out
