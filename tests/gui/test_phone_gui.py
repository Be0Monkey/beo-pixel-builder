"""Échanges avec le téléphone dans la vraie fenêtre (le fichier de test vient du vrai Atelier Pixel)."""

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication

from sbs.services.library import Library
from sbs.services.preferences import Preferences
from sbs.ui.main_window import MainWindow

SCENE = Path(__file__).resolve().parents[1] / "data" / "phone_scene_from_web.json"


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def win(qapp, tmp_path, monkeypatch):
    for name in ("critical", "information", "warning"):
        monkeypatch.setattr(f"sbs.ui.main_window.QMessageBox.{name}", lambda *a, **k: None)
    w = MainWindow(Preferences(tmp_path / "p.json"), Library(tmp_path / "lib"))
    w.show()
    yield w
    w.dirty = False
    w.close()


def test_scene_from_web_app_is_imported(win, monkeypatch):
    monkeypatch.setattr("sbs.ui.main_window.QFileDialog.getOpenFileName", lambda *a, **k: (str(SCENE), ""))
    assert win.import_phone_scene() is True
    assert len(win.library.list_assets()) == 2
    assert len(win.scene_model.draw_instances()) == 3  # même nombre d'objets que dans la scène posée sur le téléphone


def test_library_export_from_window(win, tmp_path, monkeypatch):
    out = tmp_path / "lib.json"
    monkeypatch.setattr("sbs.ui.main_window.QFileDialog.getSaveFileName", lambda *a, **k: (str(out), ""))
    win.export_phone_library()
    assert out.exists()
