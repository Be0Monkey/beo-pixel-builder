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
from sbs.services.preferences import Preferences

_B64 = "utf-8"


def _placeholder(text: str) -> QLabel:
    label = QLabel(text)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setWordWrap(True)
    return label


class MainWindow(QMainWindow):
    def __init__(self, prefs: Preferences):
        super().__init__()
        self.prefs = prefs
        self.setWindowTitle("Sprite Builder Studio")
        self.resize(1400, 850)

        self.setCentralWidget(_placeholder("Canevas\n(jalon J1)"))
        self.docks: dict[str, QDockWidget] = {}
        self._add_dock("library", "Bibliothèque", Qt.DockWidgetArea.LeftDockWidgetArea,
                       "Bibliothèque\n(jalon J1)")
        self._add_dock("properties", "Propriétés", Qt.DockWidgetArea.RightDockWidgetArea,
                       "Propriétés\n(jalon J1)")
        self._add_dock("floors", "Étages / Calques", Qt.DockWidgetArea.RightDockWidgetArea,
                       "Étages et calques\n(jalon J2)")

        self._build_menus()
        self._build_toolbar()
        self.statusBar().showMessage("Prêt")
        self._default_state = self.saveState()
        self._default_geometry = self.saveGeometry()
        self._restore_layout()

    # --- construction -------------------------------------------------
    def _add_dock(self, key: str, title: str, area: Qt.DockWidgetArea, text: str) -> None:
        dock = QDockWidget(title, self)
        dock.setObjectName(f"dock_{key}")  # obligatoire pour saveState()
        dock.setWidget(_placeholder(text))
        self.addDockWidget(area, dock)
        self.docks[key] = dock

    def _build_menus(self) -> None:
        bar = self.menuBar()
        file_menu = bar.addMenu("&Fichier")
        quit_action = QAction("&Quitter", self, shortcut="Ctrl+Q", triggered=self.close)
        file_menu.addAction(quit_action)

        view_menu = bar.addMenu("&Vue")
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
