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
