"""Options : sauvegarde automatique, versions gardées, raccourcis clavier."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QKeySequenceEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)


class OptionsDialog(QDialog):
    """`shortcuts` : id -> (libellé, raccourcis par défaut, raccourci actuel)."""

    def __init__(self, autosave_minutes: int, backup_keep: int,
                 shortcuts: dict[str, tuple[str, list[str], str]], parent=None, start_tab: int = 0):
        super().__init__(parent)
        self.setWindowTitle("Options")
        self.resize(640, 520)
        self._defaults = {k: v[1] for k, v in shortcuts.items()}
        tabs = QTabWidget()

        general = QWidget()
        form = QFormLayout(general)
        self.autosave = QSpinBox()
        self.autosave.setRange(0, 120)
        self.autosave.setSuffix(" min")
        self.autosave.setSpecialValueText("désactivée")
        self.autosave.setValue(autosave_minutes)
        self.autosave.setToolTip("Copie de secours du travail en cours, utilisée si l'application s'arrête brutalement.")
        self.keep = QSpinBox()
        self.keep.setRange(1, 200)
        self.keep.setValue(backup_keep)
        self.keep.setToolTip("Nombre d'anciennes versions conservées par projet (une par enregistrement).")
        form.addRow("Sauvegarde automatique toutes les", self.autosave)
        form.addRow("Versions conservées par projet", self.keep)

        self.table = QTableWidget(len(shortcuts), 2)
        self.table.setHorizontalHeaderLabels(["Action", "Raccourci"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 340)
        self.table.verticalHeader().hide()
        self.ids = list(shortcuts)
        self.editors: dict[str, QKeySequenceEdit] = {}
        for row, (sid, (label, _default, current)) in enumerate(shortcuts.items()):
            item = QTableWidgetItem(label)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 0, item)
            ed = QKeySequenceEdit(QKeySequence(current))
            ed.setMaximumSequenceLength(1)
            self.table.setCellWidget(row, 1, ed)
            self.editors[sid] = ed
        reset = QPushButton("Rétablir tous les raccourcis par défaut")
        reset.clicked.connect(self.reset_shortcuts)
        sc = QWidget()
        lay = QVBoxLayout(sc)
        lay.addWidget(self.table)
        lay.addWidget(reset)

        tabs.addTab(general, "Général")
        tabs.addTab(sc, "Raccourcis clavier")
        tabs.setCurrentIndex(start_tab)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        outer = QVBoxLayout(self)
        outer.addWidget(tabs)
        outer.addWidget(buttons)

    def reset_shortcuts(self) -> None:
        for sid, ed in self.editors.items():
            d = self._defaults[sid]
            ed.setKeySequence(QKeySequence(d[0] if d else ""))

    def values(self) -> tuple[int, int, dict[str, str]]:
        return (self.autosave.value(), self.keep.value(),
                {sid: ed.keySequence().toString() for sid, ed in self.editors.items()})
