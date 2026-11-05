import pytest

pytest.importorskip("PySide6")
from sbs.domain.animation import Animation, Frame
from sbs.ui.repeat_dialog import RepeatDialog, parse_points
from tests.gui.test_canvas import env, qapp  # noqa: F401


def test_repeter_en_ligne_un_geste_une_annulation(env):
    model, scene, view, asset = env
    pos = [(10 + 20 * i, 50) for i in range(10)]
    assert scene.show_preview(asset.uuid, None, pos) == 10 and len(model) == 0  # aperçu = rien dans le projet
    assert scene.place_repeated(asset.uuid, None, pos) is None
    assert len(model) == 10 and len(scene._ghosts) == 0 and len(scene.selected_ids()) == 10
    scene.undo()
    assert len(model) == 0
    scene.redo()
    assert len(model) == 10 and len(scene.history._stack) == 1


def test_repeter_groupe_et_erreurs(env):
    model, scene, view, asset = env
    assert scene.place_repeated(asset.uuid, None, [(0, 0), (20, 0)], group=True) is None
    gids = {i.group_id for i in model.all()}
    assert len(gids) == 1 and None not in gids and len(model.groups) == 1
    scene.undo()
    assert not model.groups and len(model) == 0
    assert scene.place_repeated("inconnu", None, [(0, 0)])
    assert scene.place_repeated(asset.uuid, None, [])
    assert scene.place_repeated(asset.uuid, "pas_une_variante", [(0, 0)])
    assert scene.place_repeated(asset.uuid, "gres", [(0, 0)]) is None


def test_dialogue_cloture_sur_courbe_avec_apercu(env):
    model, scene, view, asset = env
    dlg = RepeatDialog(scene, asset.uuid, None, (0, 0))
    dlg.mode.setCurrentIndex(dlg.mode.findData("path"))
    dlg.points.setPlainText("0, 0\n60, -40\n120, 0\n180, 40")
    dlg.smooth.setChecked(True)
    dlg.amount.setValue(16)
    pos = dlg.positions()
    assert pos[0] == (0, 0) and len(pos) > 10
    assert len(scene._ghosts) == len(pos) and len(model) == 0
    assert dlg.place() is None and len(model) == len(pos)
    assert len(scene._ghosts) == 0
    dlg.close()
    scene.undo()
    assert len(model) == 0


def test_dialogue_erreurs_et_grille(env):
    model, scene, view, asset = env
    dlg = RepeatDialog(scene, asset.uuid, None, (5, 5))
    dlg.mode.setCurrentIndex(dlg.mode.findData("grid"))
    dlg.cols.setValue(4); dlg.rows.setValue(3); dlg.sx.setValue(20); dlg.sy.setValue(10)
    assert len(dlg.positions()) == 12 and dlg.positions()[5] == (25, 15)
    dlg.mode.setCurrentIndex(dlg.mode.findData("path"))
    dlg.points.setPlainText("0, 0\nabc")
    assert dlg.place() and len(model) == 0 and not scene._ghosts
    with pytest.raises(ValueError):
        parse_points("1, 2, 3")
    dlg.close()


def test_points_depuis_la_selection(env):
    model, scene, view, asset = env
    ids = [scene.add_asset(asset.uuid, x, 10).id for x in (0, 40, 80)]
    scene.select_ids(ids)
    dlg = RepeatDialog(scene, asset.uuid, None, (0, 0))
    dlg.points_from_selection()
    assert parse_points(dlg.points.toPlainText()) == [(0, 10), (40, 10), (80, 10)]
    dlg.close()


def test_animations_annulables_et_validees(env):
    model, scene, view, asset = env
    anim = Animation("a1", "porte", 8, True, [Frame(asset.uuid, None, 2), Frame(asset.uuid, "gres", 1)])
    assert scene.set_animations({"a1": anim}) is None
    assert model.animations["a1"].frames[1].variant == "gres"
    scene.undo()
    assert model.animations == {}
    scene.redo()
    assert "a1" in model.animations
    bad = Animation("a2", "x", 99, True, [])
    assert scene.set_animations({"a2": bad}) and "a2" not in model.animations
