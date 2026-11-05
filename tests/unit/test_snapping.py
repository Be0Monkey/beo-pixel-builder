from sbs.domain.snapping import SnapSettings, compute_snap

OFF = SnapSettings()


def test_aimant_coupe_ne_change_rien():
    r = compute_snap((3, 3, 20, 20), (5, 5), [(40, 3, 60, 20)], OFF, 1.0)
    assert (r.dx, r.dy, r.guides) == (0, 0, [])


def test_grille_sur_le_pivot():
    s = SnapSettings(grid=True, grid_size=32)
    r = compute_snap((100, 0, 116, 20), (98, 17), [], s, 1.0)  # pivot 98 -> 96 (écart 2)
    assert r.dx == -2
    far = compute_snap((100, 0, 116, 20), (80, 17), [], s, 1.0)  # 80 : à 16 de 64 et 96 > seuil
    assert far.dx == 0


def test_bords_adjacents_gauche_droite_et_guide():
    s = SnapSettings(edges=True)
    other = (0, 0, 32, 32)
    r = compute_snap((35, 0, 51, 32), (40, 32), [other], s, 1.0)  # bord gauche 35 -> 32
    assert r.dx == -3 and ("v", 32) in r.guides


def test_seuil_depend_du_zoom():
    s = SnapSettings(edges=True, threshold_px=8)
    other = (0, 0, 32, 32)
    assert compute_snap((41, 0, 57, 32), (45, 32), [other], s, 1.0).dx == 0   # 9 px > seuil de 8
    assert compute_snap((40, 0, 56, 32), (45, 32), [other], s, 4.0).dx == 0   # seuil 2 px
    assert compute_snap((34, 0, 50, 32), (40, 32), [other], s, 4.0).dx == -2  # dans le seuil


def test_ancrages_gagnent_et_snap_sur_deux_axes():
    s = SnapSettings(anchors=True, grid=True)
    r = compute_snap((0, 0, 16, 20), (3, 17), [], s, 1.0,
                     moving_points=[(10, 10)], other_points=[(13, 8), (100, 100)])
    assert (r.dx, r.dy) == (3, -2) and ("v", 13) in r.guides and ("h", 8) in r.guides


def test_ancrages_trop_loin_ou_desactives():
    far = compute_snap((0, 0, 16, 20), (3, 17), [], SnapSettings(anchors=True), 1.0,
                       moving_points=[(10, 10)], other_points=[(60, 10)])
    assert (far.dx, far.dy) == (0, 0)
    off = compute_snap((0, 0, 16, 20), (400, 400), [], SnapSettings(grid=True, grid_size=1000), 1.0,
                       moving_points=[(10, 10)], other_points=[(12, 10)])
    assert (off.dx, off.dy) == (0, 0)
