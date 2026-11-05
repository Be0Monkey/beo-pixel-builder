"""Fenêtre principale (atelier Construction) : docks et barre d'état. Voir 03_Interface_et_parcours.md."""

import base64
from pathlib import Path

from PySide6.QtCore import QByteArray, QMimeData, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QDockWidget,
    QApplication,
    QFileDialog,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QToolBar,
    QWidget,
)

from sbs import __version__
from sbs.canvas.scene import CanvasScene
from sbs.canvas.view import CanvasView
from sbs.domain.scene import SceneModel
from sbs.services.clipboard_codec import MIME as CLIP_MIME
from sbs.services.exporter import ExportError, export_png
from sbs.services.library import Library
from sbs.services.project_io import (
    EXTENSION,
    ProjectError,
    ProjectMeta,
    load_project,
    save_project,
)
from sbs.services.preferences import Preferences
from sbs.ui.library_panel import LibraryPanel

_B64 = "utf-8"


def _placeholder(text: str) -> QLabel:
    label = QLabel(text)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setWordWrap(True)
    return label


class MainWindow(QMainWindow):
    def __init__(self, prefs: Preferences, library: Library):
        super().__init__()
        self.prefs = prefs
        self.library = library
        self.setWindowTitle("Sprite Builder Studio")
        self.resize(1400, 850)

        self.meta = ProjectMeta()
        self.path: Path | None = None
        self.dirty = False
        self._loading = False
        self._paste_n = 0
        self.scene_model = SceneModel()
        self.scene_model.add_listener(self._on_model_changed)
        self.canvas_scene = CanvasScene(self.scene_model, library)
        self.canvas = CanvasView(self.canvas_scene)
        self.setCentralWidget(self.canvas)
        self.docks: dict[str, QDockWidget] = {}
        self.library_panel = LibraryPanel(library)
        self._add_dock("library", "Bibliothèque", Qt.DockWidgetArea.LeftDockWidgetArea,
                       self.library_panel)
        self._add_dock("properties", "Propriétés", Qt.DockWidgetArea.RightDockWidgetArea,
                       "Propriétés\n(jalon J1b)")
        self._add_dock("floors", "Étages / Calques", Qt.DockWidgetArea.RightDockWidgetArea,
                       "Étages et calques\n(jalon J2)")

        self.library_panel.asset_activated.connect(self.canvas.add_asset_at_center)
        self.pos_label = QLabel()
        self.statusBar().addPermanentWidget(self.pos_label)
        self.canvas.mouse_moved.connect(lambda x, y: self._update_status(x, y))
        self.canvas.zoom_changed.connect(lambda z: self._update_status())
        self._mouse = (0, 0)
        self._build_menus()
        self._build_toolbar()
        self.statusBar().showMessage("Prêt")
        self._update_status()
        self._update_title()
        QApplication.clipboard().dataChanged.connect(lambda: setattr(self, "_paste_n", 0))
        self._default_state = self.saveState()
        self._default_geometry = self.saveGeometry()
        self._restore_layout()

    # --- construction -------------------------------------------------
    def _add_dock(self, key: str, title: str, area: Qt.DockWidgetArea, content: str | QWidget) -> None:
        dock = QDockWidget(title, self)
        dock.setObjectName(f"dock_{key}")  # obligatoire pour saveState()
        dock.setWidget(_placeholder(content) if isinstance(content, str) else content)
        self.addDockWidget(area, dock)
        self.docks[key] = dock

    def _build_menus(self) -> None:
        bar = self.menuBar()
        file_menu = bar.addMenu("&Fichier")
        file_menu.addAction(QAction("&Nouveau", self, shortcut="Ctrl+N", triggered=self.new_project))
        file_menu.addAction(QAction("&Ouvrir…", self, shortcut="Ctrl+O", triggered=self.open_dialog))
        file_menu.addAction(QAction("&Enregistrer", self, shortcut="Ctrl+S", triggered=self.save))
        file_menu.addAction(QAction("Enregistrer &sous…", self, shortcut="Ctrl+Shift+S",
                                    triggered=self.save_as))
        file_menu.addSeparator()
        file_menu.addAction(QAction("E&xporter en PNG…", self, shortcut="Ctrl+E",
                                    triggered=lambda: self.export_dialog(False)))
        file_menu.addAction(QAction("Exporter en PNG a&grandi…", self,
                                    triggered=lambda: self.export_dialog(True)))
        file_menu.addSeparator()
        file_menu.addAction(QAction("&Quitter", self, shortcut="Ctrl+Q", triggered=self.close))

        edit_menu = bar.addMenu("&Édition")
        edit_menu.addAction(QAction("&Copier", self, shortcut="Ctrl+C", triggered=self.copy_selection))
        edit_menu.addAction(QAction("Co&uper", self, shortcut="Ctrl+X", triggered=self.cut_selection))
        edit_menu.addAction(QAction("C&oller", self, shortcut="Ctrl+V", triggered=self.paste))
        edit_menu.addAction(QAction("Dupli&quer", self, shortcut="Ctrl+D",
                                    triggered=self.duplicate_selection))
        edit_menu.addSeparator()
        edit_menu.addAction(QAction("&Supprimer", self, shortcut="Delete",
                                    triggered=self.canvas_scene.remove_selected))
        edit_menu.addSeparator()
        edit_menu.addAction(QAction("Mettre &devant", self, shortcut="Ctrl+]",
                                    triggered=lambda: self.canvas_scene.shift_z_selected(1)))
        edit_menu.addAction(QAction("Mettre d&errière", self, shortcut="Ctrl+[",
                                    triggered=lambda: self.canvas_scene.shift_z_selected(-1)))
        edit_menu.addAction(QAction("Ordre &automatique", self, shortcut="Ctrl+\\",
                                    triggered=self.canvas_scene.reset_z_selected))

        view_menu = bar.addMenu("&Vue")
        view_menu.addAction(QAction("Zoom +", self, shortcut="Ctrl++", triggered=self.canvas.zoom_in))
        view_menu.addAction(QAction("Zoom −", self, shortcut="Ctrl+-", triggered=self.canvas.zoom_out))
        view_menu.addAction(QAction("Zoom 200 %", self, shortcut="Ctrl+0", triggered=self.canvas.zoom_reset))
        grid = QAction("Grille (32 px)", self, checkable=True, shortcut="G")
        grid.toggled.connect(self.canvas.set_grid_visible)
        view_menu.addAction(grid)
        view_menu.addSeparator()
        for dock in self.docks.values():
            view_menu.addAction(dock.toggleViewAction())
        view_menu.addSeparator()
        view_menu.addAction(
            QAction("Réinitialiser les panneaux", self, triggered=self.reset_layout)
        )

        help_menu = bar.addMenu("&Aide")
        help_menu.addAction(QAction("À propos", self, triggered=self._about))

    def _build_toolbar(self) -> None:
        tb = QToolBar("Outils", self)
        tb.setObjectName("toolbar_main")
        tb.setMovable(True)
        self.addToolBar(tb)
        tb.addWidget(QLabel("  Outils : à venir (J1)  "))

    def _update_status(self, x: int | None = None, y: int | None = None) -> None:
        if x is not None:
            self._mouse = (x, y)
        self.pos_label.setText(
            f"X: {self._mouse[0]}  Y: {self._mouse[1]}  |  Zoom: {round(self.canvas.zoom * 100)} %"
            f"  |  {len(self.scene_model)} objet(s)"
        )

    # --- document ---------------------------------------------------------------------------
    def _on_model_changed(self) -> None:
        if self._loading:
            return
        self.dirty = True
        self._update_title()
        self._update_status()

    def _update_title(self) -> None:
        name = self.path.stem if self.path else self.meta.name
        self.setWindowTitle(f"{name}{' *' if self.dirty else ''} — Sprite Builder Studio")

    def _confirm_discard(self) -> bool:
        """True si on peut continuer (rien à perdre, enregistré, ou abandon accepté)."""
        if not self.dirty:
            return True
        box = QMessageBox.question(
            self, "Modifications non enregistrées",
            "Enregistrer les modifications avant de continuer ?",
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
        )
        if box == QMessageBox.StandardButton.Save:
            return self.save()
        return box == QMessageBox.StandardButton.Discard

    def new_project(self) -> bool:
        if not self._confirm_discard():
            return False
        self._apply(ProjectMeta(), [], None)
        return True

    def _apply(self, meta: ProjectMeta, instances, path: Path | None) -> None:
        self._loading = True
        try:
            self.scene_model.replace(instances)
            self.canvas_scene.rebuild()
        finally:
            self._loading = False
        self.meta, self.path, self.dirty = meta, path, False
        self._update_title()
        self._update_status()

    def open_dialog(self) -> None:
        if not self._confirm_discard():
            return
        file, _ = QFileDialog.getOpenFileName(
            self, "Ouvrir un projet", "", f"Projet Sprite Builder Studio (*{EXTENSION})"
        )
        if file:
            self.open_path(Path(file))

    def open_path(self, path: Path) -> bool:
        """Charge un projet. En cas d'erreur, le projet actuel reste intact."""
        try:
            result = load_project(path, self.library)
        except ProjectError as exc:
            QMessageBox.critical(self, "Ouverture impossible", str(exc))
            return False
        self._apply(result.meta, result.instances, Path(path))
        notes = []
        if result.missing_assets:
            notes.append(f"{len(result.missing_assets)} image(s) absente(s) de la bibliothèque : "
                         "les objets concernés sont conservés et affichés en rose avec un « ? ».")
        if result.remapped:
            notes.append(f"{result.remapped} objet(s) rattaché(s) à la bibliothèque de cet ordinateur.")
        if notes:
            QMessageBox.information(self, "Projet ouvert", "\n".join(notes))
        return True

    def save(self) -> bool:
        if self.path is None:
            return self.save_as()
        return self.save_to(self.path)

    def save_as(self) -> bool:
        file, _ = QFileDialog.getSaveFileName(
            self, "Enregistrer le projet sous", f"{self.meta.name}{EXTENSION}",
            f"Projet Sprite Builder Studio (*{EXTENSION})",
        )
        if not file:
            return False
        path = Path(file)
        if path.suffix.lower() != EXTENSION:
            path = path.with_name(path.name + EXTENSION)
        return self.save_to(path)

    def save_to(self, path: Path) -> bool:
        self.canvas_scene.commit_positions()
        try:
            if self.path is None or Path(path) != self.path:
                self.meta.name = Path(path).stem
            save_project(Path(path), self.meta, self.scene_model.all(), self.library)
        except (OSError, ProjectError) as exc:
            QMessageBox.critical(
                self, "Enregistrement impossible",
                f"{exc}\n\nLe fichier précédent n'a pas été modifié.",
            )
            return False
        self.path, self.dirty = Path(path), False
        self._update_title()
        self.statusBar().showMessage(f"Enregistré : {path}", 4000)
        return True

    # --- copier / coller / dupliquer -----------------------------------------------------------
    def copy_selection(self) -> bool:
        text = self.canvas_scene.copy_payload()
        if text is None:
            return False
        mime = QMimeData()
        mime.setData(CLIP_MIME, text.encode("utf-8"))
        mime.setText(text)
        QApplication.clipboard().setMimeData(mime)
        self._paste_n = 0
        return True

    def cut_selection(self) -> bool:
        if not self.copy_selection():
            return False
        self.canvas_scene.remove_selected()
        return True

    def paste(self) -> int:
        mime = QApplication.clipboard().mimeData()
        if mime is None or not mime.hasFormat(CLIP_MIME):
            return 0
        text = bytes(mime.data(CLIP_MIME)).decode("utf-8", errors="replace")
        self._paste_n += 1
        step = 8 * self._paste_n  # décalage croissant : on voit les copies
        try:
            pasted, skipped = self.canvas_scene.paste_payload(text, step, step)
        except ValueError:
            self.statusBar().showMessage("Le presse-papiers ne contient pas d'objets de l'atelier.", 4000)
            return 0
        if skipped:
            self.statusBar().showMessage(f"{skipped} objet(s) ignoré(s) : image absente de la bibliothèque.", 5000)
        return pasted

    def duplicate_selection(self) -> int:
        return self.canvas_scene.duplicate_selected(8)

    # --- export -------------------------------------------------------------------------------
    def export_dialog(self, ask_scale: bool) -> None:
        scale = 1
        if ask_scale:
            scale, ok = QInputDialog.getInt(
                self, "Exporter en PNG agrandi", "Facteur d'agrandissement (entier) :", 2, 1, 16
            )
            if not ok:
                return
        file, _ = QFileDialog.getSaveFileName(
            self, "Exporter en PNG", f"{self.meta.name}.png", "Image PNG (*.png)"
        )
        if file:
            path = Path(file)
            if path.suffix.lower() != ".png":
                path = path.with_name(path.name + ".png")
            self.export_to(path, scale)

    def export_to(self, path: Path, scale: int = 1) -> bool:
        self.canvas_scene.commit_positions()
        try:
            r = export_png(Path(path), self.scene_model.all(), self.library, scale=scale)
        except ExportError as exc:
            QMessageBox.critical(self, "Export impossible", str(exc))
            return False
        msg = f"PNG exporté : {r.width}×{r.height} px (×{r.scale}), {r.count} objet(s)."
        if r.skipped:
            QMessageBox.warning(
                self, "Export incomplet",
                f"{msg}\n\n{len(r.skipped)} objet(s) non dessiné(s) (image absente ou illisible).",
            )
        self.statusBar().showMessage(msg, 6000)
        return True

    # --- disposition --------------------------------------------------
    def _restore_layout(self) -> None:
        geo = self.prefs.get("window.geometry")
        state = self.prefs.get("window.state")
        try:
            if geo:
                self.restoreGeometry(QByteArray(base64.b64decode(geo)))
            if state:
                self.restoreState(QByteArray(base64.b64decode(state)))
        except (ValueError, TypeError):
            self.reset_layout()

    def reset_layout(self) -> None:
        """Remet les panneaux par défaut (jamais de panneau définitivement perdu)."""
        self.restoreState(self._default_state)
        for dock in self.docks.values():
            dock.show()
            dock.setFloating(False)

    def save_layout(self) -> None:
        self.prefs.set("window.geometry", base64.b64encode(bytes(self.saveGeometry())).decode(_B64))
        self.prefs.set("window.state", base64.b64encode(bytes(self.saveState())).decode(_B64))
        self.prefs.save()

    def closeEvent(self, event) -> None:
        if not self._confirm_discard():
            event.ignore()
            return
        try:
            self.save_layout()
        except OSError as exc:
            QMessageBox.warning(self, "Préférences", f"Impossible d'enregistrer la disposition : {exc}")
        super().closeEvent(event)

    def _about(self) -> None:
        QMessageBox.about(
            self, "À propos",
            f"Sprite Builder Studio {__version__}\nApplication locale, sans IA.",
        )


__all__ = ["MainWindow", "QWidget"]
