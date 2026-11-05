"""J7 : sauvegarde automatique, récupération après arrêt brutal, versions, options, raccourcis,
espaces de travail, import d'images, auto-test d'installation."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication, QMessageBox

from sbs.services.kit_importer import import_kit
from sbs.services.library import Library
from sbs.services.preferences import Preferences
from sbs.ui.main_window import MainWindow
from tests.unit.test_kit_importer import card, make_files, make_kit


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def env(qapp, tmp_path, monkeypatch):
    for name in ("critical", "information", "warning"):
        monkeypatch.setattr(f"sbs.ui.main_window.QMessageBox.{name}", lambda *a, **k: None)
        monkeypatch.setattr(f"sbs.ui.session_mixin.QMessageBox.{name}", lambda *a, **k: None)
    cards = [card("mur_a")]
    kit = make_kit(tmp_path / "kit", cards)
    make_files(kit, cards[0])
    lib = Library(tmp_path / "lib")
    import_kit(lib, kit)
    windows = []

    def make():
        w = MainWindow(Preferences(tmp_path / "data" / "preferences.json"), lib)
        w.show()
        windows.append(w)
        return w
    yield make, lib, tmp_path
    for w in windows:
        w.dirty = False
        w.close()


def _fill(w, lib, n=3):
    a = lib.list_assets()[0]
    for i in range(n):
        w.canvas_scene.add_asset(a.uuid, 10 * i, 10 * i)


def test_t12_arret_brutal_puis_recuperation(env):
    make, lib, tmp = env
    w1 = make()
    assert not w1.autosave_now()  # rien de modifié : pas de copie
    _fill(w1, lib, 3)
    assert w1.dirty and w1.autosave_now()
    # « crash » : w1 n'est jamais fermé proprement ; l'application redémarre
    w2 = make()
    asked = []
    w2._ask_recovery = lambda e: asked.append(e) or "recover"
    assert w2.offer_recovery() is True
    assert asked[0].name == w1.meta.name
    assert len(w2.scene_model) == 3 and w2.dirty and "*" in w2.windowTitle()
    target = tmp / "dossier é" / "recup.sbsproj"
    target.parent.mkdir()
    assert w2.save_to(target)
    assert not w2.recovery.pending()  # l'enregistrement efface la copie de secours
    assert w2.backups.versions(w2.meta.id)
    w1.recovery.clear(w1.meta.id)


def test_fermeture_normale_ne_laisse_pas_de_recuperation(env, monkeypatch):
    make, lib, _ = env
    w = make()
    _fill(w, lib)
    w.autosave_now()
    assert w.recovery.pending()
    monkeypatch.setattr("sbs.ui.main_window.QMessageBox.question",
                        lambda *a, **k: QMessageBox.StandardButton.Discard)
    w.close()
    assert not w.recovery.pending()


def test_choix_plus_tard_supprimer_et_copie_abimee(env):
    make, lib, _ = env
    w1 = make()
    _fill(w1, lib)
    w1.autosave_now()
    w2 = make()
    w2._ask_recovery = lambda e: "later"
    assert w2.offer_recovery() is False and w2.recovery.pending()  # conservée
    w2._ask_recovery = lambda e: "delete"
    assert w2.offer_recovery() is False and not w2.recovery.pending()  # supprimée
    # copie abîmée (coupure pendant l'écriture d'un autre outil) : mise de côté, pas de plantage
    w1.autosave_now()
    entry = w1.recovery.pending()[0]
    entry.file.write_text("{ceci n'est pas du json", encoding="utf-8")
    w3 = make()
    w3._ask_recovery = lambda e: "recover"
    assert w3.offer_recovery() is False
    assert not w3.recovery.pending() and list(entry.file.parent.glob("*.abimee"))
    assert len(w3.scene_model) == 0


def test_ouvrir_une_ancienne_version_ne_touche_pas_au_projet(env):
    make, lib, tmp = env
    w = make()
    target = tmp / "v.sbsproj"
    for n in (1, 2, 3):
        _fill(w, lib, 1)
        assert w.save_to(target)
    versions = w.backups.versions(w.meta.id)
    assert len(versions) == 3
    before = target.read_text(encoding="utf-8")
    oldest = versions[-1]
    assert w.open_version(oldest.path, oldest.created)
    assert len(w.scene_model) == 1 and w.dirty and w.path is None
    assert "version" in w.meta.name 
    assert target.read_text(encoding="utf-8") == before


def test_options_valides_refusees_et_persistantes(env):
    make, lib, tmp = env
    w = make()
    w.apply_options(5, 7, {})
    assert w._autosave_timer.isActive() and w._autosave_timer.interval() == 5 * 60_000
    assert w.backups.keep == 7
    w.apply_options(0, 7, {})
    assert not w._autosave_timer.isActive()
    for bad in ((-1, 5), (500, 5), (5, 0), (5, 1000)):
        with pytest.raises(ValueError):
            w.apply_options(bad[0], bad[1], {})
    assert Preferences(tmp / "data" / "preferences.json").get("autosave.minutes") == 0
    assert make().backups.keep == 7


def test_raccourcis_personnalises_conflits_et_persistance(env):
    make, lib, tmp = env
    w = make()
    copier = next(s for s, lab in w.shortcut_labels.items() if lab.endswith("Copier"))
    coller = next(s for s, lab in w.shortcut_labels.items() if lab.endswith("Coller"))
    assert w.shortcut_actions[copier].shortcut().toString() == "Ctrl+C"
    w.apply_options(2, 10, {copier: "Ctrl+Shift+K"})
    assert w.shortcut_actions[copier].shortcut().toString() == "Ctrl+Shift+K"
    with pytest.raises(ValueError, match="utilisé"):
        w.apply_options(2, 10, {copier: "Ctrl+V"})  # déjà pris par Coller
    assert w.shortcut_actions[copier].shortcut().toString() == "Ctrl+Shift+K"  # rien n'a changé
    assert w.shortcut_actions[coller].shortcut().toString() == "Ctrl+V"
    # rétablir défaut ; Rétablir garde ses deux raccourcis tant qu'il n'est pas modifié
    redo = "edit_redo"
    assert {s.toString() for s in w.shortcut_actions[redo].shortcuts()} == {"Ctrl+Y", "Ctrl+Shift+Z"}
    w.apply_options(2, 10, {copier: "Ctrl+Shift+K", redo: "Ctrl+Y"})
    assert len(w.shortcut_actions[redo].shortcuts()) == 2
    w2 = make()  # persistance
    assert w2.shortcut_actions[copier].shortcut().toString() == "Ctrl+Shift+K"
    w2.apply_options(2, 10, {copier: "Ctrl+C"})
    assert w2.shortcut_actions[copier].shortcut().toString() == "Ctrl+C" and w2.shortcut_overrides() == {}
    w2.apply_options(2, 10, {coller: ""})  # raccourci retiré
    assert w2.shortcut_actions[coller].shortcut().isEmpty()


def test_dialogue_options_lit_et_ecrit_les_valeurs(env):
    from sbs.ui.options_dialog import OptionsDialog
    make, lib, _ = env
    w = make()
    eff = w.effective_shortcuts()
    table = {s: (w.shortcut_labels[s], w.default_shortcuts[s], eff[s][0] if eff[s] else "")
             for s in w.shortcut_actions}
    dlg = OptionsDialog(3, 12, table)
    assert dlg.table.rowCount() == len(table)
    dlg.autosave.setValue(4)
    assert dlg.values()[:2] == (4, 12)
    dlg.reset_shortcuts()
    assert dlg.values()[2]["edit_undo"] == "Ctrl+Z"


def test_espaces_de_travail(env):
    make, lib, tmp = env
    w = make()
    assert w.workspace_names() == []
    w.docks["library"].hide()
    assert w.save_workspace("  Dessin  ") == "Dessin"
    w.docks["library"].show()
    assert w.load_workspace("Dessin") and w.docks["library"].isHidden()
    w.reset_layout()
    assert not w.docks["library"].isHidden()
    for bad in ("", "x" * 41, "   "):
        with pytest.raises(ValueError):
            w.save_workspace(bad)
    assert make().workspace_names() == ["Dessin"]  # persistant
    w.prefs.set("workspaces", {"Cassé": "pas-du-base64-valide!!", "Vide": "AAAA"})
    assert w.load_workspace("Cassé") is False and not w.docks["library"].isHidden()  # jamais de panneau perdu
    assert w.load_workspace("Inconnu") is False
    assert w.delete_workspace("Vide") and not w.delete_workspace("Vide")
    w._fill_workspace_menu()
    assert "Disposition par défaut" in [a.text() for a in w.workspace_menu.actions()]


def test_import_d_images_par_lot_depuis_le_panneau(env, monkeypatch):
    from PIL import Image
    make, lib, tmp = env
    monkeypatch.setattr("sbs.ui.library_panel.QMessageBox.information", lambda *a, **k: None)
    monkeypatch.setattr("sbs.ui.library_panel.QMessageBox.warning", lambda *a, **k: None)
    src = tmp / "images é"
    src.mkdir()
    for n in range(4):
        Image.new("RGBA", (8, 8), (n * 40, 0, 0, 255)).save(src / f"s{n}.png")
    (src / "cassee.png").write_bytes(b"pas une image")
    w = make()
    before = lib.count()
    w.library_panel.start_images_import([src])
    loop = QEventLoop()
    timer = QTimer()
    timer.setInterval(50)
    timer.timeout.connect(lambda: loop.quit() if w.library_panel._thread is None else None)
    timer.start()
    QTimer.singleShot(15000, loop.quit)
    loop.exec()
    timer.stop()
    assert w.library_panel._thread is None
    assert lib.count() == before + 4
    assert w.library_panel.images_button.isEnabled()


def test_cache_d_images_borne_en_memoire(env):
    from PIL import Image

    from sbs.canvas.pixmaps import PixmapCache
    make, lib, tmp = env
    assets = []
    for n in range(6):
        buf = tmp / f"p{n}.png"
        Image.new("RGBA", (32, 32), (n * 30, 0, 0, 255)).save(buf)
        assets.append(lib.create_asset(f"p{n}", buf.read_bytes(), (16, 31)))
    cache = PixmapCache(lib, max_bytes=3 * 32 * 32 * 4)
    for a in assets:
        assert not cache.get(a).isNull()
    assert cache.size_bytes <= 3 * 32 * 32 * 4  # les plus anciennes ont été oubliées
    assert not cache.get(assets[0]).isNull()  # rechargée à la demande
    cache.invalidate(assets[0])
    assert cache.size_bytes >= 0


def test_guide_et_version_en_ligne_de_commande(env, capsys):
    from sbs.app import main
    from sbs.ui.guide_dialog import GuideDialog, guide_text
    assert "guide utilisateur" in guide_text()
    d = GuideDialog()
    assert "Sprite Builder Studio" in d.view.toPlainText()
    assert main(["--version"]) == 0
    assert "Sprite Builder Studio" in capsys.readouterr().out


def test_auto_test_d_installation(env, tmp_path, monkeypatch):
    from sbs.selftest import run
    monkeypatch.setenv("SBS_DATA_DIR", str(tmp_path / "x"))
    report = tmp_path / "rapport.txt"
    assert run(str(report)) == 0, report.read_text(encoding="utf-8")
    text = report.read_text(encoding="utf-8")
    assert "tout fonctionne" in text and "ÉCHEC" not in text
