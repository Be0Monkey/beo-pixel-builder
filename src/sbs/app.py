"""Point d'entrée."""

import sys

from PySide6.QtWidgets import QApplication

from sbs.paths import user_data_dir
from sbs.services.library import Library
from sbs.services.preferences import Preferences
from sbs.ui.main_window import MainWindow


def main(argv: list[str] | None = None) -> int:
    app = QApplication.instance() or QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName("Sprite Builder Studio")
    prefs = Preferences(user_data_dir() / "preferences.json")
    library = Library(user_data_dir() / "library")
    window = MainWindow(prefs, library)
    window.show()
    return app.exec()
