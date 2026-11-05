"""Démonstration de bout en bout (scénarios S01 et S04 de 05_Plan_de_tests.md) dans la vraie fenêtre :
import par lot -> assemblage -> groupe -> enregistrement -> fermeture -> réouverture dans une autre
fenêtre -> export PNG identique au pixel près ; ordre de recouvrement conservé après sauvegarde."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
from PIL import Image, ImageChops
from PySide6.QtWidgets import QApplication

from sbs.services.batch_import import import_images
from sbs.services.library import Library
from sbs.services.preferences import Preferences
from sbs.ui.main_window import MainWindow


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def world(qapp, tmp_path, monkeypatch):
    for name in ("critical", "information", "warning"):
        monkeypatch.setattr(f"sbs.ui.main_window.QMessageBox.{name}", lambda *a, **k: None)
        monkeypatch.setattr(f"sbs.ui.session_mixin.QMessageBox.{name}", lambda *a, **k: None)
    src = tmp_path / "sprites de la maison"
    src.mkdir()
    for n in range(10):
        Image.new("RGBA", (12 + 4 * (n % 4), 16 + 2 * n), (25 * n, 255 - 20 * n, 80, 255 if n % 3 else 170)).save(
            src / f"element {n}.png")
    lib = Library(tmp_path / "bibliothèque")
    report = import_images(lib, sorted(src.glob("*.png")))
    assert len(report.imported) == 10
    windows = []

    def make():
        w = MainWindow(Preferences(tmp_path / "data" / "preferences.json"), lib)
        w.show()
        windows.append(w)
        return w
    yield make, lib, tmp_path
    for w in windows:
        w.dirty = False
        w.close()


def _state(w):
    return [(i.asset_uuid, i.x, i.y, i.z_manual, i.floor_id, i.layer_id, i.group_id is not None)
            for i in w.scene_model.all()]


def _png(w, path):
    from sbs.services.exporter import export_png
    export_png(path, w.scene_model.draw_instances(), w.library)
    return Image.open(path).convert("RGBA")


def test_s01_maison_simple_de_bout_en_bout(world):
    make, lib, tmp = world
    w = make()
    assets = lib.list_assets()
    placed = []
    for n, a in enumerate(assets):  # 10 éléments assemblés au pixel près
        placed.append(w.canvas_scene.add_asset(a.uuid, 8 * n, 30 + 3 * (n % 4)))
    assert len(w.scene_model) == 10
    w.canvas_scene.select_ids([p.id for p in placed[:4]])
    assert w.group_selection()
    w.canvas_scene.select_ids([placed[9].id])
    w.canvas_scene.move_selected(5, -2)  # déplacement au clavier, annulable
    w.canvas_scene.undo()
    w.canvas_scene.redo()
    before_state = _state(w)
    before_png = _png(w, tmp / "avant.png")
    target = tmp / "ma maison é" / "maison.sbsproj"
    target.parent.mkdir()
    assert w.save_to(target) and not w.dirty
    assert w.backups.versions(w.meta.id) and not w.recovery.pending()

    w2 = make()  # « rouvrir » dans une session neuve
    assert w2.open_path(target)
    assert _state(w2) == before_state
    assert [i.id for i in w2.scene_model.draw_instances()] == [i.id for i in w.scene_model.draw_instances()]
    after_png = _png(w2, tmp / "apres.png")
    assert after_png.size == before_png.size
    assert ImageChops.difference(before_png, after_png).getbbox() is None  # 0 pixel de différence
    assert after_png.getchannel("A").getextrema()[0] == 0  # la transparence est conservée


def test_s04_perspective_3_4_ordre_apres_sauvegarde(world):
    make, lib, tmp = world
    w = make()
    tree, fence, hero = lib.list_assets()[:3]
    i_tree = w.canvas_scene.add_asset(tree.uuid, 40, 60)
    i_fence = w.canvas_scene.add_asset(fence.uuid, 30, 90)
    i_hero = w.canvas_scene.add_asset(hero.uuid, 35, 75)
    order = lambda win: [i.id for i in win.scene_model.draw_instances()]  # noqa: E731
    assert order(w) == [i_tree.id, i_hero.id, i_fence.id]  # auto : plus bas à l'écran = devant
    w.canvas_scene.select_ids([i_hero.id])
    w.canvas_scene.shift_z_selected(1)  # correction manuelle : le personnage passe devant la clôture
    assert order(w) == [i_tree.id, i_fence.id, i_hero.id]
    target = tmp / "perspective.sbsproj"
    assert w.save_to(target)
    w2 = make()
    assert w2.open_path(target)
    assert order(w2) == [i_tree.id, i_fence.id, i_hero.id]
    assert [i.z_manual for i in w2.scene_model.all()] == [i.z_manual for i in w.scene_model.all()]
