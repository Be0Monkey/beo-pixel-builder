import pytest

pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication

from sbs.services.library import Library
from sbs.services.preferences import Preferences
from sbs.ui.main_window import MainWindow


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_fenetre_s_ouvre(qapp, tmp_path):
    w = MainWindow(Preferences(tmp_path / "p.json"), Library(tmp_path / "lib"))
    w.show()
    assert w.windowTitle() == "Sprite Builder Studio"
    assert set(w.docks) == {"library", "properties", "floors"}
    w.close()


def test_disposition_enregistree_puis_restauree(qapp, tmp_path):
    path = tmp_path / "p.json"
    w = MainWindow(Preferences(path), Library(tmp_path / "lib"))
    w.show()
    w.docks["library"].hide()
    w.close()  # enregistre
    assert path.exists()
    w2 = MainWindow(Preferences(path), Library(tmp_path / "lib"))
    w2.show()
    assert not w2.docks["library"].isVisible()
    w2.reset_layout()
    assert w2.docks["library"].isVisible()  # jamais de panneau perdu
    w2.close()


def test_preferences_corrompues_ne_bloquent_pas_le_demarrage(qapp, tmp_path):
    path = tmp_path / "p.json"
    path.write_text("n'importe quoi", encoding="utf-8")
    w = MainWindow(Preferences(path), Library(tmp_path / "lib"))
    w.show()
    assert w.docks["library"].isVisible()
    w.close()
