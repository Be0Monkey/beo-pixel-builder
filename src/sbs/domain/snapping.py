"""Aimantation : calcul pur (sans Qt) du décalage à ajouter à un déplacement.

Trois sources (décision Q11) : grille, bords/boîtes englobantes, points d'ancrage (jalon J3).
L'aimantation ne s'applique qu'au glissement à la souris ; les flèches du clavier restent au pixel.
"""

from dataclasses import dataclass, field

Rect = tuple[int, int, int, int]  # gauche, haut, droite, bas (droite/bas exclus)


@dataclass
class SnapSettings:
    grid: bool = False
    edges: bool = False
    anchors: bool = False  # ancrages nommés des modules (J3)
    grid_size: int = 32
    threshold_px: int = 8  # seuil de capture, en pixels d'écran
    priority: str = "edges"  # à distance égale : "edges" ou "grid"


@dataclass
class SnapResult:
    dx: int = 0
    dy: int = 0
    guides: list[tuple[str, int]] = field(default_factory=list)  # ("v", x) ou ("h", y)


def _axis(moving: tuple[int, int], pivot: int, targets: list[int], s: SnapSettings, thr: int):
    """Meilleur décalage sur un axe : (décalage, guide ou None) ou None."""
    cands: list[tuple[int, int, int, int | None]] = []  # (|d|, rang de priorité, d, guide)
    lo, hi = moving
    if s.edges:
        rank = 0 if s.priority == "edges" else 1
        edges = [lo, hi] + ([(lo + hi) // 2] if (lo + hi) % 2 == 0 else [])
        for e in edges:
            for t in targets:
                d = t - e
                if abs(d) <= thr:
                    cands.append((abs(d), rank, d, t))
    if s.grid and s.grid_size > 0:
        g = s.grid_size
        d = round(pivot / g) * g - pivot
        if abs(d) <= thr:
            cands.append((abs(d), 1 if s.priority == "edges" else 0, d, None))
    if not cands:
        return None
    cands.sort(key=lambda c: (c[0], c[1]))
    best = cands[0]
    guides = {c[3] for c in cands if c[2] == best[2] and c[3] is not None}
    return best[2], sorted(guides)


def _anchor_snap(moving_points, other_points, thr: int):
    """Meilleure paire d'ancrages (un de la sélection, un d'un autre module) à portée sur X ET Y."""
    best = None
    for mx, my in moving_points:
        for ox, oy in other_points:
            dx, dy = ox - mx, oy - my
            if abs(dx) <= thr and abs(dy) <= thr:
                key = (abs(dx) + abs(dy), ox, oy)
                if best is None or key < best[0]:
                    best = (key, dx, dy, ox, oy)
    return best


def compute_snap(moving: Rect, pivot: tuple[int, int], others: list[Rect],
                 settings: SnapSettings, zoom: float, moving_points=(), other_points=()) -> SnapResult:
    """moving : boîte (déjà déplacée du geste brut) de la sélection ; pivot : pivot de l'objet saisi.
    moving_points / other_points : ancrages nommés (coordonnées de la scène), pour settings.anchors."""
    if not (settings.grid or settings.edges or settings.anchors):
        return SnapResult()
    thr = max(1, round(settings.threshold_px / max(zoom, 0.01)))
    if settings.anchors and moving_points and other_points:
        hit = _anchor_snap(moving_points, other_points, thr)
        if hit:  # un ancrage tombe sur un autre : il gagne sur grille et bords (2 axes d'un coup)
            _, dx, dy, ox, oy = hit
            return SnapResult(dx, dy, [("v", ox), ("h", oy)])
    xs: list[int] = []
    ys: list[int] = []
    for l, t, r, b in others:
        xs += [l, r] + ([(l + r) // 2] if (l + r) % 2 == 0 else [])
        ys += [t, b] + ([(t + b) // 2] if (t + b) % 2 == 0 else [])
    res = SnapResult()
    ax = _axis((moving[0], moving[2]), pivot[0], xs, settings, thr)
    ay = _axis((moving[1], moving[3]), pivot[1], ys, settings, thr)
    if ax:
        res.dx = ax[0]
        res.guides += [("v", g) for g in ax[1]]
    if ay:
        res.dy = ay[0]
        res.guides += [("h", g) for g in ay[1]]
    return res
