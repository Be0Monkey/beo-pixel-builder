"""Point d'entrée.

Options : `--version` ; `--selftest [--report FICHIER]` (auto-test d'installation, sans fenêtre visible).
"""

import sys

from sbs import __version__


def _option(argv: list[str], name: str) -> str | None:
    if name in argv:
        i = argv.index(name)
        return argv[i + 1] if i + 1 < len(argv) else None
    return None


def _install_starter_modules(library) -> None:
    """Premier lancement : bibliothèque vide -> on y met les modules fournis avec l'application."""
    from sbs.services.phone_pack import import_library_pack, starter_pack_path
    try:
        if library.list_assets():
            return
        import_library_pack(library, starter_pack_path().read_text(encoding="utf-8"))
    except Exception:  # jamais bloquant : l'utilisateur peut toujours importer son propre kit
        pass


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if "--version" in args:
        if sys.stdout is not None:
            print(f"Sprite Builder Studio {__version__}")
        return 0
    if "--selftest" in args:
        from sbs.selftest import run
        return run(_option(args, "--report"))

    from PySide6.QtWidgets import QApplication

    from sbs.paths import user_data_dir
    from sbs.services.library import Library
    from sbs.services.preferences import Preferences
    from sbs.ui.main_window import MainWindow

    app = QApplication.instance() or QApplication(["sbs", *args])
    app.setApplicationName("Sprite Builder Studio")
    prefs = Preferences(user_data_dir() / "preferences.json")
    library = Library(user_data_dir() / "library")
    _install_starter_modules(library)
    window = MainWindow(prefs, library)
    window.show()
    window.offer_recovery()  # un arrêt brutal précédent ? proposer de récupérer le travail
    return app.exec()
