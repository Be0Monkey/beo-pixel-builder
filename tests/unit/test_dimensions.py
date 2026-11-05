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
