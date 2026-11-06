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


# ------------------------------------------------------------------ perspective (mur qui s'éloigne)
def test_perspective_tailles_decroissantes_et_pieces_jointives():
    pieces = R.perspective((0, 100), 6, (32, -16), 50, levels=6)
    scales = [p[2] for p in pieces]
    assert scales[0] == 1.0 and scales[-1] == 0.5
    assert scales == sorted(scales, reverse=True)  # jamais plus grand en s'éloignant
    xs = [p[0] for p in pieces]
    gaps = [b - a for a, b in zip(xs, xs[1:])]
    assert gaps == sorted(gaps, reverse=True) and gaps[0] <= 32 and gaps[-1] >= 16  # l'avancée rétrécit aussi
    assert all(b[1] < a[1] for a, b in zip(pieces, pieces[1:]))  # monte à l'écran : s'éloigne


def test_perspective_paliers_limites_et_cas_simples():
    pieces = R.perspective((0, 0), 40, (10, -5), 25, levels=4)
    assert len({p[2] for p in pieces}) <= 4  # peu de modules à créer
    assert R.perspective((5, 5), 1, (10, 10), 50) == [(5, 5, 1.0)]
    flat = R.perspective((0, 0), 4, (8, 0), 100)
    assert {p[2] for p in flat} == {1.0} and [p[0] for p in flat] == [0, 8, 16, 24]
    for bad in ({"last_percent": 5}, {"last_percent": 101}, {"levels": 1}, {"levels": 13}, {"count": 0}):
        args = dict(origin=(0, 0), count=5, step=(8, -4), last_percent=50, levels=6) | bad
        with pytest.raises(ValueError):
            R.perspective(**args)


def test_create_scaled_reduit_en_gardant_le_bas_et_reutilise(tmp_path):
    lib, a, src = make_asset(tmp_path, size=(8, 10), pivot=(4, 9))
    half, created = RZ.create_scaled(lib, a.uuid, 0.5)
    assert created and (half.width, half.height) == (4, 5) and half.name == "mur 50%"
    assert half.pivot_y == 4  # le bas du sprite reste le bas
    img = Image.open(lib.abs_path(half.image_path)).convert("RGBA")
    assert {img.getpixel((x, y)) for x in range(4) for y in range(5)} <= {
        src.getpixel((x, y)) for x in range(8) for y in range(10)}  # aucune couleur inventée
    again, created2 = RZ.create_scaled(lib, a.uuid, 0.5)
    assert not created2 and again.uuid == half.uuid and lib.count() == 2  # réutilisé
    same, c3 = RZ.create_scaled(lib, a.uuid, 1.0)
    assert same.uuid == a.uuid and not c3
    for bad in (0.05, 1.5, True, "x"):
        with pytest.raises(ValueError, match="comprise"):
            RZ.create_scaled(lib, a.uuid, bad)
