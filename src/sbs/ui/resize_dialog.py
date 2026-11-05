"""Redimensionner : facteurs entiers (pixels nets). Crée un nouveau module ; l'original reste intact."""

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QVBoxLayout,
)

from sbs.canvas.scene import CanvasScene
from sbs.services import resize as RZ


class ResizeDialog(QDialog):
    def __init__(self, scene: CanvasScene, asset_uuid: str, has_selection: bool, parent=None):
        super().__init__(parent)
        self.scene, self.asset_uuid = scene, asset_uuid
        asset = scene.library.get(asset_uuid)
        self.setWindowTitle(f"Redimensionner — {asset.name if asset else '?'}")
        self._size = (asset.width, asset.height) if asset else (0, 0)
        self.factor = QComboBox()
        for mode, k in RZ.FACTORS:
            self.factor.addItem(RZ.label(mode, k), (mode, k))
        self.factor.setCurrentIndex(3)  # ×2
        self.replace = QCheckBox("Remplacer les objets sélectionnés par la nouvelle version")
        self.replace.setChecked(has_selection)
        self.replace.setEnabled(has_selection)
        self.info = QLabel("")
        self.info.setWordWrap(True)
        note = QLabel("Les pixels restent nets (facteurs entiers). Un nouveau module est créé dans la "
                      "bibliothèque ; l'original n'est pas modifié. Les variantes ne sont pas reprises.")
        note.setWordWrap(True)
        form = QFormLayout()
        form.addRow("Facteur", self.factor)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.apply)
        buttons.rejected.connect(self.reject)
        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(self.replace)
        lay.addWidget(self.info)
        lay.addWidget(note)
        lay.addWidget(buttons)
        self.factor.currentIndexChanged.connect(self.update_info)
        self.update_info()

    def update_info(self) -> None:
        mode, k = self.factor.currentData()
        try:
            nw, nh = RZ.target_size(*self._size, mode, k)
            self.info.setText(f"{self._size[0]}×{self._size[1]} → {nw}×{nh} px")
        except ValueError as exc:
            self.info.setText(str(exc))

    def apply(self) -> None:
        mode, k = self.factor.currentData()
        try:
            if self.replace.isChecked():
                n, m = self.scene.resize_selected(mode, k)
                self.result_text = f"{n} objet(s) remplacé(s), {m} module(s) créé(s) (Ctrl+Z pour annuler)."
            else:
                new = self.scene.create_resized_module(self.asset_uuid, mode, k)
                self.result_text = f"Module « {new.name} » ajouté à la bibliothèque."
        except ValueError as exc:
            self.info.setText(str(exc))
            return
        self.accept()
