"""Exports : JSON structuré et scène Godot 4, vers un dossier qui nous appartient."""

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QWidget,
)

from sbs.canvas.scene import CanvasScene
from sbs.exporters import EXPORTERS, build_export_scene, run_export


class ExportDialog(QDialog):
    def __init__(self, scene: CanvasScene, kind: str, name: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.scene, self.kind, self.scene_name = scene, kind, name
        self.exporter = EXPORTERS[kind]
        self.setWindowTitle(f"Exporter — {self.exporter.label}")
        self.folder = QLineEdit()
        browse = QPushButton("Choisir…")
        browse.clicked.connect(self._browse)
        row = QHBoxLayout()
        row.addWidget(self.folder, 1)
        row.addWidget(browse)
        form = QFormLayout(self)
        form.addRow("Dossier de destination", row)
        self.prefix = QLineEdit()
        self.project = QCheckBox("Créer aussi project.godot (projet Godot de test)")
        self.textures = QCheckBox("Copier les images (dossier textures/)")
        self.textures.setChecked(True)
        if kind == "godot4":
            self.prefix.setPlaceholderText("vide = le dossier est la racine du projet Godot")
            form.addRow("Chemin du dossier dans le projet", self.prefix)
            form.addRow(self.project)
        else:
            form.addRow(self.textures)
        self.note = QLabel("Rien n'est écrasé : un dossier qui contient d'autres fichiers est refusé.")
        self.note.setWordWrap(True)
        form.addRow(self.note)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.run)
        bb.rejected.connect(self.reject)
        form.addRow(bb)
        self.report = None

    def _browse(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Dossier de destination")
        if d:
            self.folder.setText(d)

    def options(self) -> dict:
        return {"res_prefix": self.prefix.text(), "create_project": self.project.isChecked(),
                "copy_textures": self.textures.isChecked()}

    def run(self) -> None:
        if not self.folder.text().strip():
            self.note.setText("Choisis un dossier de destination.")
            return
        export = build_export_scene(self.scene.model, self.scene.library, self.scene_name)
        self.report = run_export(self.exporter, export, Path(self.folder.text()), self.options())
        if not self.report.ok:
            QMessageBox.warning(self, "Export impossible", self.report.error)
            return
        extra = f"\n{len(self.report.warnings)} avertissement(s) :\n- " + "\n- ".join(self.report.warnings[:8]) \
            if self.report.warnings else ""
        QMessageBox.information(self, "Export terminé",
                                f"{len(self.report.files)} fichier(s) écrit(s) dans\n{self.folder.text()}{extra}")
        self.accept()
