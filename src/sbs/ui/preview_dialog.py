"""Aperçu éclairé (SIMULATION) : lumière, ombres, émission et fond, sans jamais modifier les sprites."""

from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from sbs.canvas.scene import CanvasScene
from sbs.services.backgrounds import BACKGROUNDS
from sbs.services.lighting import LightSettings, load_items, render_lit

BANNER = "SIMULATION D'ÉCLAIRAGE — aperçu seulement : rien n'est écrit dans les sprites ni dans le projet."


def _slider(lo: int, hi: int, value: int) -> QSlider:
    s = QSlider(Qt.Orientation.Horizontal)
    s.setRange(lo, hi)
    s.setValue(value)
    return s


def to_qimage(img) -> QImage:
    data = img.tobytes("raw", "RGBA")
    qi = QImage(data, img.width, img.height, img.width * 4, QImage.Format.Format_RGBA8888)
    return qi.copy()  # copie : `data` peut être libéré


class PreviewDialog(QDialog):
    def __init__(self, scene: CanvasScene, parent: QWidget | None = None):
        super().__init__(parent)
        self.scene = scene
        self.setWindowTitle("Aperçu éclairé (simulation)")
        self.resize(900, 700)
        self.image = None
        banner = QLabel(BANNER)
        banner.setStyleSheet("background:#8a5a00;color:white;padding:4px;font-weight:bold")
        banner.setWordWrap(True)

        self.az = _slider(0, 360, 135)
        self.el = _slider(5, 85, 45)
        self.intensity = _slider(0, 200, 80)
        self.ambient = _slider(0, 150, 55)
        self.emission = _slider(0, 200, 100)
        self.shadow_opacity = _slider(0, 100, 35)
        self.shadows = QCheckBox("Ombres au sol")
        self.shadows.setChecked(True)
        self.flip = QCheckBox("Normales « Y vers le haut » (Blender)")
        self.flip.setChecked(True)
        self.bg = QComboBox()
        self.bg.addItem("Transparent", "transparent")
        for key, (label, _, _) in BACKGROUNDS.items():
            self.bg.addItem(label, key)
        self.bg.setCurrentIndex(self.bg.findData("ciel"))
        self.zoom = QSpinBox()
        self.zoom.setRange(1, 8)
        self.zoom.setValue(2)
        self.zoom.setSuffix(" ×")

        form = QFormLayout()
        for label, w in (("Direction (°)", self.az), ("Hauteur du soleil (°)", self.el),
                         ("Lumière", self.intensity), ("Ambiance", self.ambient), ("Émission", self.emission),
                         ("Opacité des ombres", self.shadow_opacity)):
            form.addRow(label, w)
        form.addRow("Fond", self.bg)
        form.addRow("Zoom", self.zoom)
        form.addRow(self.shadows)
        form.addRow(self.flip)
        self.view = QLabel()
        self.view.setAlignment(Qt.AlignmentFlag.AlignCenter)
        area = QScrollArea()
        area.setWidget(self.view)
        area.setWidgetResizable(True)
        self.info = QLabel("")
        save = QPushButton("Enregistrer l'aperçu en PNG…")
        save.clicked.connect(self.save_png)
        close = QPushButton("Fermer")
        close.clicked.connect(self.close)
        row = QHBoxLayout()
        row.addWidget(self.info, 1)
        row.addWidget(save)
        row.addWidget(close)
        lay = QVBoxLayout(self)
        lay.addWidget(banner)
        side = QHBoxLayout()
        side.addLayout(form, 1)
        side.addWidget(area, 3)
        lay.addLayout(side, 1)
        lay.addLayout(row)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(120)
        self._timer.timeout.connect(self.render)
        for s in (self.az, self.el, self.intensity, self.ambient, self.emission, self.shadow_opacity):
            s.valueChanged.connect(self._timer.start)
        for c in (self.shadows, self.flip):
            c.toggled.connect(self._timer.start)
        self.bg.currentIndexChanged.connect(self._timer.start)
        self.zoom.valueChanged.connect(self._timer.start)
        self.render()

    def settings(self) -> LightSettings:
        return LightSettings(
            azimuth=float(self.az.value()), elevation=float(self.el.value()),
            intensity=self.intensity.value() / 100, ambient=self.ambient.value() / 100,
            emission=self.emission.value() / 100, shadows=self.shadows.isChecked(),
            shadow_opacity=self.shadow_opacity.value() / 100, flip_green=self.flip.isChecked())

    def render(self) -> bool:
        items, skipped = load_items(self.scene.model.draw_instances(), self.scene.library)
        try:
            self.image, _ = render_lit(items, self.settings(), self.bg.currentData(), self.zoom.value())
        except ValueError as exc:
            self.image = None
            self.view.clear()
            self.info.setText(str(exc))
            return False
        self.view.setPixmap(QPixmap.fromImage(to_qimage(self.image)))
        extra = f" — {len(skipped)} image(s) absente(s)" if skipped else ""
        self.info.setText(f"{len(items)} objet(s){extra}")
        return True

    def save_png(self) -> bool:
        if self.image is None:
            return False
        path, _ = QFileDialog.getSaveFileName(self, "Enregistrer l'aperçu", "apercu_eclaire.png", "Image PNG (*.png)")
        if not path:
            return False
        try:
            self.image.save(Path(path), format="PNG")
        except OSError as exc:
            QMessageBox.warning(self, "Enregistrement impossible", str(exc))
            return False
        return True
