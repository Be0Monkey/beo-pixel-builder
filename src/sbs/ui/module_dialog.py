"""Fenêtre « Propriétés du module » : pivot, ancrages nommés, et portée de la modification."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from sbs.canvas.scene import CanvasScene
from sbs.domain.asset import Anchor


class ModuleDialog(QDialog):
    def __init__(self, scene: CanvasScene, parent: QWidget | None = None):
        super().__init__(parent)
        self.scene = scene
        self.asset = scene.selected_asset()
        self.setWindowTitle("Propriétés du module")
        a = self.asset
        uses = scene.count_uses(a.uuid) if a else 0
        selected = len(scene.selected_ids())

        self.pivot_x, self.pivot_y = QSpinBox(), QSpinBox()
        for sp, hi in ((self.pivot_x, a.width if a else 0), (self.pivot_y, a.height if a else 0)):
            sp.setRange(0, hi)
        if a:
            self.pivot_x.setValue(a.pivot_x)
            self.pivot_y.setValue(a.pivot_y)

        form = QFormLayout()
        form.addRow("Module", QLabel(f"{a.name}  ({a.width}×{a.height} px)" if a else "—"))
        form.addRow("Utilisations dans la scène", QLabel(str(uses)))
        form.addRow("Pivot X (depuis la gauche)", self.pivot_x)
        form.addRow("Pivot Y (depuis le haut)", self.pivot_y)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Nom", "X", "Y"])
        for anchor in (a.anchors if a else ()):
            self._add_row(anchor.name, anchor.x, anchor.y)
        add, rem = QPushButton("+ Ancrage"), QPushButton("Supprimer")
        add.clicked.connect(lambda: self._add_row(f"ancrage_{self.table.rowCount() + 1}", 0, 0))
        rem.clicked.connect(self._remove_row)
        row = QHBoxLayout()
        row.addWidget(add)
        row.addWidget(rem)
        row.addStretch(1)

        self.rb_source = QRadioButton(f"Toutes les utilisations du module ({uses})")
        self.rb_instance = QRadioButton(f"Cette sélection seulement ({selected}) — crée une copie du module")
        self.rb_instance.setChecked(True)  # choix le plus prudent par défaut
        self.error = QLabel("")
        self.error.setStyleSheet("color: #c0392b")
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)

        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(QLabel("Ancrages nommés (pixels depuis le coin haut-gauche de l'image) :"))
        lay.addWidget(self.table)
        lay.addLayout(row)
        lay.addWidget(QLabel("Appliquer la modification à :"))
        lay.addWidget(self.rb_instance)
        lay.addWidget(self.rb_source)
        lay.addWidget(self.error)
        lay.addWidget(buttons)

    def _add_row(self, name: str, x: int, y: int) -> None:
        r = self.table.rowCount()
        self.table.insertRow(r)
        self.table.setItem(r, 0, QTableWidgetItem(name))
        for c, v in ((1, x), (2, y)):
            it = QTableWidgetItem(str(v))
            it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(r, c, it)

    def _remove_row(self) -> None:
        r = self.table.currentRow()
        if r >= 0:
            self.table.removeRow(r)

    def anchors(self) -> list[Anchor]:
        out = []
        for r in range(self.table.rowCount()):
            try:
                out.append(Anchor(self.table.item(r, 0).text().strip(),
                                  int(self.table.item(r, 1).text()), int(self.table.item(r, 2).text())))
            except ValueError as exc:
                raise ValueError(f"ligne {r + 1} : X et Y doivent être des nombres entiers") from exc
        return out

    def apply(self) -> str | None:
        """Applique la modification ; renvoie None si OK, sinon un message d'erreur."""
        if self.asset is None:
            return "Sélectionne un ou plusieurs objets du même module."
        try:
            anchors = self.anchors()
        except ValueError as exc:
            return str(exc)
        scope = "source" if self.rb_source.isChecked() else "instance"
        return self.scene.edit_geometry(scope, (self.pivot_x.value(), self.pivot_y.value()), anchors)

    def _accept(self) -> None:
        err = self.apply()
        if err:
            self.error.setText(err)
        else:
            self.accept()
