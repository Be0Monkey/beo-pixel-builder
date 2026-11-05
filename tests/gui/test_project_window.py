import pytest

pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication, QMessageBox

from sbs.services.kit_importer import import_kit
from sbs.services.library import Library
from sbs.services.preferences import Preferences
from sbs.ui.main_window import MainWindow
from tests.unit.test_kit_importer import card, make_files, make_kit


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def win(qapp, tmp_path, monkeypatch):
    for name in ("critical", "information", "warning"):
        monkeypatch.setattr(f"sbs.ui.main_window.QMessageBox.{name}", lambda *a, **k: None)
    cards = [card("mur_a")]
    kit = make_kit(tmp_path / "kit", cards)
    make_files(kit, cards[0])
    lib = Library(tmp_path / "lib")
    import_kit(lib, kit)
    w = MainWindow(Preferences(tmp_path / "p.json"), lib)
    w.show()
    w._asset = lib.list_assets()[0]
    yield w
    w.dirty = False
    w.close()


def test_modifier_puis_enregistrer_puis_rouvrir(win, tmp_path):
    a = win._asset
    assert not win.dirty and win.windowTitle().startswith("Sans titre")
    i1 = win.canvas_scene.add_asset(a.uuid, 10, 10)
    i2 = win.canvas_scene.add_asset(a.uuid, 10, 10)
    assert win.dirty and "*" in win.windowTitle()
    win.canvas_scene.clearSelection()
    win.canvas_scene.items_by_id[i1.id].setSelected(True)
    win.canvas_scene.shift_z_selected(1)  # i1 forcé devant
    path = tmp_path / "Mon dossier é" / "maison.sbsproj"
    assert win.save_to(path) and not win.dirty and win.windowTitle().startswith("maison")
    order_before = win.scene_model.draw_order()

    win.new_project()
    assert len(win.scene_model) == 0 and not win.canvas_scene.items_by_id

    assert win.open_path(path)
    assert [i.id for i in win.scene_model.all()] == [i1.id, i2.id]
    assert win.scene_model.draw_order() == order_before
    assert win.scene_model.get(i1.id).z_manual == 1
    assert len(win.canvas_scene.items_by_id) == 2 and not win.dirty
    z = {k: v.zValue() for k, v in win.canvas_scene.items_by_id.items()}
    assert z[i1.id] > z[i2.id]


def test_deplacement_souris_ou_clavier_est_enregistre(win, tmp_path):
    a = win._asset
    inst = win.canvas_scene.add_asset(a.uuid, 0, 0)
    win.canvas.setFocus()
    win.canvas_scene.move_selected(5, 7)
    path = tmp_path / "p.sbsproj"
    win.save_to(path)
    win.new_project()
    win.open_path(path)
    m = win.scene_model.get(inst.id)
    assert (m.x, m.y) == (5, 7)


def test_ouverture_d_un_fichier_abime_ne_touche_pas_au_projet_en_cours(win, tmp_path):
    a = win._asset
    inst = win.canvas_scene.add_asset(a.uuid, 3, 4)
    bad = tmp_path / "abime.sbsproj"
    bad.write_text("{pas du json", encoding="utf-8")
    assert win.open_path(bad) is False
    assert [i.id for i in win.scene_model.all()] == [inst.id]
    assert win.dirty  # toujours modifié, rien n'a été perdu


def test_confirmation_avant_de_perdre_des_modifications(win, monkeypatch):
    win.canvas_scene.add_asset(win._asset.uuid, 1, 1)
    monkeypatch.setattr(
        "sbs.ui.main_window.QMessageBox.question", lambda *a, **k: QMessageBox.StandardButton.Cancel
    )
    assert win.new_project() is False and len(win.scene_model) == 1
    monkeypatch.setattr(
        "sbs.ui.main_window.QMessageBox.question", lambda *a, **k: QMessageBox.StandardButton.Discard
    )
    assert win.new_project() is True and len(win.scene_model) == 0


def test_echec_d_ecriture_signale_et_garde_les_modifications(win, tmp_path, monkeypatch):
    win.canvas_scene.add_asset(win._asset.uuid, 1, 1)
    monkeypatch.setattr("sbs.services.atomic.os.replace",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("plein")))
    assert win.save_to(tmp_path / "x.sbsproj") is False
    assert win.dirty


def test_copier_coller_via_la_fenetre(win):
    a = win._asset
    win.canvas_scene.add_asset(a.uuid, 10, 10)
    assert win.copy_selection()
    assert win.paste() == 1 and win.paste() == 1  # deux collages : décalés de 8 puis 16
    xs = sorted(i.x for i in win.scene_model.all())
    assert xs == [10, 18, 26]
    assert win.cut_selection() and len(win.scene_model) == 2


def test_presse_papiers_etranger_ignore(win):
    from PySide6.QtCore import QMimeData
    mime = QMimeData()
    mime.setText("du texte quelconque")
    QApplication.clipboard().setMimeData(mime)
    assert win.paste() == 0 and len(win.scene_model) == 0


def test_export_depuis_la_fenetre(win, tmp_path):
    from PIL import Image
    a = win._asset
    win.canvas_scene.add_asset(a.uuid, 0, 0)
    out = tmp_path / "sortie é.png"
    assert win.export_to(out, 2)
    im = Image.open(out)
    assert im.mode == "RGBA" and im.size == (32, 40)
    assert win.dirty  # exporter n'enregistre pas et ne change pas le document


def test_export_scene_vide_refuse_sans_fichier(win, tmp_path):
    assert win.export_to(tmp_path / "vide.png") is False
    assert not (tmp_path / "vide.png").exists()


def test_annuler_retablir_dans_la_fenetre(win):
    a = win._asset
    assert not win.act_undo.isEnabled()
    win.canvas_scene.add_asset(a.uuid, 5, 5)
    assert win.act_undo.isEnabled() and "Ajouter" in win.act_undo.text()
    win.act_undo.trigger()
    assert len(win.scene_model) == 0 and not win.act_undo.isEnabled()
    assert win.act_redo.isEnabled() and "Ajouter" in win.act_redo.text()
    win.act_redo.trigger()
    assert len(win.scene_model) == 1


def test_annuler_jusqu_a_l_etat_enregistre_enleve_l_etoile(win, tmp_path):
    a = win._asset
    win.canvas_scene.add_asset(a.uuid, 5, 5)
    win.save_to(tmp_path / "p.sbsproj")
    assert not win.dirty and "*" not in win.windowTitle()
    win.canvas_scene.move_selected(3, 3)
    assert win.dirty and "*" in win.windowTitle()
    win.canvas_scene.undo()
    assert not win.dirty and "*" not in win.windowTitle()


def test_ouvrir_vide_l_historique(win, tmp_path):
    a = win._asset
    win.canvas_scene.add_asset(a.uuid, 5, 5)
    win.save_to(tmp_path / "p.sbsproj")
    win.canvas_scene.add_asset(a.uuid, 9, 9)
    win.open_path(tmp_path / "p.sbsproj")
    assert not win.act_undo.isEnabled() and not win.dirty and len(win.scene_model) == 1
