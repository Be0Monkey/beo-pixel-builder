"""Fenêtre principale (atelier Construction) : docks et barre d'état. Voir 03_Interface_et_parcours.md."""

import base64

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QDockWidget,
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
from sbs.services.library import Library
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

        self.scene_model = SceneModel()
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
        quit_action = QAction("&Quitter", self, shortcut="Ctrl+Q", triggered=self.close)
        file_menu.addAction(quit_action)

        edit_menu = bar.addMenu("&Édition")
        edit_menu.addAction(QAction("&Supprimer", self, shortcut="Delete",
                                    triggered=self.canvas_scene.remove_selected))

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
