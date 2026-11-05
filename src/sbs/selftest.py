"""Auto-test d'installation : `sbs --selftest` (ou SpriteBuilderStudio.exe --selftest).

Vérifie, dans un dossier de données jetable, que l'installation fonctionne de bout en bout :
interface (hors écran), bibliothèque, import d'images, assemblage, enregistrement/relecture,
sauvegarde versionnée, récupération, export PNG, export Godot, éclairage. Code retour 0 = tout va bien.
Ne touche ni aux préférences ni à la bibliothèque de l'utilisateur.
"""

import os
import shutil
import sys
import tempfile
import traceback
from pathlib import Path


def _checks(tmp: Path) -> list[tuple[str, bool, str]]:
    from PIL import Image
    from PySide6.QtWidgets import QApplication, QMessageBox

    from sbs import __version__
    from sbs.exporters import EXPORTERS
    from sbs.exporters.base import run_export
    from sbs.exporters.model import build_export_scene
    from sbs.services.batch_import import import_images
    from sbs.services.exporter import export_png
    from sbs.services.library import Library
    from sbs.services.lighting import LightSettings, LitItem, render_lit
    from sbs.services.preferences import Preferences
    from sbs.ui.main_window import MainWindow

    results: list[tuple[str, bool, str]] = []

    def check(name: str, fn) -> None:
        try:
            detail = fn()
            results.append((name, True, str(detail or "")))
        except Exception as exc:  # noqa: BLE001 - on rapporte tout échec
            results.append((name, False, f"{type(exc).__name__}: {exc}"))

    app = QApplication.instance() or QApplication([])
    saved = {fn: QMessageBox.__dict__[fn] for fn in ("critical", "information", "warning")}
    for fn in saved:  # jamais de boîte bloquante pendant le test (rétablies à la fin)
        setattr(QMessageBox, fn, staticmethod(lambda *a, **k: None))
    state: dict = {}

    def sprites():
        src = tmp / "sources avec é et espaces"
        src.mkdir()
        for n, c in enumerate([(200, 30, 30, 255), (30, 200, 30, 255), (30, 30, 200, 128)]):
            Image.new("RGBA", (16 + n, 24), c).save(src / f"sprite {n}.png")
        lib = Library(tmp / "bibliothèque")
        rep = import_images(lib, sorted(src.glob("*.png")))
        assert len(rep.imported) == 3 and not rep.errors, rep
        state["lib"] = lib
        return f"{len(rep.imported)} images"
    check("bibliothèque et import d'images", sprites)

    def window():
        lib = state["lib"]
        w = MainWindow(Preferences(tmp / "data" / "preferences.json"), lib)
        w.show()
        state["win"] = w
        a = lib.list_assets()
        for i, asset in enumerate(a):
            w.canvas_scene.add_asset(asset.uuid, 20 * i, 10 * i)
        assert len(w.scene_model) == 3
        return f"{len(w.scene_model)} objets"
    check("fenêtre principale et assemblage", window)

    def saving():
        w = state["win"]
        target = tmp / "mon projet é" / "test.sbsproj"
        target.parent.mkdir()
        assert w.save_to(target)
        assert w.backups.versions(w.meta.id), "aucune version rangée"
        n = len(w.scene_model)
        assert w.open_path(target) and len(w.scene_model) == n
        return target.name
    check("enregistrement, version, relecture", saving)

    def recovery():
        w = state["win"]
        w.canvas_scene.add_asset(state["lib"].list_assets()[0].uuid, 0, 0)
        assert w.autosave_now()
        assert w.recovery.pending()
        w.dirty = False
        w.recovery.clear(w.meta.id)
        assert not w.recovery.pending()
    check("copie de secours automatique", recovery)

    def png():
        w = state["win"]
        out = tmp / "export.png"
        export_png(out, w.scene_model.all(), state["lib"])
        with Image.open(out) as im:
            assert im.mode == "RGBA" and im.width > 0
            return f"{im.width}×{im.height} RGBA"
    check("export PNG", png)

    def godot():
        w = state["win"]
        scene = build_export_scene(w.scene_model, state["lib"], "test")
        dest = tmp / "export godot"
        report = run_export(EXPORTERS["godot4"], scene, dest, {"create_project": True})
        assert report.ok, report.error
        assert (dest / "test.tscn").exists() and (dest / "project.godot").exists()
    check("export Godot 4", godot)

    def light():
        lib = state["lib"]
        a = lib.list_assets()[0]
        with Image.open(lib.abs_path(a.image_path)) as im:
            base = im.convert("RGBA")
        img, _ = render_lit([LitItem(base, None, None, 0, 0, (a.pivot_x, a.pivot_y))], LightSettings())
        return f"{img.width}×{img.height}"
    check("aperçu éclairé (NumPy)", light)

    def closing():
        w = state["win"]
        w.dirty = False
        w.close()
    check("fermeture propre", closing)
    for fn, original in saved.items():
        setattr(QMessageBox, fn, original)
    return results


def run(report_path: str | None = None) -> int:
    """Retourne 0 si tout est bon. Écrit un rapport texte (stdout si disponible, et fichier si demandé)."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    tmp = Path(tempfile.mkdtemp(prefix="sbs_selftest_é "))
    os.environ["SBS_DATA_DIR"] = str(tmp / "data")
    lines = []
    try:
        from sbs import __version__
        lines.append(f"Sprite Builder Studio {__version__} — auto-test d'installation")
        lines.append(f"Python {sys.version.split()[0]} — {sys.platform}")
        try:
            results = _checks(tmp)
        except Exception:  # noqa: BLE001
            results = [("démarrage", False, traceback.format_exc())]
        for name, ok, detail in results:
            lines.append(f"[{'OK' if ok else 'ÉCHEC'}] {name}" + (f" — {detail}" if detail else ""))
        failed = [r for r in results if not r[1]]
        lines.append("RÉSULTAT : " + ("tout fonctionne" if not failed else f"{len(failed)} échec(s)"))
        code = 0 if not failed else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    text = "\n".join(lines)
    if sys.stdout is not None:
        try:
            print(text)
        except (UnicodeEncodeError, OSError):
            print(text.encode("ascii", "replace").decode())
    if report_path:
        Path(report_path).write_text(text, encoding="utf-8")
    return code


__all__ = ["run"]
