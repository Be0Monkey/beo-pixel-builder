import hashlib

import numpy as np
import pytest
from PIL import Image

from sbs.services.backgrounds import BACKGROUNDS, make_background
from sbs.services.lighting import (
    LightSettings,
    LitItem,
    compare_images,
    render_lit,
    shade_sprite,
    shadow_image,
)


def solid(w, h, rgba):
    return Image.new("RGBA", (w, h), rgba)


def normal_map(w, h, rgb):
    return Image.new("RGBA", (w, h), (*rgb, 255))


NO_AMBIENT = dict(ambient=0.0, intensity=1.0, light_color=(255, 255, 255), shadows=False)


def test_normale_vers_la_lumiere_eclaire_et_dos_a_la_lumiere_assombrit():
    base = solid(2, 2, (200, 200, 200, 255))
    right = normal_map(2, 2, (255, 128, 128))  # n ≈ (+1, 0, 0)
    lit = shade_sprite(base, right, None, LightSettings(azimuth=0, elevation=10, **NO_AMBIENT))
    dark = shade_sprite(base, right, None, LightSettings(azimuth=180, elevation=10, **NO_AMBIENT))
    assert lit.getpixel((0, 0))[0] > 150 and dark.getpixel((0, 0))[0] < 40
    assert lit.getpixel((0, 0))[3] == 255


def test_sans_carte_de_normales_eclairage_uniforme_et_alpha_conserve():
    base = Image.new("RGBA", (2, 1))
    base.putpixel((0, 0), (100, 100, 100, 255))
    base.putpixel((1, 0), (100, 100, 100, 0))
    out = shade_sprite(base, None, None, LightSettings(**NO_AMBIENT))
    assert out.getpixel((1, 0))[3] == 0 and out.getpixel((0, 0))[3] == 255


def test_emission_ajoute_de_la_lumiere_propre_et_reglable():
    base = solid(1, 1, (50, 50, 50, 255))
    em = solid(1, 1, (255, 200, 0, 255))
    s = LightSettings(ambient=0.0, intensity=0.0, shadows=False, emission=1.0)
    full = shade_sprite(base, None, em, s).getpixel((0, 0))
    off = shade_sprite(base, None, em, LightSettings(ambient=0.0, intensity=0.0, shadows=False, emission=0.0)).getpixel((0, 0))
    assert full[:3] == (50 * 0 + 255, 200, 0) and off[:3] == (0, 0, 0)


def test_flip_green_change_le_resultat_pour_une_normale_verticale():
    base = solid(1, 1, (200, 200, 200, 255))
    up = normal_map(1, 1, (128, 255, 128))  # vert max
    a = shade_sprite(base, up, None, LightSettings(azimuth=90, elevation=10, flip_green=False, **NO_AMBIENT))
    b = shade_sprite(base, up, None, LightSettings(azimuth=90, elevation=10, flip_green=True, **NO_AMBIENT))
    assert a.getpixel((0, 0))[0] != b.getpixel((0, 0))[0]


def test_reglages_invalides():
    for bad in (dict(elevation=0), dict(elevation=90), dict(intensity=-1), dict(shadow_opacity=2),
                dict(azimuth="x"), dict(light_color=(1, 2)), dict(emission=True)):
        with pytest.raises(ValueError):
            LightSettings(**bad).validate()
    LightSettings().validate()


def test_ombre_tombe_a_l_oppose_de_la_lumiere():
    alpha = solid(10, 20, (255, 255, 255, 255)).getchannel("A")
    sh, (dx, dy) = shadow_image(alpha, (5, 19), LightSettings(azimuth=135, elevation=40))
    assert sh.getbbox() is not None
    bbox = sh.getbbox()
    assert dx + bbox[2] > 10  # dépasse à droite du sprite (lumière en haut à gauche)
    sh2, (dx2, _) = shadow_image(alpha, (5, 19), LightSettings(azimuth=45, elevation=40))
    assert dx2 + sh2.getbbox()[0] < 0  # lumière en haut à droite : ombre à gauche
    low, _ = shadow_image(alpha, (5, 19), LightSettings(azimuth=135, elevation=10))
    high, _ = shadow_image(alpha, (5, 19), LightSettings(azimuth=135, elevation=80))
    assert low.getbbox()[2] - low.getbbox()[0] >= high.getbbox()[2] - high.getbbox()[0]  # soleil bas : ombre plus longue


def test_rendu_complet_non_destructif_et_valide(tmp_path):
    src = tmp_path / "s.png"
    solid(8, 8, (120, 60, 30, 255)).save(src)
    before = hashlib.sha256(src.read_bytes()).hexdigest()
    base = Image.open(src).convert("RGBA")
    item = LitItem(base, None, None, 10, 20, (4, 7))
    img, origin = render_lit([item], LightSettings(), "ciel", scale=3)
    assert img.width % 3 == 0 and origin[0] < 10 and origin[1] < 20
    assert hashlib.sha256(src.read_bytes()).hexdigest() == before  # le fichier n'a pas bougé
    transparent, _ = render_lit([item], LightSettings(shadows=False), "transparent")
    assert transparent.getpixel((0, 0))[3] == 0  # fond transparent respecté
    with pytest.raises(ValueError):
        render_lit([], LightSettings())
    with pytest.raises(ValueError):
        render_lit([item], LightSettings(), scale=0)
    with pytest.raises(ValueError):
        render_lit([item], LightSettings(), scale=9)


def test_fonds():
    for key in BACKGROUNDS:
        im = make_background(key, (4, 10))
        assert im.size == (4, 10) and im.getpixel((0, 0))[3] == 255
    ciel = make_background("ciel", (2, 50))
    assert ciel.getpixel((0, 0))[:3] == BACKGROUNDS["ciel"][1]
    assert ciel.getpixel((0, 49))[:3] == BACKGROUNDS["ciel"][2]
    with pytest.raises(ValueError):
        make_background("inconnu", (2, 2))


def test_comparaison_d_images():
    a = solid(4, 4, (10, 20, 30, 255))
    assert compare_images(a, a)["mean_abs_diff"] == 0
    r = compare_images(a, solid(4, 4, (110, 20, 30, 255)))
    assert abs(r["mean_abs_diff"] - 100 / 3) < 1e-3 and 0 < r["similarity"] < 1
    assert np.isfinite(compare_images(a, solid(2, 2, (0, 0, 0, 255)))["similarity"])
