import pytest

pytest.importorskip("PySide6")
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

from sbs.services.library import Library
from sbs.ui.library_panel import LibraryPanel
from tests.unit.test_kit_importer import card, make_files, make_kit


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_import_en_arriere_plan_puis_filtres(qapp, tmp_path, monkeypatch):
    cards = [card("mur_a"), card("mur_b"), card("arbre_chene", "vegetation")]
    kit = make_kit(tmp_path / "kit", cards)
    for c in cards:
        make_files(kit, c)
    # pas de boîte de dialogue bloquante pendant le test
    monkeypatch.setattr("sbs.ui.library_panel.QMessageBox.information", lambda *a, **k: None)
    monkeypatch.setattr("sbs.ui.library_panel.QMessageBox.warning", lambda *a, **k: None)

    panel = LibraryPanel(Library(tmp_path / "lib"))
    assert panel.list.count() == 0 and "vide" in panel.count_label.text()
    panel.start_import(kit)
    loop = QEventLoop()
    timer = QTimer()
    timer.setInterval(50)
    timer.timeout.connect(lambda: loop.quit() if panel._thread is None else None)
    timer.start()
    QTimer.singleShot(15000, loop.quit)
    loop.exec()
    timer.stop()
    assert panel._thread is None
    assert panel.list.count() == 3
    assert not panel.list.item(0).icon().isNull()  # miniature présente

    panel.search.setText("chene")
    assert panel.list.count() == 1
    panel.search.setText("")
    panel.category.setCurrentIndex(panel.category.findData("murs"))
    assert panel.list.count() == 2
