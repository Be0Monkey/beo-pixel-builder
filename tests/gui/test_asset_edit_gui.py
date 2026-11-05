import pytest

pytest.importorskip("PySide6")
from sbs.domain.asset import Anchor
from tests.gui.test_canvas import env, qapp  # noqa: F401


def test_15_fenetres_detacher_une_puis_modifier_la_source(env):
    model, scene, view, asset = env
    ids = [scene.add_asset(asset.uuid, 40 * n, 100).id for n in range(15)]
    assert scene.count_uses(asset.uuid) == 15
    # 1) détacher UNE instance et lui donner un autre pivot
    scene.select_ids([ids[0]])
    assert scene.edit_geometry("instance", (1, 1), [Anchor("test", 2, 2)]) is None
    clone_uuid = model.get(ids[0]).asset_uuid
    assert clone_uuid != asset.uuid and scene.count_uses(asset.uuid) == 14
    assert scene.library.get(clone_uuid).pivot_x == 1
    # 2) modifier la SOURCE : les 14 autres suivent, l'instance détachée non
    scene.select_ids([ids[1]])
    assert scene.edit_geometry("source", (8, 20), []) is None
    assert scene.library.get(asset.uuid).pivot_x == 8
    assert scene.library.get(clone_uuid).pivot_x == 1 and scene.library.get(clone_uuid).anchors
    assert scene.items_by_id[ids[1]].pivot_position() == (model.get(ids[1]).x, model.get(ids[1]).y)
    # 3) annulations : retour exact
    scene.undo()
    assert scene.library.get(asset.uuid).pivot_x == 3
    scene.undo()
    assert model.get(ids[0]).asset_uuid == asset.uuid and scene.count_uses(asset.uuid) == 15
    scene.redo()
    assert model.get(ids[0]).asset_uuid == clone_uuid


def test_modification_mixte_refusee_et_valeurs_invalides(env):
    model, scene, view, asset = env
    a = scene.add_asset(asset.uuid, 0, 0)
    scene.select_ids([])
    assert scene.edit_geometry("source", (1, 1), []) is not None
    scene.select_ids([a.id])
    before = len(scene.history._stack)
    assert scene.edit_geometry("source", (999, 1), []) is not None  # hors image
    assert scene.edit_geometry("inconnue", (1, 1), []) is not None
    assert len(scene.history._stack) == before


def test_changer_de_variante_garde_position_et_annule(env):
    model, scene, view, asset = env
    a = scene.add_asset(asset.uuid, 50, 60)
    b = scene.add_asset(asset.uuid, 90, 60)
    scene.select_ids([a.id, b.id])
    assert scene.set_variant_selected("gres") == 2
    assert model.get(a.id).variant == "gres" and (model.get(a.id).x, model.get(a.id).y) == (50, 60)
    assert scene.items_by_id[a.id].variant == "gres"
    assert scene.set_variant_selected("gres") == 0  # déjà fait
    assert scene.set_variant_selected("inexistante") == 0
    scene.undo()
    assert model.get(a.id).variant is None and scene.items_by_id[a.id].variant is None


def test_aimant_ancrages_pendant_le_glisser(env):
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtWidgets import QApplication
    model, scene, view, asset = env
    scene.library.update_geometry(asset.uuid, (3, 17), [Anchor("haut", 8, 0)])
    fixe = scene.add_asset(asset.uuid, 150, 100)   # ancrage « haut » en (155, 83)
    mobile = scene.add_asset(asset.uuid, 50, 100)  # ancrage à (55, 83)
    scene.snap.anchors = True
    scene.select_ids([mobile.id])

    def ev(kind, pt, btns):
        p = QPointF(view.mapFromScene(QPointF(*pt)))
        QApplication.sendEvent(view.viewport(), QMouseEvent(
            kind, p, p, Qt.MouseButton.LeftButton, btns, Qt.KeyboardModifier.NoModifier))
    ev(QEvent.Type.MouseButtonPress, (52, 95), Qt.MouseButton.LeftButton)
    ev(QEvent.Type.MouseMove, (150, 97), Qt.MouseButton.LeftButton)  # brut : +98, +2 -> ancrage (153, 85)
    ev(QEvent.Type.MouseButtonRelease, (150, 97), Qt.MouseButton.NoButton)
    got = model.get(mobile.id)
    assert (got.x, got.y) == (150, 100)  # ancrage tombé exactement sur (155, 83)
    assert model.get(fixe.id).x == 150


def test_selectionner_les_images_manquantes(env):
    model, scene, view, asset = env
    ok = scene.add_asset(asset.uuid, 0, 0)
    scene.library.abs_path(asset.image_path).unlink()
    assert scene.select_missing() == 1 and scene.selected_ids() == [ok.id]
