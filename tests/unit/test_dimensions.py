"""J3 « dimensions libres » : redimensionner avec pixels nets, couvrir une longueur."""

import io

import pytest
from PIL import Image

from sbs.domain import repeat as R
from sbs.domain.asset import Anchor
from sbs.services import resize as RZ
from sbs.services.library import Library


def make_asset(tmp_path, size=(4, 6), pivot=(2, 5)):
    lib = Library(tmp_path / "lib")
    im = Image.new("RGBA", size)
    for x in range(size[0]):
        for y in range(size[1]):
            im.putpixel((x, y), (x * 40, y * 30, 7, 255 if (x + y) % 2 else 100))  # chaque pixel est unique
    buf = io.BytesIO()
    im.save(buf, "PNG")
    a = lib.create_asset("mur", buf.getvalue(), pivot, "murs")
    return lib, a, im


# ------------------------------------------------------------------ couvrir une longueur
def test_cover_over_within_exact():
    assert R.cover((0, 10), 100, 32) == [(0, 10), (32, 10), (64, 10), (96, 10)]  # 128 px : dépasse
    assert R.cover((0, 10), 100, 32, fit="within") == [(0, 10), (32, 10), (64, 10)]  # 96 px : vide de 4
    ex = R.cover((0, 10), 100, 32, fit="exact")
    assert len(ex) == 4 and ex[0] == (0, 10) and ex[-1] == (68, 10)  # dernière pièce finit pile à 100
    assert all(b[0] - a[0] <= 32 for a, b in zip(ex, ex[1:]))  # jamais de vide entre pièces
    assert R.cover((5, 5), 64, 32) == [(5, 5), (37, 5)]  # division exacte : pas de pièce en trop


def test_cover_vertical_origine_et_cas_limites():
    assert R.cover((7, 0), 50, 20, horizontal=False) == [(7, 0), (7, 20), (7, 40)]
    assert R.cover((0, 0), 10, 32) == [(0, 0)]  # longueur plus courte qu'une pièce : une pièce
    assert R.cover((0, 0), 10, 32, fit="within") == [(0, 0)]  # au moins une
    assert R.cover((0, 0), 10, 32, fit="exact") == [(0, 0)]


def test_cover_refus():
    for args in ((0, 32), (-5, 32), (100, 0), (True, 32)):
        with pytest.raises(ValueError):
            R.cover((0, 0), *args)
    with pytest.raises(ValueError, match="ajustement"):
        R.cover((0, 0), 100, 10, fit="autre")
    with pytest.raises(ValueError, match="au maximum"):
        R.cover((0, 0), 10**6, 1)


# ------------------------------------------------------------------ redimensionner
def test_agrandir_pixels_nets_et_pivot(tmp_path):
    lib, a, src = make_asset(tmp_path)
    new = RZ.create_resized(lib, a.uuid, "up", 3)
    assert (new.width, new.height) == (12, 18) and new.name == "mur ×3" and new.category == "murs"
    out = Image.open(lib.abs_path(new.image_path)).convert("RGBA")
    for x in range(12):
        for y in range(18):
            assert out.getpixel((x, y)) == src.getpixel((x // 3, y // 3))  # blocs exacts : aucune couleur nouvelle
    assert len({out.getpixel((x, y)) for x in range(12) for y in range(18)}) == len(
        {src.getpixel((x, y)) for x in range(4) for y in range(6)})
    assert (new.pivot_x, new.pivot_y) == (2 * 3 + 1, 17)  # le bas reste le bas (dernier pixel)
    assert lib.get(a.uuid).width == 4  # l'original n'est pas touché
    assert lib.count() == 2


def test_reduire_exige_une_taille_divisible(tmp_path):
    lib, a, src = make_asset(tmp_path, size=(8, 6), pivot=(4, 5))
    with pytest.raises(ValueError, match="divisible"):
        RZ.create_resized(lib, a.uuid, "down", 4)
    assert lib.count() == 1  # rien n'a été créé
    new = RZ.create_resized(lib, a.uuid, "down", 2)
    assert (new.width, new.height) == (4, 3) and (new.pivot_x, new.pivot_y) == (2, 2)
    out = Image.open(lib.abs_path(new.image_path)).convert("RGBA")
    assert out.getpixel((1, 1)) == src.getpixel((3, 3))  # pixel central du bloc 2×2


def test_aller_retour_agrandir_puis_reduire_identique(tmp_path):
    lib, a, src = make_asset(tmp_path)
    big = RZ.create_resized(lib, a.uuid, "up", 4)
    back = RZ.create_resized(lib, big.uuid, "down", 4)
    assert Image.open(lib.abs_path(back.image_path)).convert("RGBA").tobytes() == src.tobytes()
    assert (back.pivot_x, back.pivot_y) == (a.pivot_x, a.pivot_y)


def test_ancrages_et_mots_cles_suivent(tmp_path):
    lib, a, _ = make_asset(tmp_path)
    lib.update_geometry(a.uuid, (2, 5), [Anchor("haut", 1, 0), Anchor("coin", 4, 6)])
    lib.set_tags(a.uuid, ["pierre"])
    new = RZ.create_resized(lib, a.uuid, "up", 2)
    pts = {x.name: (x.x, x.y) for x in new.anchors}
    assert pts == {"haut": (3, 1), "coin": (8, 12)}  # centre du bloc ; bord extérieur reste au bord
    assert new.tags == ("pierre",)


def test_limites_et_facteurs_invalides(tmp_path):
    lib, a, _ = make_asset(tmp_path, size=(600, 600), pivot=(300, 599))
    with pytest.raises(ValueError, match="trop grand"):
        RZ.create_resized(lib, a.uuid, "up", 8)
    for mode, k in (("up", 1), ("up", 9), ("sideways", 2), ("up", True), ("down", 0)):
        with pytest.raises(ValueError, match="facteur"):
            RZ.target_size(4, 4, mode, k)
    with pytest.raises(ValueError, match="absent"):
        RZ.create_resized(lib, "inconnu", "up", 2)
    assert RZ.label("up", 3) == "×3" and RZ.label("down", 2) == "÷2"


# ------------------------------------------------------------------ mur en perspective (bords alignés)
def test_mur_raccords_exacts_et_convergence():
    ps = R.perspective_wall((0, 100), 6, 32, -50, 50)
    assert len(ps) == 6 and ps[0].s_left == 1.0 and abs(ps[-1].s_right - 0.5) < 1e-9
    for a, b in zip(ps, ps[1:]):
        assert a.x + a.width == b.x  # pas de trou en largeur
        assert a.y + a.drop == b.y  # le bas du bord droit = le bas du bord gauche suivant
        assert a.s_right == b.s_left  # même hauteur au raccord
    widths = [p.width for p in ps]
    assert widths == sorted(widths, reverse=True) and widths[0] <= 32  # raccourci de perspective
    assert all(b.y < a.y for a, b in zip(ps, ps[1:]))  # le sol monte : s'éloigne


def test_mur_cas_simples_et_limites():
    one = R.perspective_wall((5, 7), 1, 10, 0, 100)
    assert one == [R.WallPiece(5, 7, 10, 1.0, 1.0, 0)]
    for bad in ({"last_percent": 5}, {"last_percent": 101}, {"count": 0}, {"count": 41}, {"piece_width": 0},
                {"slope_percent": 301}):
        args = dict(origin=(0, 0), count=5, piece_width=8, slope_percent=-50, last_percent=50) | bad
        with pytest.raises(ValueError):
            R.perspective_wall(**args)


def test_warp_wall_piece_hauteurs_et_couleurs(tmp_path):
    lib, a, src = make_asset(tmp_path, size=(8, 10), pivot=(0, 9))
    img, pivot = RZ.warp_wall_piece(src, 8, 1.0, 0.5, -4)
    alpha = [[img.getpixel((x, y))[3] for y in range(img.height)] for x in range(img.width)]

    def col_height(x):
        ys = [y for y, v in enumerate(alpha[x]) if v]
        return (max(ys) - min(ys) + 1) if ys else 0
    assert col_height(0) >= 9 and col_height(7) <= 6  # la hauteur diminue vers la droite
    assert pivot[0] == 0 and pivot[1] >= 0
    seen = {img.getpixel((x, y))[:3] for x in range(img.width) for y in range(img.height)
            if img.getpixel((x, y))[3]}
    assert seen <= {src.getpixel((x, y))[:3] for x in range(8) for y in range(10)}  # aucune couleur inventée
    with pytest.raises(ValueError):
        RZ.warp_wall_piece(src, 0, 1.0, 0.5, 0)


def test_create_wall_piece_reutilise(tmp_path):
    lib, a, _ = make_asset(tmp_path, size=(8, 10), pivot=(0, 9))
    m, created = RZ.create_wall_piece(lib, a.uuid, 8, 1.0, 0.5, -4, "1/1")
    assert created and "perspective" in m.name
    again, created2 = RZ.create_wall_piece(lib, a.uuid, 8, 1.0, 0.5, -4, "1/1")
    assert not created2 and again.uuid == m.uuid
    with pytest.raises(ValueError, match="absent"):
        RZ.create_wall_piece(lib, "inconnu", 8, 1.0, 0.5, 0)




# ------------------------------------------------------------------ miroir et alignement
def test_miroir_retourne_image_pivot_ancrages_et_se_reutilise(tmp_path):
    lib, a, im = make_asset(tmp_path)
    lib.update_geometry(a.uuid, (1, 5), [Anchor("main", 3, 2)], revision=a.revision)
    lib.set_tags(a.uuid, ["pierre"])
    m, created = RZ.create_mirrored(lib, a.uuid)
    assert created and m.name == "mur (miroir)" and list(m.tags) == ["pierre"]
    out = Image.open(io.BytesIO(lib.image_bytes(m.uuid))).convert("RGBA")
    assert out.getpixel((0, 1)) == im.getpixel((3, 1)) and out.getpixel((3, 4)) == im.getpixel((0, 4))
    assert (m.pivot_x, m.pivot_y) == (3, 5)  # 4 - 1
    assert [(x.x, x.y) for x in m.anchors] == [(1, 2)]  # 4 - 3
    again, created2 = RZ.create_mirrored(lib, a.uuid)
    assert not created2 and again.uuid == m.uuid  # rien de dupliqué
    back, created3 = RZ.create_mirrored(lib, m.uuid)
    assert back.uuid == a.uuid and not created3 and back.name == "mur"  # le miroir du miroir est l'original


def test_miroir_module_inconnu(tmp_path):
    lib, a, _ = make_asset(tmp_path)
    with pytest.raises(ValueError):
        RZ.create_mirrored(lib, "inconnu")


def test_alignement_calcul():
    from sbs.domain.align import align_shifts
    boxes = [(0, 0, 10, 10), (20, 5, 24, 9), (40, 2, 50, 20)]
    assert align_shifts(boxes, "left") == [(0, 0), (-20, 0), (-40, 0)]
    assert align_shifts(boxes, "right") == [(40, 0), (26, 0), (0, 0)]
    assert align_shifts(boxes, "top") == [(0, 0), (0, -5), (0, -2)]
    assert align_shifts(boxes, "bottom") == [(0, 10), (0, 11), (0, 0)]
    assert align_shifts(boxes, "hcenter") == [(20, 0), (3, 0), (-20, 0)]  # centre commun : 25


def test_alignement_repartition_et_refus():
    from sbs.domain.align import align_shifts
    boxes = [(0, 0, 10, 10), (12, 0, 22, 10), (90, 0, 100, 10)]
    sh = align_shifts(boxes, "dist_h")  # espaces égaux : 100 - 30 = 70 / 2 = 35
    assert [b[0] + d[0] for b, d in zip(boxes, sh)] == [0, 45, 90]
    with pytest.raises(ValueError):
        align_shifts(boxes[:1], "left")
    with pytest.raises(ValueError):
        align_shifts(boxes[:2], "dist_h")
    with pytest.raises(ValueError):
        align_shifts(boxes, "nimporte")
