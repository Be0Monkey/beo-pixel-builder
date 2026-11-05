import pytest

pytest.importorskip("PySide6")
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

from sbs.domain import structure as S
from tests.gui.test_canvas import env, qapp  # noqa: F401  (fixtures)


def _click(view, pt, double=False):
    from PySide6.QtCore import QEvent
    p = QPointF(view.mapFromScene(QPointF(*pt)))
    kinds = [QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonRelease]
    if double:
        kinds = [QEvent.Type.MouseButtonDblClick, QEvent.Type.MouseButtonRelease]
    for k in kinds:
        btns = Qt.MouseButton.LeftButton if k != QEvent.Type.MouseButtonRelease else Qt.MouseButton.NoButton
        ev = QMouseEvent(k, p, p, Qt.MouseButton.LeftButton, btns, Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(view.viewport(), ev)


def _three(scene, asset):
    a = scene.add_asset(asset.uuid, 0, 0)
    b = scene.add_asset(asset.uuid, 40, 0)
    c = scene.add_asset(asset.uuid, 80, 0)
    return a, b, c


def test_t03_grouper_degrouper_et_annulation(env):
    model, scene, view, asset = env
    a, b, c = _three(scene, asset)
    scene.select_ids([a.id, b.id])
    assert scene.group_selected() is None
    gid = model.get(a.id).group_id
    assert gid and model.get(b.id).group_id == gid and model.get(c.id).group_id is None
    scene.undo()
    assert model.get(a.id).group_id is None and not model.groups
    scene.redo()
    assert model.get(a.id).group_id == gid
    scene.select_ids([a.id])
    scene.select_unit_of(a.id)
    assert set(scene.selected_ids()) == {a.id, b.id}  # un clic = tout le groupe
    assert scene.ungroup_selected() == 1
    assert model.get(a.id).group_id is None and not model.groups
    scene.undo()
    assert model.get(a.id).group_id == gid


def test_grouper_exige_deux_unites(env):
    model, scene, view, asset = env
    a, b, c = _three(scene, asset)
    scene.select_ids([a.id])
    assert scene.group_selected() is not None


def test_clic_souris_selectionne_le_groupe_et_double_clic_entre(env):
    model, scene, view, asset = env
    a, b, c = _three(scene, asset)
    scene.select_ids([a.id, b.id])
    scene.group_selected()
    scene.clearSelection()
    _click(view, (0 + 2, 0 - 5))  # sur a (pivot (0,0), sprite au-dessus)
    assert set(scene.selected_ids()) == {a.id, b.id}
    _click(view, (0 + 2, 0 - 5), double=True)
    assert scene.entered_group == model.get(a.id).group_id
    _click(view, (0 + 2, 0 - 5))
    assert scene.selected_ids() == [a.id]  # dans le groupe : élément seul
    scene.exit_group()
    assert scene.entered_group is None


def test_groupes_imbriques_max_3_niveaux(env):
    model, scene, view, asset = env
    items = [scene.add_asset(asset.uuid, 40 * n, 0) for n in range(5)]
    ids = [i.id for i in items]
    scene.select_ids(ids[:2]); assert scene.group_selected() is None          # niveau 1
    scene.select_ids(ids[:3]); assert scene.group_selected() is None          # niveau 2
    scene.select_ids(ids[:4]); assert scene.group_selected() is None          # niveau 3
    scene.select_ids(ids[:5]); assert scene.group_selected() is not None      # niveau 4 refusé
    assert len(model.groups) == 3


def test_suppression_nettoie_les_groupes_vides_et_annule(env):
    model, scene, view, asset = env
    a, b, c = _three(scene, asset)
    scene.select_ids([a.id, b.id]); scene.group_selected()
    scene.select_ids([a.id, b.id]); scene.remove_selected()
    assert not model.groups
    scene.undo()
    assert len(model.groups) == 1 and model.get(a.id).group_id


def test_copier_coller_conserve_les_groupes(env):
    model, scene, view, asset = env
    a, b, c = _three(scene, asset)
    scene.select_ids([a.id, b.id]); scene.group_selected()
    text = scene.copy_payload()
    scene.paste_payload(text, 16, 16)
    assert len(model.groups) == 2
    pasted = [i for i in model.all() if i.id not in (a.id, b.id, c.id)]
    assert len(pasted) == 2 and pasted[0].group_id == pasted[1].group_id != model.get(a.id).group_id


def test_s02_etages_masquer_verrouiller_deplacer(env):
    model, scene, view, asset = env
    scene.edit_structure("Ajouter", lambda f: (S.add_floor(f, "Étage 1"), S.add_floor(f, "Toit")))
    rdc, e1, toit = [f.id for f in model.floors][:3]
    lay = lambda fid: model.find_floor(fid).layers[0].id
    made = {}
    for name, fid in (("rdc", rdc), ("e1", e1), ("toit", toit)):
        scene.set_active_target(fid, lay(fid))
        made[name] = scene.add_asset(asset.uuid, 10, 100)
    scene.edit_structure("Masquer toit", lambda f: S.set_visible(f, toit, None, False))
    scene.edit_structure("Verrouiller RDC", lambda f: S.set_locked(f, rdc, None, True))
    assert scene.items_by_id[made["toit"].id].isVisible() is False
    assert not scene.items_by_id[made["rdc"].id].editable
    n = scene.move_content(e1, None, 0, -32)
    assert n == 1 and model.get(made["e1"].id).y == 68
    scene.move_content(rdc, None, 5, 5)  # verrouillé : rien ne bouge
    assert (model.get(made["rdc"].id).x, model.get(made["rdc"].id).y) == (10, 100)
    scene.undo(); scene.undo(); scene.undo(); scene.undo()  # déplacement, verrou, masquage, ajout étages
    assert len(model.floors) == 1 or model.get(made["e1"].id).y == 100


def test_affecter_calque_dupliquer_etage_et_annuler(env):
    model, scene, view, asset = env
    a, b, c = _three(scene, asset)
    scene.edit_structure("Ajouter calque", lambda f: S.add_layer(f, model.floors[0].id, "Détails"))
    new_layer = model.floors[0].layers[-1].id
    scene.select_ids([a.id])
    assert scene.assign_selection_to_layer(model.floors[0].id, new_layer) == 1
    assert model.get(a.id).layer_id == new_layer
    scene.undo()
    assert model.get(a.id).layer_id != new_layer
    before = len(model)
    new_floor = scene.duplicate_floor(model.floors[0].id)
    assert new_floor and len(model) == before + 3
    scene.undo()
    assert len(model) == before


def test_glisser_a_la_souris_aimante_sur_la_grille(env):
    model, scene, view, asset = env
    scene.snap.grid = True
    scene.snap.grid_size = 32
    a = scene.add_asset(asset.uuid, 100, 100)
    scene.select_ids([a.id])
    from PySide6.QtCore import QEvent
    def ev(kind, pt, btns):
        p = QPointF(view.mapFromScene(QPointF(*pt)))
        QApplication.sendEvent(view.viewport(), QMouseEvent(
            kind, p, p, Qt.MouseButton.LeftButton, btns, Qt.KeyboardModifier.NoModifier))
    ev(QEvent.Type.MouseButtonPress, (102, 95), Qt.MouseButton.LeftButton)
    ev(QEvent.Type.MouseMove, (128, 95), Qt.MouseButton.LeftButton)  # +26 -> pivot 126, grille 128
    ev(QEvent.Type.MouseButtonRelease, (128, 95), Qt.MouseButton.NoButton)
    assert model.get(a.id).x == 128 and model.get(a.id).y == 96
    scene.undo()
    assert model.get(a.id).x == 100
