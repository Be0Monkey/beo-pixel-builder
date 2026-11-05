import json
import math

import pytest
from PIL import Image

from sbs.domain import repeat as R
from sbs.domain.animation import Animation, Frame, frame_index_at, total_ticks, validate_animation
from sbs.domain.scene import SceneModel
from sbs.services.animation_tools import export_animation, import_sheet
from sbs.services.kit_importer import import_kit
from sbs.services.library import Library
from sbs.services.project_io import ProjectError, ProjectMeta, load_project, save_project
from sbs.services.spritesheet import FrameImage, SheetError, build_sheet, slice_sheet
from tests.unit.test_kit_importer import card, make_files, make_kit


# ------------------------------------------------------------------ répétition
def test_ligne_et_grille():
    assert R.line((10, 20), 3, (16, -4)) == [(10, 20), (26, 16), (42, 12)]
    g = R.grid((0, 0), 3, 2, (10, 5))
    assert g == [(0, 0), (10, 0), (20, 0), (0, 5), (10, 5), (20, 5)]


@pytest.mark.parametrize("call", [
    lambda: R.line((0, 0), 0, (1, 1)), lambda: R.line((0, 0), R.MAX_COUNT + 1, (1, 1)),
    lambda: R.grid((0, 0), 50, 50, (1, 1)), lambda: R.line((0, 0), 2.5, (1, 1)),
    lambda: R.path([(0, 0)], spacing=4), lambda: R.path([(0, 0), (9, 9)]),
    lambda: R.path([(0, 0), (9, 9)], spacing=4, count=3), lambda: R.path([(0, 0), (9, 9)], spacing=0),
    lambda: R.path([(0, 0), (10000, 0)], spacing=1),
])
def test_repetition_invalide_refusee(call):
    with pytest.raises(ValueError):
        call()


def test_trace_droit_espacement_et_nombre():
    assert R.path([(0, 0), (100, 0)], spacing=25) == [(0, 0), (25, 0), (50, 0), (75, 0), (100, 0)]
    assert R.path([(0, 0), (100, 0)], count=3) == [(0, 0), (50, 0), (100, 0)]
    assert R.path([(0, 0), (100, 0)], count=1) == [(0, 0)]
    # polyligne coudée : l'espacement se mesure sur le chemin, pas en ligne droite
    pts = R.path([(0, 0), (40, 0), (40, 40)], spacing=20)
    assert pts == [(0, 0), (20, 0), (40, 0), (40, 20), (40, 40)]


def test_cloture_le_long_dune_courbe_simple():
    ctrl = [(0, 0), (60, -40), (120, 0), (180, 40)]
    pts = R.path(ctrl, smooth=True, spacing=16)
    assert pts[0] == (0, 0) and len(pts) > 10
    dense = R.sample_path(ctrl, True)
    total = R.path_length(dense)
    assert len(pts) == int(total // 16) + 1
    gaps = [math.dist(a, b) for a, b in zip(pts, pts[1:])]
    assert all(10 <= g <= 17.5 for g in gaps)  # pas réguliers (la corde est un peu plus courte que l'arc)
    for c in ctrl:  # la courbe passe par les points de contrôle
        assert min(math.dist(c, d) for d in dense) < 1e-6
    assert R.path(ctrl, smooth=True, count=7)[-1] == (180, 40)  # extrémité atteinte


# ------------------------------------------------------------------ animations
def _anim(*holds, fps=10, loop=True):
    return Animation("a", "Porte", fps, loop, [Frame(f"u{i}", None, h) for i, h in enumerate(holds)])


def test_validation_animation():
    validate_animation(_anim(1, 2))
    for bad in (Animation("", "x"), Animation("a", " "), Animation("a", "x", 0), Animation("a", "x", 61),
                Animation("a", "x", 8, "oui"), Animation("a", "x", 8, True, [Frame("", None, 1)]),
                Animation("a", "x", 8, True, [Frame("u", None, 0)]), Animation("a", "x", 8, True, [Frame("u", None, 101)]),
                Animation("a", "x", 8, True, [Frame("u")] * 257)):
        with pytest.raises(ValueError):
            validate_animation(bad)


def test_temps_boucle_et_arret():
    a = _anim(1, 2, 1, fps=10)  # 4 tops de 100 ms
    assert total_ticks(a) == 4
    assert [frame_index_at(a, t) for t in (0, 99, 100, 299, 300, 399, 400, 500)] == [0, 0, 1, 1, 2, 2, 0, 1]
    once = _anim(1, 2, 1, fps=10, loop=False)
    assert frame_index_at(once, 10_000) == 2 and frame_index_at(_anim(), 0) == -1


# ------------------------------------------------------------------ planches
def _img(w, h, color):
    return Image.new("RGBA", (w, h), color)


def test_planche_alignement_des_pivots_et_decoupe(tmp_path):
    frames = [FrameImage(_img(4, 6, (255, 0, 0, 255)), (2, 5)), FrameImage(_img(6, 4, (0, 255, 0, 255)), (3, 3))]
    sheet, meta = build_sheet(frames, columns=2)
    assert meta["cell"] == [6, 6] and meta["pivot"] == [3, 5] and sheet.size == (12, 6)
    assert sheet.getpixel((1, 5)) == (255, 0, 0, 255)       # pied de la 1re image : pivot (3,5) - (2,5) -> x=1
    assert sheet.getpixel((0, 5)) == (0, 0, 0, 0)
    assert sheet.getpixel((6, 2)) == (0, 255, 0, 255)       # 2e image : pivot aligné sur (3,5) de la case 2
    assert sheet.getpixel((6, 1)) == (0, 0, 0, 0)
    sheet.save(tmp_path / "s.png")
    cells = slice_sheet(tmp_path / "s.png", 6, 6)
    assert len(cells) == 2 and cells[0].getpixel((1, 5)) == (255, 0, 0, 255)


def test_planche_refus(tmp_path):
    f = [FrameImage(_img(4, 4, (1, 1, 1, 255)), (0, 0))]
    with pytest.raises(SheetError):
        build_sheet([], 1)
    with pytest.raises(SheetError):
        build_sheet(f, 3)
    with pytest.raises(SheetError):
        build_sheet([FrameImage(_img(512, 512, (1, 1, 1, 255)), (0, 0))] * 20, 20)  # > 8192
    _img(8, 8, (0, 0, 0, 0)).save(tmp_path / "v.png")
    for args in ((0, 4), (4, 600), (16, 16)):
        with pytest.raises(SheetError):
            slice_sheet(tmp_path / "v.png", *args)
    (tmp_path / "x.png").write_bytes(b"pas un png")
    with pytest.raises(SheetError):
        slice_sheet(tmp_path / "x.png", 4, 4)
    assert len(slice_sheet(tmp_path / "v.png", 4, 4)) == 1  # cases vides finales ignorées (il en reste une)
    assert len(slice_sheet(tmp_path / "v.png", 4, 4, count=3)) == 3


# ------------------------------------------------------------------ bibliothèque + projet
@pytest.fixture
def lib(tmp_path):
    cards = [card(f"porte_{n}", "ouvertures") for n in range(3)]
    kit = make_kit(tmp_path / "kit", cards)
    for c in cards:
        make_files(kit, c)
    lb = Library(tmp_path / "lib")
    import_kit(lb, kit)
    return lb


def test_animation_de_porte_aller_retour_planche(tmp_path, lib):
    assets = lib.list_assets()
    for k, a in enumerate(assets):  # trois images distinctes
        im = _img(a.width, a.height, (50 * k + 10, 0, 0, 255))
        import io
        buf = io.BytesIO()
        im.save(buf, format="PNG")
        lib.replace_image(a.uuid, buf.getvalue())
    anim = Animation("p", "porte", 6, False, [Frame(a.uuid, None, h) for a, h in zip(assets, (1, 2, 1))])
    meta = export_animation(lib, anim, tmp_path / "porte.png", columns=3)
    assert meta["columns"] == 3 and (tmp_path / "porte.json").is_file()
    sheet = Image.open(tmp_path / "porte.png")
    assert sheet.size == (3 * assets[0].width, assets[0].height)
    again = import_sheet(lib, tmp_path / "porte.png", "porte_importee")
    assert [f.hold for f in again.frames] == [1, 2, 1] and again.fps == 6 and again.loop is False
    new = [lib.get(f.asset_uuid) for f in again.frames]
    assert all(a.origin == "local" and a.category == "animations" for a in new)
    assert (new[0].pivot_x, new[0].pivot_y) == (assets[0].pivot_x, assets[0].pivot_y)
    first = Image.open(lib.abs_path(new[0].image_path)).convert("RGBA")
    assert first.getpixel((0, 0)) == (10, 0, 0, 255)


def test_import_planche_sans_json_demande_la_case_et_nettoie_en_cas_derreur(tmp_path, lib):
    _img(16, 8, (9, 9, 9, 255)).save(tmp_path / "nue.png")
    with pytest.raises(SheetError):
        import_sheet(lib, tmp_path / "nue.png", "x")
    before = lib.count()
    anim = import_sheet(lib, tmp_path / "nue.png", "x", cell=(8, 8))
    assert len(anim.frames) == 2 and lib.count() == before + 2
    assert (lib.get(anim.frames[0].asset_uuid).pivot_x, lib.get(anim.frames[0].asset_uuid).pivot_y) == (4, 7)


def test_projet_v3_animations_aller_retour_et_migration(tmp_path, lib):
    a = lib.list_assets()
    m = SceneModel()
    m.add(a[0].uuid, 1, 2)
    anim = Animation("anim1", "porte", 12, True, [Frame(a[1].uuid, None, 2), Frame(a[2].uuid, None, 1)])
    m.set_animations({"anim1": anim})
    path = tmp_path / "p.sbsproj"
    save_project(path, ProjectMeta(), m, lib)
    r = load_project(path, lib)
    assert r.animations["anim1"].frames[0].hold == 2 and r.animations["anim1"].fps == 12
    doc = json.loads(path.read_text(encoding="utf-8"))
    assert {a[1].uuid, a[2].uuid} <= set(doc["library_refs"])  # les images d'animation sont référencées
    # v2 sans animations : migration
    doc["schema_version"] = 2
    del doc["scenes"][0]["animations"]
    path.write_text(json.dumps(doc), encoding="utf-8")
    assert load_project(path, lib).animations == {}
    # animation invalide : refus clair
    doc["schema_version"] = 3
    doc["scenes"][0]["animations"] = [{"id": "z", "name": "x", "fps": 0, "loop": True, "frames": []}]
    path.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(ProjectError):
        load_project(path, lib)
