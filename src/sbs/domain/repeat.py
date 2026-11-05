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
