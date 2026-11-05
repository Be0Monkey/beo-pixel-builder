"""Versions du projet et récupérations disponibles."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
)

from sbs.services.backups import RecoveryEntry, Version

ROLE = Qt.ItemDataRole.UserRole


class VersionsDialog(QDialog):
    def __init__(self, versions: list[Version], recoveries: list[RecoveryEntry], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Versions et récupération")
        self.resize(520, 400)
        self.list = QListWidget()
        for e in recoveries:
            it = QListWidgetItem(f"Récupération automatique — {e.name} — {e.saved_at}")
            it.setData(ROLE, ("recovery", e))
            self.list.addItem(it)
        for v in versions:
            it = QListWidgetItem(f"Version enregistrée — {v.created}")
            it.setData(ROLE, ("version", v))
            self.list.addItem(it)
        text = ("Choisis un élément puis « Ouvrir ». Une ancienne version s'ouvre comme une copie "
                "non enregistrée : ton projet actuel n'est pas touché.")
        if not versions and not recoveries:
            text = "Aucune version ni récupération disponible pour l'instant."
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(text, wordWrap=True))
        lay.addWidget(self.list)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Open | QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Open).setEnabled(False)
        self.open_button = buttons.button(QDialogButtonBox.StandardButton.Open)
        self.list.currentItemChanged.connect(lambda cur, _prev: self.open_button.setEnabled(cur is not None))
        self.list.itemDoubleClicked.connect(lambda _it: self.accept())
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)

    def choice(self):
        it = self.list.currentItem()
        return it.data(ROLE) if it is not None else None
