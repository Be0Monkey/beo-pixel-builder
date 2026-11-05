"""Affiche le guide utilisateur (Markdown embarqué)."""

from pathlib import Path

from PySide6.QtWidgets import QDialog, QTextBrowser, QVBoxLayout

GUIDE = Path(__file__).resolve().parent.parent / "resources" / "Guide_utilisateur.md"


def guide_text() -> str:
    try:
        return GUIDE.read_text(encoding="utf-8")
    except OSError:
        return "# Guide indisponible\n\nLe fichier du guide n'a pas été trouvé dans cette installation."


class GuideDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Guide utilisateur")
        self.resize(820, 640)
        self.view = QTextBrowser()
        self.view.setOpenExternalLinks(False)
        self.view.setMarkdown(guide_text())
        lay = QVBoxLayout(self)
        lay.addWidget(self.view)
