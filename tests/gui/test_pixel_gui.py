import io

import pytest

pytest.importorskip("PySide6")
from PIL import Image
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest

from sbs.domain.pixel import PixelDoc
from sbs.domain.pixel_edit import PixelEditor
from sbs.services.pixel_io import load_doc, png_bytes
from sbs.ui.pixel_editor import PixelEditorDialog
from tests.gui.test_canvas import env, qapp  # noqa: F401


def _pixel(lib, uuid, xy=(0, 0)):
    return Image.open(io.BytesIO(lib.image_bytes(uuid))).convert("RGBA").getpixel(xy)


def _retouche(scene, asset):
    doc = load_doc(scene.library, asset.uuid)
    e = PixelEditor(doc)
    e.set_color((10, 200, 30, 255))
    e.begin(0, 0)
    e.end()
    return doc


def test_validation_corriger_un_toit_sans_toucher_une_autre_occurrence(env):
    model, scene, view, asset = env
    a = scene.add_asset(asset.uuid, 0, 0)
    b = scene.add_asset(asset.uuid, 40, 0)
    original = _pixel(scene.library, asset.uuid)
    scene.select_ids([a.id])
    err, uuid = scene.apply_pixels("instance", png_bytes(_retouche(scene, asset)))
    assert err is None and uuid != asset.uuid
    assert model.get(a.id).asset_uuid == uuid and model.get(b.id).asset_uuid == asset.uuid
    assert _pixel(scene.library, uuid) == (10, 200, 30, 255)
    assert _pixel(scene.library, asset.uuid) == original  # l'autre occurrence est intacte
    scene.undo()
    assert model.get(a.id).asset_uuid == asset.uuid


def test_toutes_les_utilisations_puis_annuler(env):
    model, scene, view, asset = env
    a = scene.add_asset(asset.uuid, 0, 0)
    b = scene.add_asset(asset.uuid, 40, 0)
    original = _pixel(scene.library, asset.uuid)
    scene.select_ids([a.id])
    pm_before = scene.pixmaps.get(scene.library.get(asset.uuid)).toImage().pixelColor(0, 0).getRgb()
    err, uuid = scene.apply_pixels("source", png_bytes(_retouche(scene, asset)))
    assert err is None and uuid == asset.uuid
    assert model.get(b.id).asset_uuid == asset.uuid and _pixel(scene.library, asset.uuid) == (10, 200, 30, 255)
    pm = scene.items_by_id[b.id].pixmap().toImage().pixelColor(0, 0).getRgb()
    assert pm[:3] == (10, 200, 30) and pm != pm_before  # l'affichage suit (cache invalidé)
    scene.undo()
    assert _pixel(scene.library, asset.uuid) == original
    assert scene.items_by_id[b.id].pixmap().toImage().pixelColor(0, 0).getRgb() == pm_before


def test_retouche_refusee_taille_changee_ou_selection_melangee(env):
    model, scene, view, asset = env
    a = scene.add_asset(asset.uuid, 0, 0)
    scene.select_ids([])
    assert scene.pixel_target()[0] is None
    scene.select_ids([a.id])
    err, _ = scene.apply_pixels("source", png_bytes(PixelDoc(3, 3)))
    assert err and "taille" in err
    assert scene.library.count() == 1  # aucune copie orpheline après l'échec
    err, _ = scene.apply_pixels("instance", png_bytes(PixelDoc(3, 3)))
    assert err and scene.library.count() == 1 and len(scene.history._stack) == 1


def test_fenetre_atelier_dessine_a_la_souris(qapp):
    editor = PixelEditor(PixelDoc(8, 8))
    editor.set_color((255, 0, 0, 255))
    dlg = PixelEditorDialog(editor)
    dlg.canvas.set_zoom(10)
    dlg.show()
    QTest.mousePress(dlg.canvas, Qt.MouseButton.LeftButton, pos=QPoint(25, 35))   # pixel (2, 3)
    QTest.mouseRelease(dlg.canvas, Qt.MouseButton.LeftButton, pos=QPoint(25, 35))
    assert editor.doc.get(editor.doc.active, 2, 3) == (255, 0, 0, 255) and editor.modified
    dlg.undo_btn.click()
    assert editor.doc.get(editor.doc.active, 2, 3) == (0, 0, 0, 0)
    dlg.set_tool("fill")
    assert editor.tool == "fill"
    dlg.close()
