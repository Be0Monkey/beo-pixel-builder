"""J3 « dimensions libres » dans la vraie fenêtre : redimensionner (annulable) et couvrir une longueur."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication

from sbs.domain import repeat as R
from sbs.services.kit_importer import import_kit
from sbs.services.library import Library
from sbs.services.preferences import Preferences
from sbs.ui.main_window import MainWindow
from sbs.ui.repeat_dialog import RepeatDialog
from sbs.ui.resize_dialog import ResizeDialog
from tests.unit.test_kit_importer import card, make_files, make_kit


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def win(qapp, tmp_path, monkeypatch):
    for name in ("critical", "information", "warning"):
        monkeypatch.setattr(f"sbs.ui.main_window.QMessageBox.{name}", lambda *a, **k: None)
    cards = [card("mur_a"), card("mur_b")]
    kit = make_kit(tmp_path / "kit", cards)
    for c in cards:
        make_files(kit, c)  # images 16×20, pivot (3, 17)
    lib = Library(tmp_path / "lib")
    import_kit(lib, kit)
    w = MainWindow(Preferences(tmp_path / "p.json"), lib)
    w.show()
    yield w
    w.dirty = False
    w.close()


def test_redimensionner_la_selection_puis_annuler(win):
    sc, lib = win.canvas_scene, win.library
    a, b = lib.list_assets()
    i1, i2, i3 = sc.add_asset(a.uuid, 10, 20), sc.add_asset(a.uuid, 50, 20), sc.add_asset(b.uuid, 90, 20)
    sc.select_ids([i1.id, i2.id, i3.id])
    n, created = sc.resize_selected("up", 2)
    assert (n, created) == (3, 2)  # 2 modules sources -> 2 nouveaux modules, pas un par objet
    after = [win.scene_model.get(i.id) for i in (i1, i2, i3)]
    assert [(i.x, i.y) for i in after] == [(10, 20), (50, 20), (90, 20)]  # pivots inchangés
    assert after[0].asset_uuid == after[1].asset_uuid != a.uuid
    new = lib.get(after[0].asset_uuid)
    assert (new.width, new.height) == (32, 40) and new.name.endswith("×2")
    assert win.canvas_scene.items_by_id[i1.id].pixmap().width() == 32  # l'écran suit
    assert lib.count() == 4 and win.history.undo_name.startswith("Redimensionner")
    win.canvas_scene.undo()
    assert win.scene_model.get(i1.id).asset_uuid == a.uuid
    assert win.canvas_scene.items_by_id[i1.id].pixmap().width() == 16
    win.canvas_scene.redo()
    assert win.scene_model.get(i1.id).asset_uuid == after[0].asset_uuid


def test_redimensionner_refus_ne_laisse_rien(win):
    sc, lib = win.canvas_scene, win.library
    a, _ = lib.list_assets()
    i = sc.add_asset(a.uuid, 0, 0)
    sc.select_ids([i.id])
    before = lib.count()
    with pytest.raises(ValueError, match="divisible"):
        sc.resize_selected("down", 3)  # 16×20 n'est pas divisible par 3
    assert lib.count() == before and win.scene_model.get(i.id).asset_uuid == a.uuid
    sc.select_ids([])
    with pytest.raises(ValueError, match="Sélectionne"):
        sc.resize_selected("up", 2)


def test_dialogue_redimensionner_remplace_ou_cree_un_module(win):
    sc, lib = win.canvas_scene, win.library
    a, _ = lib.list_assets()
    i = sc.add_asset(a.uuid, 0, 0)
    sc.select_ids([i.id])
    dlg = ResizeDialog(sc, a.uuid, True)
    assert dlg.replace.isChecked() and "16×20 → 32×40" in dlg.info.text()
    dlg.factor.setCurrentIndex(dlg.factor.findText("÷3"))
    assert "divisible" in dlg.info.text()
    dlg.apply()  # refus : la boîte reste ouverte, aucun changement
    assert dlg.result() == 0 and lib.count() == 2
    dlg.factor.setCurrentIndex(dlg.factor.findText("×4"))
    dlg.apply()
    assert dlg.result() == 1 and win.scene_model.get(i.id).asset_uuid != a.uuid
    # sans sélection : seulement un module de plus dans la bibliothèque
    sc.select_ids([])
    dlg2 = ResizeDialog(sc, a.uuid, False)
    assert not dlg2.replace.isEnabled()
    dlg2.apply()
    assert dlg2.result() == 1 and "ajouté" in dlg2.result_text and lib.count() == 4


def test_repeter_pour_couvrir_une_largeur(win):
    sc, lib = win.canvas_scene, win.library
    a, _ = lib.list_assets()
    dlg = RepeatDialog(sc, a.uuid, None, (0, 40))
    dlg.mode.setCurrentIndex(dlg.mode.findData("cover"))
    assert dlg.piece.value() == 16  # largeur du module proposée
    dlg.length.setValue(100)
    assert "7 objet(s)" in dlg.info.text() and "112 px couverts sur 100" in dlg.info.text()
    dlg.fit.setCurrentIndex(dlg.fit.findData("exact"))
    assert "100 px couverts sur 100" in dlg.info.text()
    assert dlg.place() is None
    xs = sorted(i.x for i in win.scene_model.all())
    assert len(xs) == 7 and xs[0] == 0 and xs[-1] == 84  # dernière pièce : 84 + 16 = 100 pile
    assert all(i.y == 40 for i in win.scene_model.all())
    win.canvas_scene.undo()
    assert len(win.scene_model) == 0
    dlg.axis.setCurrentIndex(dlg.axis.findData("v"))
    assert dlg.piece.value() == 20  # hauteur du module en sens vertical
    dlg.length.setValue(0 + 60)
    dlg.fit.setCurrentIndex(dlg.fit.findData("within"))
    assert dlg.positions() == [(0, 40), (0, 60), (0, 80)]
    dlg.close()


def test_mur_en_perspective_pose_annule_et_ordre(win):
    sc, lib = win.canvas_scene, win.library
    a, _ = lib.list_assets()  # 16×20
    pieces = R.perspective_wall((0, 100), 5, 16, -50, 50)
    assert sc.place_wall(a.uuid, pieces) is None
    insts = win.scene_model.all()
    assert len(insts) == 5
    assert [(i.x, i.y) for i in insts] == [(p.x, p.y) for p in pieces]
    for p, i in zip(pieces, insts):
        assert lib.get(i.asset_uuid).width == p.width
    order = [i.id for i in win.scene_model.draw_instances()]
    assert order[-1] == insts[0].id  # la plus proche (en bas) est dessinée devant
    win.canvas_scene.undo()
    assert len(win.scene_model) == 0


def test_dialogue_mur_perspective(win):
    sc, lib = win.canvas_scene, win.library
    a, _ = lib.list_assets()
    dlg = RepeatDialog(sc, a.uuid, None, (0, 60))
    dlg.mode.setCurrentIndex(dlg.mode.findData("persp"))
    dlg.wall_count.setValue(6)
    dlg.slope.setValue(-50)
    dlg.last_pct.setValue(40)
    assert "6 objet(s)" in dlg.info.text() and "100 % à 40 %" in dlg.info.text()
    assert dlg.place() is None and len(win.scene_model) == 6
    dlg.close()
