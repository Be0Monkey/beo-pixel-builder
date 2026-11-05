import json
import os
from pathlib import Path

import pytest
from PIL import Image, ImageChops

from sbs.domain.scene import Instance, SceneModel
from sbs.services.exporter import ExportError, export_png, render_scene
from sbs.services.kit_importer import import_kit
from sbs.services.library import Library
from tests.unit.test_kit_importer import card, make_files, make_kit


def _rgba_sprite(path: Path, size=(16, 20)):
    """Sprite avec pixels opaques, semi-transparents et transparents."""
    im = Image.new("RGBA", size, (0, 0, 0, 0))
    px = im.load()
    for y in range(size[1]):
        for x in range(size[0]):
            k = (x + y) % 4
            px[x, y] = [(0, 0, 0, 0), (200, 30, 40, 255), (30, 200, 90, 128), (10, 20, 250, 17)][k]
    path.parent.mkdir(parents=True, exist_ok=True)
    im.save(path)
    return im


@pytest.fixture
def env(tmp_path):
    c = card("mur_a")  # pivot (3, 17), 16x20
    kit = make_kit(tmp_path / "kit", [c])
    make_files(kit, c)
    original = _rgba_sprite(kit / "modules_px" / c["fichiers"]["sprite"])
    Image.new("RGBA", (16, 20), (255, 255, 0, 255)).save(kit / "modules_px" / c["variantes"]["gres"])
    lib = Library(tmp_path / "lib")
    import_kit(lib, kit)
    return lib, lib.list_assets()[0], original, tmp_path


def _same_pixels(a: Image.Image, b: Image.Image):
    assert a.size == b.size
    assert a.getchannel("A").tobytes() == b.getchannel("A").tobytes()
    # couleurs comparées là où le pixel est visible
    pa, pb = a.load(), b.load()
    for y in range(a.height):
        for x in range(a.width):
            if pa[x, y][3] > 0:
                assert pa[x, y] == pb[x, y], (x, y)


def test_t09_un_sprite_exporte_est_identique_a_l_original(env):
    lib, asset, original, tmp = env
    m = SceneModel()
    m.add(asset.uuid, 100, 50)
    r = export_png(tmp / "out" / "maison é.png", m.draw_instances(), lib)
    out = Image.open(r.path)
    assert out.mode == "RGBA"
    _same_pixels(out, original)
    assert r.origin == (100 - 3, 50 - 17) and (r.width, r.height) == (16, 20)


def test_ordre_de_dessin_profondeur_puis_z_manuel(env):
    lib, asset, original, tmp = env
    m = SceneModel()
    loin = m.add(asset.uuid, 0, 10)
    pres = m.add(asset.uuid, 1, 10)  # même y : insertion → pres au-dessus
    img, _ = render_scene(m.draw_instances(), lib)
    assert img.size == (17, 20)  # deux sprites décalés d'un pixel
    # même profondeur : « pres » (inséré après) recouvre « loin » ; en forçant « loin » devant,
    # le résultat change.
    m.set_z_manual(loin.id, 1)
    img2, _ = render_scene(m.draw_instances(), lib)
    assert img.tobytes() != img2.tobytes()
    m.set_z_manual(loin.id, 0)
    assert render_scene(m.draw_instances(), lib)[0].tobytes() == img.tobytes()  # déterministe


def test_variante_exportee(env):
    lib, asset, original, tmp = env
    m = SceneModel()
    i = m.add(asset.uuid, 0, 0)
    i.variant = "gres"
    img, _ = render_scene(m.draw_instances(), lib)
    assert img.getpixel((0, 0)) == (255, 255, 0, 255)


def test_rectangle_explicite_decoupe_et_decalage(env):
    lib, asset, original, tmp = env
    m = SceneModel()
    m.add(asset.uuid, 0, 0)  # image en (-3, -17)
    img, r = render_scene(m.draw_instances(), lib, rect=(-3, -17, 8, 10))
    assert img.size == (8, 10)
    _same_pixels(img, original.crop((0, 0, 8, 10)))
    vide, _ = render_scene(m.draw_instances(), lib, rect=(500, 500, 4, 4))
    assert vide.getbbox() is None  # tout transparent, pas de plantage
    img, _ = render_scene(m.draw_instances(), lib, rect=(-20, -30, 40, 40))  # plus grand que le sprite
    assert img.getpixel((0, 0)) == (0, 0, 0, 0)


def test_agrandissement_entier_sans_flou(env):
    lib, asset, original, tmp = env
    m = SceneModel()
    m.add(asset.uuid, 0, 0)
    img, r = render_scene(m.draw_instances(), lib, scale=3)
    assert img.size == (48, 60) and r.scale == 3
    base, _ = render_scene(m.draw_instances(), lib)
    for y in (0, 7, 19):
        for x in (0, 5, 15):
            for dy in range(3):
                for dx in range(3):
                    assert img.getpixel((x * 3 + dx, y * 3 + dy)) == base.getpixel((x, y))


@pytest.mark.parametrize("scale", [0, 17, 1.5, True, "2"])
def test_facteur_invalide(env, scale):
    lib, asset, _, _ = env
    m = SceneModel()
    m.add(asset.uuid, 0, 0)
    with pytest.raises(ExportError):
        render_scene(m.draw_instances(), lib, scale=scale)


@pytest.mark.parametrize("rect", [(0, 0, 0, 5), (0, 0, 5, -1), (0, 0, 1.5, 5)])
def test_rectangle_invalide(env, rect):
    lib, asset, _, _ = env
    m = SceneModel()
    m.add(asset.uuid, 0, 0)
    with pytest.raises(ExportError):
        render_scene(m.draw_instances(), lib, rect=rect)


def test_scene_vide_et_trop_grande(env):
    lib, asset, _, _ = env
    with pytest.raises(ExportError, match="Rien à exporter"):
        render_scene([], lib)
    m = SceneModel()
    m.add(asset.uuid, 0, 0)
    with pytest.raises(ExportError, match="trop grande"):
        render_scene(m.draw_instances(), lib, rect=(0, 0, 20000, 20000))


def test_image_manquante_signalee_et_le_reste_exporte(env):
    lib, asset, _, tmp = env
    m = SceneModel()
    m.add(asset.uuid, 0, 0)
    m.add("uuid-inconnu", 5, 5)
    r = export_png(tmp / "o.png", m.draw_instances(), lib)
    assert r.count == 1 and r.skipped == ["uuid-inconnu"] and r.path.exists()


def test_echec_d_ecriture_laisse_le_fichier_precedent(env, monkeypatch):
    lib, asset, _, tmp = env
    m = SceneModel()
    m.add(asset.uuid, 0, 0)
    out = tmp / "o.png"
    export_png(out, m.draw_instances(), lib)
    before = out.read_bytes()

    def boom(*a, **k):
        raise OSError("disque plein simulé")

    monkeypatch.setattr("sbs.services.exporter.os.replace", boom)
    with pytest.raises(ExportError, match="n'a pas été modifié"):
        export_png(out, m.draw_instances(), lib)
    assert out.read_bytes() == before
    assert [p for p in tmp.iterdir() if p.suffix == ".tmp"] == []


@pytest.mark.skipif(not os.environ.get("SBS_KIT_DIR"), reason="kit réel non indiqué (SBS_KIT_DIR)")
def test_recettes_du_kit_identiques_aux_images_de_reference(tmp_path):
    """Bout en bout : import du kit -> instances d'une recette -> export -> 0 pixel de différence."""
    kit = Path(os.environ["SBS_KIT_DIR"])
    lib = Library(tmp_path / "lib")
    import_kit(lib, kit)
    by_id = {a.source_id: a for a in lib.list_assets()}
    checked = 0
    for recipe in sorted((kit / "recipes").glob("*.json")):
        rec = json.loads(recipe.read_text(encoding="utf-8"))
        ref_path = kit / "assemblages" / f"{rec['id']}_sprite.png"
        if not ref_path.exists():
            continue
        # Recettes à plusieurs variantes (ex. "boulangerie") : fichiers nommés <id>_<variante>.
        insts = []
        for e in rec["elements"]:
            a = by_id.get(e["m"])
            if a is None:
                break
            variant = next((v for v in rec.get("variantes", []) if any(x.name == v for x in a.variants)), None)
            insts.append(Instance(f"{len(insts)}", a.uuid, e["x"], -e["y"], 0, variant))
        else:
            ref = Image.open(ref_path).convert("RGBA")
            out, _ = render_scene(insts, lib)
            rc, oc = ref.crop(ref.getchannel("A").getbbox()), out.crop(out.getchannel("A").getbbox())
            if rc.size != oc.size:
                continue  # la recette n'est pas celle de cette image de référence
            diff = ImageChops.difference(rc, oc).getbbox()
            assert diff is None, f"{rec['id']} : différences à {diff}"
            checked += 1
    assert checked >= 1
