"""Répétition d'objets : ligne, grille, tracé (sans Qt). Renvoie des positions entières de pivots."""

import math

MAX_COUNT = 2000
Point = tuple[int, int]


def _check_count(n: int) -> None:
    if n > MAX_COUNT:
        raise ValueError(f"{n} objets demandés : {MAX_COUNT} au maximum")


def _int(name: str, v: object, lo: int, hi: int) -> int:
    if isinstance(v, bool) or not isinstance(v, int) or not (lo <= v <= hi):
        raise ValueError(f"{name} : un entier de {lo} à {hi}")
    return v


def line(origin: Point, count: int, step: Point) -> list[Point]:
    count = _int("nombre", count, 1, 10**6)
    _check_count(count)
    return [(origin[0] + i * step[0], origin[1] + i * step[1]) for i in range(count)]


def grid(origin: Point, cols: int, rows: int, step: Point) -> list[Point]:
    cols, rows = _int("colonnes", cols, 1, 10**6), _int("lignes", rows, 1, 10**6)
    _check_count(cols * rows)
    return [(origin[0] + c * step[0], origin[1] + r * step[1]) for r in range(rows) for c in range(cols)]


def cover(origin: Point, length: int, piece: int, horizontal: bool = True, fit: str = "over") -> list[Point]:
    """Pièces alignées pour couvrir une longueur (largeur si horizontal, hauteur sinon).
    `origin` = pivot de la première pièce ; `piece` = largeur (ou hauteur) d'une pièce, en pixels.
    - « over »   : assez de pièces pour tout couvrir, la dernière dépasse ;
    - « within » : seulement des pièces entières dans la longueur (un vide peut rester) ;
    - « exact »  : mêmes pièces que « over » mais réparties pour que la dernière finisse pile
                   à la longueur (léger chevauchement, jamais de vide)."""
    length, piece = _int("longueur", length, 1, 10**6), _int("pièce", piece, 1, 10**6)
    if fit not in ("over", "within", "exact"):
        raise ValueError("ajustement inconnu : over, within ou exact")
    n = max(1, length // piece) if fit == "within" else -(-length // piece)
    _check_count(n)
    if fit == "exact" and n > 1:
        # si la longueur est plus courte que la pièce, n vaut 1 ; sinon n >= 2 et length >= piece
        offsets = [round(i * (length - piece) / (n - 1)) for i in range(n)]
    else:
        offsets = [i * piece for i in range(n)]
    return [(origin[0] + o, origin[1]) if horizontal else (origin[0], origin[1] + o) for o in offsets]


def perspective(origin: Point, count: int, step: Point, last_percent: int, levels: int = 6) -> list[tuple[int, int, float]]:
    """Pièces qui s'éloignent en diagonale : la 1re est à taille normale (100 %), la dernière à `last_percent` %.
    `step` = avancée entre deux pièces à taille normale ; elle rétrécit avec la taille (pièces toujours jointives).
    Les tailles sont regroupées en `levels` paliers (2 à 12) pour ne créer que peu de modules.
    Renvoie [(x, y, échelle)] ; l'échelle vaut exactement 1.0 pour les pièces à taille normale."""
    count = _int("nombre", count, 1, 10**6)
    _check_count(count)
    last_percent = _int("échelle de la dernière pièce (%)", last_percent, 10, 100)
    levels = _int("niveaux", levels, 2, 12)
    last = last_percent / 100
    palette = [1.0 - (1.0 - last) * k / (levels - 1) for k in range(levels)]
    raw = [1.0 if count == 1 else 1.0 + (last - 1.0) * i / (count - 1) for i in range(count)]
    out: list[tuple[int, int, float]] = []
    fx, fy = float(origin[0]), float(origin[1])
    for i, r in enumerate(raw):
        q = min(palette, key=lambda v: abs(v - r))
        out.append((round(fx), round(fy), 1.0 if q >= 0.9999 else round(q, 4)))
        nxt = raw[i + 1] if i + 1 < count else r
        mid = (r + nxt) / 2  # l'avancée suit la taille moyenne des deux pièces voisines
        fx += step[0] * mid
        fy += step[1] * mid
    return out


def _catmull(p0, p1, p2, p3, t: float) -> tuple[float, float]:
    t2, t3 = t * t, t * t * t
    return tuple(  # type: ignore[return-value]
        0.5 * ((2 * p1[k]) + (-p0[k] + p2[k]) * t + (2 * p0[k] - 5 * p1[k] + 4 * p2[k] - p3[k]) * t2
               + (-p0[k] + 3 * p1[k] - 3 * p2[k] + p3[k]) * t3) for k in (0, 1))


def sample_path(points: list[Point], smooth: bool, per_segment: int = 32) -> list[tuple[float, float]]:
    """Polyligne dense passant par tous les points ; avec smooth, courbe de Catmull-Rom."""
    if len(points) < 2:
        raise ValueError("un tracé a besoin d'au moins 2 points")
    if len(points) > 200:
        raise ValueError("200 points de tracé au maximum")
    if not smooth or len(points) == 2:
        return [(float(x), float(y)) for x, y in points]
    out: list[tuple[float, float]] = []
    pts = [points[0], *points, points[-1]]
    for i in range(1, len(pts) - 2):
        for s in range(per_segment):
            out.append(_catmull(pts[i - 1], pts[i], pts[i + 1], pts[i + 2], s / per_segment))
    out.append((float(points[-1][0]), float(points[-1][1])))
    return out


def path_length(dense: list[tuple[float, float]]) -> float:
    return sum(math.dist(a, b) for a, b in zip(dense, dense[1:]))


def path(points: list[Point], smooth: bool = False, spacing: int | None = None,
         count: int | None = None) -> list[Point]:
    """Positions réparties le long du tracé : tous les `spacing` pixels (mesurés sur la courbe),
    ou `count` objets équidistants, extrémités comprises."""
    if (spacing is None) == (count is None):
        raise ValueError("indique soit l'espacement, soit le nombre d'objets")
    dense = sample_path(points, smooth)
    total = path_length(dense)
    if spacing is not None:
        spacing = _int("espacement", spacing, 1, 10**6)
        n = int(total // spacing) + 1
        targets = [i * spacing for i in range(n)]
    else:
        count = _int("nombre", count, 1, 10**6)
        targets = [0.0] if count == 1 else [i * total / (count - 1) for i in range(count)]
    _check_count(len(targets))
    out: list[Point] = []
    seg, walked = 0, 0.0
    for t in targets:
        while seg < len(dense) - 2 and walked + math.dist(dense[seg], dense[seg + 1]) < t:
            walked += math.dist(dense[seg], dense[seg + 1])
            seg += 1
        a, b = dense[seg], dense[seg + 1]
        d = math.dist(a, b)
        f = 0.0 if d == 0 else min(1.0, max(0.0, (t - walked) / d))
        out.append((round(a[0] + (b[0] - a[0]) * f), round(a[1] + (b[1] - a[1]) * f)))
    return out
