import pytest

pytest.importorskip("PySide6")
from PySide6.QtCore import QEvent, QMimeData, QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from sbs.canvas.mime import ASSET_MIME
from sbs.canvas.scene import CanvasScene
from sbs.canvas.view import ZOOM_LEVELS, CanvasView
from sbs.domain.scene import SceneModel
from sbs.services.kit_importer import import_kit
from sbs.services.library import Library
from tests.unit.test_kit_importer import card, make_files, make_kit


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def env(qapp, tmp_path):
    cards = [card("mur_a")]  # sprite 16×20, pivot (3, 17)
    kit = make_kit(tmp_path / "kit", cards)
    make_files(kit, cards[0])
    lib = Library(tmp_path / "lib")
    import_kit(lib, kit)
    asset = lib.list_assets()[0]
    model = SceneModel()
    scene = CanvasScene(model, lib)
    view = CanvasView(scene)
    view.resize(800, 600)
    view.show()
    qapp.processEvents()
    yield model, scene, view, asset
    view.close()


def _send(view, kind, scene_pt, button=Qt.MouseButton.LeftButton, buttons=None):
    p = QPointF(view.mapFromScene(QPointF(*scene_pt)))
    ev = QMouseEvent(kind, p, p, button, buttons if buttons is not None else button,
                     Qt.KeyboardModifier.NoModifier)
    QApplication.sendEvent(view.viewport(), ev)


def test_ajout_place_le_pivot_au_pixel(env):
    model, scene, view, asset = env
    inst = scene.add_asset(asset.uuid, 100, 50)
    item = scene.items_by_id[inst.id]
    assert (item.pos().x(), item.pos().y()) == (100 - 3, 50 - 17)
    assert item.pivot_position() == (100, 50)
    assert scene.add_asset("inconnu", 0, 0) is None  # rien d'ajouté
    assert len(model) == 1


def test_deplacement_souris_aligne_sur_pixels_entiers(env):
    model, scene, view, asset = env
    inst = scene.add_asset(asset.uuid, 0, 0)
    start = (0 - 3 + 8, 0 - 17 + 10)  # un point opaque du sprite
    _send(view, QEvent.Type.MouseButtonPress, start)
    _send(view, QEvent.Type.MouseMove, (start[0] + 25, start[1] + 12), Qt.MouseButton.NoButton,
          Qt.MouseButton.LeftButton)
    _send(view, QEvent.Type.MouseButtonRelease, (start[0] + 25, start[1] + 12),
          buttons=Qt.MouseButton.NoButton)
    m = model.get(inst.id)
    assert isinstance(m.x, int) and isinstance(m.y, int)
    assert (m.x, m.y) != (0, 0)
    item = scene.items_by_id[inst.id]
    assert item.pos().x() == round(item.pos().x()) and item.pos().y() == round(item.pos().y())


def test_fleches_et_suppression(env):
    model, scene, view, asset = env
    inst = scene.add_asset(asset.uuid, 10, 10)  # sélectionné à l'ajout
    view.setFocus()
    QTest.keyClick(view, Qt.Key.Key_Right)
    QTest.keyClick(view, Qt.Key.Key_Down, Qt.KeyboardModifier.ShiftModifier)
    assert (model.get(inst.id).x, model.get(inst.id).y) == (11, 18)
    assert scene.remove_selected() == 1
    assert len(model) == 0 and not scene.items_by_id


def test_ordre_de_recouvrement_suit_la_profondeur(env):
    model, scene, view, asset = env
    a = scene.add_asset(asset.uuid, 0, 10)
    b = scene.add_asset(asset.uuid, 0, 90)
    za, zb = scene.items_by_id[a.id].zValue(), scene.items_by_id[b.id].zValue()
    assert zb > za
    model.set_z_manual(a.id, 1)
    scene.refresh_z()
    assert scene.items_by_id[a.id].zValue() > scene.items_by_id[b.id].zValue()


def test_zoom_par_paliers_pixels_nets(env):
    model, scene, view, asset = env
    view.set_zoom_index(0)
    assert view.zoom == ZOOM_LEVELS[0]
    for _ in range(50):
        view.zoom_in()
    assert view.zoom == ZOOM_LEVELS[-1]
    assert view.transform().m11() == pytest.approx(ZOOM_LEVELS[-1])
    view.zoom_reset()
    assert view.transform().m11() == pytest.approx(2.0)


def test_depot_depuis_la_bibliotheque(env):
    model, scene, view, asset = env
    mime = QMimeData()
    mime.setData(ASSET_MIME, asset.uuid.encode())
    inst = view.handle_drop(mime, QPointF(40.4, 60.6))
    assert (inst.x, inst.y) == (40, 61)
    assert view.handle_drop(QMimeData(), QPointF(0, 0)) is None  # autre contenu : ignoré


def test_image_manquante_donne_un_repere_sans_planter(env, tmp_path):
    model, scene, view, asset = env
    scene.library.abs_path(asset.image_path).unlink()
    scene.pixmaps._cache.clear()
    inst = scene.add_asset(asset.uuid, 5, 5)
    assert inst is not None and not scene.items_by_id[inst.id].pixmap().isNull()
