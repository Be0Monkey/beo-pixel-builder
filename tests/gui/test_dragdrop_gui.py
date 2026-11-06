"""Glisser un module de la bibliothèque (à gauche) vers l'espace de travail : chaîne complète
(début du glisser côté liste -> événements d'entrée/dépôt reçus par la vue -> objet posé)."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent
from PySide6.QtWidgets import QApplication

from sbs.canvas.mime import ASSET_MIME
from sbs.services.kit_importer import import_kit
from sbs.services.library import Library
from sbs.services.preferences import Preferences
from sbs.ui.main_window import MainWindow
from tests.unit.test_kit_importer import card, make_files, make_kit


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def win(qapp, tmp_path):
    cards = [card("mur_a"), card("mur_b")]
    kit = make_kit(tmp_path / "kit", cards)
    for c in cards:
        make_files(kit, c)
    lib = Library(tmp_path / "lib")
    import_kit(lib, kit)
    w = MainWindow(Preferences(tmp_path / "p.json"), lib)
    w.resize(1200, 800)
    w.show()
    w.library_panel.refresh()
    qapp.processEvents()
    yield w
    w.dirty = False
    w.close()


def test_la_liste_autorise_le_glisser_et_fournit_le_module(win):
    lst = win.library_panel.list
    assert lst.dragEnabled()  # régression : setMovement(Static) l'éteignait
    assert lst.count() == 2
    lst.setCurrentRow(1)
    expected = lst.currentItem().data(Qt.ItemDataRole.UserRole)
    mime = lst.model().mimeData(lst.selectedIndexes())  # ce que Qt envoie au début du glisser
    assert mime is not None and mime.hasFormat(ASSET_MIME)
    assert bytes(mime.data(ASSET_MIME)).decode() == expected
    assert ASSET_MIME in lst.model().mimeTypes()


def test_depot_reel_sur_la_vue_pose_l_objet_sous_la_souris(win, qapp):
    lst, view = win.library_panel.list, win.canvas
    lst.setCurrentRow(0)
    asset_uuid = lst.currentItem().data(Qt.ItemDataRole.UserRole)
    mime = lst.model().mimeData(lst.selectedIndexes())
    vp = view.viewport()
    pos = QPoint(vp.width() // 2 + 40, vp.height() // 2 + 20)
    copy, btn, mod = Qt.DropAction.CopyAction, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier
    enter = QDragEnterEvent(pos, copy, mime, btn, mod)
    qapp.sendEvent(vp, enter)
    assert enter.isAccepted()  # le curseur « interdit » ne s'affiche pas
    move = QDragMoveEvent(pos, copy, mime, btn, mod)
    qapp.sendEvent(vp, move)
    assert move.isAccepted()
    before = len(win.scene_model)
    drop = QDropEvent(QPointF(pos), copy, mime, btn, mod)
    qapp.sendEvent(vp, drop)
    assert drop.isAccepted() and len(win.scene_model) == before + 1
    inst = win.scene_model.all()[-1]
    target = view.mapToScene(pos)
    assert inst.asset_uuid == asset_uuid and (inst.x, inst.y) == (round(target.x()), round(target.y()))
    win.canvas_scene.undo()  # annulable comme le reste
    assert len(win.scene_model) == before


def test_un_autre_contenu_est_refuse(win, qapp):
    from PySide6.QtCore import QMimeData
    m = QMimeData()
    m.setText("bonjour")
    vp = win.canvas.viewport()
    ev = QDragEnterEvent(QPoint(10, 10), Qt.DropAction.CopyAction, m, Qt.MouseButton.LeftButton,
                         Qt.KeyboardModifier.NoModifier)
    qapp.sendEvent(vp, ev)
    assert not ev.isAccepted()
