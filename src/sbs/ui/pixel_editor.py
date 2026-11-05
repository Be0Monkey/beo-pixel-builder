"""Atelier Pixel Art : outils (crayon, gomme, pipette, remplissage, sélection), palette, calques.

Zoom entier uniquement, pixels nets. Le dessin passe par PixelEditor (testé sans interface)."""

from PySide6.QtCore import QPointF, QRect, QSize, Qt
from PySide6.QtGui import QColor, QImage, QKeySequence, QPainter, QPen, QShortcut
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QColorDialog,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from sbs.domain.pixel_edit import PixelEditor

TOOL_LABELS = {"pencil": ("Crayon", "B"), "eraser": ("Gomme", "E"), "picker": ("Pipette", "I"),
               "fill": ("Remplir", "G"), "select": ("Sélection", "M")}
ROLE = Qt.ItemDataRole.UserRole


class PixelCanvas(QWidget):
    def __init__(self, editor: PixelEditor, on_change, parent: QWidget | None = None):
        super().__init__(parent)
        self.editor = editor
        self.on_change = on_change
        self.zoom = 8
        self.show_grid = True
        self._down = False
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._resize()

    def _resize(self) -> None:
        d = self.editor.doc
        self.setFixedSize(d.width * self.zoom, d.height * self.zoom)
        self.update()

    def set_zoom(self, z: int) -> None:
        self.zoom = max(1, min(64, int(z)))
        self._resize()

    def pixel_at(self, pos: QPointF) -> tuple[int, int]:
        return int(pos.x() // self.zoom), int(pos.y() // self.zoom)

    # --- dessin --------------------------------------------------------------------------------------
    def paintEvent(self, _event) -> None:
        d, z = self.editor.doc, self.zoom
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        cell = max(4, z // 2 * 2) if z < 8 else 8
        for y in range(0, d.height * z, cell):  # damier de transparence
            for x in range(0, d.width * z, cell):
                light = ((x // cell) + (y // cell)) % 2 == 0
                p.fillRect(x, y, cell, cell, QColor(204, 204, 204) if light else QColor(245, 245, 245))
        flat = d.flatten_image()
        img = QImage(flat.tobytes(), d.width, d.height, d.width * 4, QImage.Format.Format_RGBA8888)
        p.drawImage(QRect(0, 0, d.width * z, d.height * z), img)
        if self.show_grid and z >= 6:
            p.setPen(QPen(QColor(0, 0, 0, 40), 1))
            for x in range(0, d.width + 1):
                p.drawLine(x * z, 0, x * z, d.height * z)
            for y in range(0, d.height + 1):
                p.drawLine(0, y * z, d.width * z, y * z)
        sel = self.editor.selection
        if sel:
            pen = QPen(QColor(255, 255, 255), 1, Qt.PenStyle.DashLine)
            p.setPen(QPen(QColor(0, 0, 0), 3))
            r = QRect(sel[0] * z, sel[1] * z, (sel[2] - sel[0] + 1) * z, (sel[3] - sel[1] + 1) * z)
            p.drawRect(r)
            p.setPen(pen)
            p.drawRect(r)
        p.end()

    # --- souris --------------------------------------------------------------------------------------
    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            self._down = True
            self.editor.begin(*self.pixel_at(e.position()))
            self.on_change()

    def mouseMoveEvent(self, e) -> None:
        if self._down:
            self.editor.move(*self.pixel_at(e.position()))
            self.update()

    def mouseReleaseEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton and self._down:
            self._down = False
            self.editor.end()
            self.on_change()

    def wheelEvent(self, e) -> None:
        if e.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.set_zoom(self.zoom + (1 if e.angleDelta().y() > 0 else -1))
            e.accept()
        else:
            super().wheelEvent(e)


class PixelEditorDialog(QDialog):
    def __init__(self, editor: PixelEditor, title: str = "Atelier Pixel Art", note: str = "",
                 parent: QWidget | None = None):
        super().__init__(parent)
        self.editor = editor
        self.setWindowTitle(title)
        self.resize(1000, 700)
        self.canvas = PixelCanvas(editor, self.refresh)

        # outils
        tools = QVBoxLayout()
        self.tool_buttons = QButtonGroup(self)
        self.tool_buttons.setExclusive(True)
        for name, (label, key) in TOOL_LABELS.items():
            b = QToolButton()
            b.setText(f"{label} ({key})")
            b.setCheckable(True)
            b.setChecked(name == editor.tool)
            b.clicked.connect(lambda _=False, n=name: self.set_tool(n))
            self.tool_buttons.addButton(b)
            tools.addWidget(b)
            QShortcut(QKeySequence(key), self, activated=lambda n=name: self.set_tool(n))
        self.color_button = QPushButton("Couleur…")
        self.color_button.clicked.connect(self.pick_color)
        add_pal = QPushButton("+ Palette")
        add_pal.clicked.connect(lambda: (editor.add_to_palette(), self.refresh()))
        tools.addWidget(self.color_button)
        tools.addWidget(add_pal)
        self.palette_grid = QGridLayout()
        self.palette_grid.setSpacing(2)
        tools.addLayout(self.palette_grid)
        tools.addStretch(1)

        # calques
        self.layer_list = QListWidget()
        self.layer_list.itemChanged.connect(self._layer_item_changed)
        self.layer_list.currentItemChanged.connect(self._layer_selected)
        layer_btns = QGridLayout()
        for n, (text, fn) in enumerate([
            ("+ Calque", editor.add_layer), ("Dupliquer", editor.duplicate_layer),
            ("Supprimer", editor.remove_layer), ("Monter", lambda: editor.move_layer(+1)),
            ("Descendre", lambda: editor.move_layer(-1)), ("Verrouiller", self._toggle_lock)]):
            b = QPushButton(text)
            b.clicked.connect(lambda _=False, f=fn: (f(), self.refresh()))
            layer_btns.addWidget(b, n // 2, n % 2)
        side = QVBoxLayout()
        side.addWidget(QLabel("Calques (case = visible)"))
        side.addWidget(self.layer_list, 1)
        side.addLayout(layer_btns)

        # bas
        self.undo_btn, self.redo_btn = QPushButton("Annuler"), QPushButton("Rétablir")
        self.undo_btn.clicked.connect(lambda: (editor.undo(), self.refresh()))
        self.redo_btn.clicked.connect(lambda: (editor.redo(), self.refresh()))
        self.zoom_spin = QSpinBox()
        self.zoom_spin.setRange(1, 64)
        self.zoom_spin.setValue(self.canvas.zoom)
        self.zoom_spin.setSuffix(" ×")
        self.zoom_spin.valueChanged.connect(self.canvas.set_zoom)
        self.grid_box = QCheckBox("Grille")
        self.grid_box.setChecked(True)
        self.grid_box.toggled.connect(lambda v: (setattr(self.canvas, "show_grid", v), self.canvas.update()))
        self.status = QLabel(note)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Appliquer…")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        bottom = QHBoxLayout()
        for w in (self.undo_btn, self.redo_btn, QLabel("Zoom"), self.zoom_spin, self.grid_box):
            bottom.addWidget(w)
        bottom.addWidget(self.status, 1)
        bottom.addWidget(buttons)

        scroll = QScrollArea()
        scroll.setWidget(self.canvas)
        scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top = QHBoxLayout()
        top.addLayout(tools)
        top.addWidget(scroll, 1)
        top.addLayout(side)
        lay = QVBoxLayout(self)
        lay.addLayout(top, 1)
        lay.addLayout(bottom)

        QShortcut(QKeySequence("Ctrl+Z"), self, activated=lambda: (editor.undo(), self.refresh()))
        QShortcut(QKeySequence("Ctrl+Y"), self, activated=lambda: (editor.redo(), self.refresh()))
        QShortcut(QKeySequence("Ctrl+A"), self, activated=lambda: (editor.select_all(), self.refresh()))
        QShortcut(QKeySequence("Esc"), self, activated=lambda: (editor.clear_selection(), self.refresh()))
        QShortcut(QKeySequence("Delete"), self, activated=lambda: (editor.delete_selection(), self.refresh()))
        for key, dx, dy in (("Left", -1, 0), ("Right", 1, 0), ("Up", 0, -1), ("Down", 0, 1)):
            QShortcut(QKeySequence(key), self, activated=lambda a=dx, b=dy: (editor.move_selection(a, b), self.refresh()))
        self.refresh()

    # --- actions ------------------------------------------------------------------------------------
    def set_tool(self, name: str) -> None:
        self.editor.tool = name
        for b in self.tool_buttons.buttons():
            b.setChecked(b.text().startswith(TOOL_LABELS[name][0]))

    def pick_color(self) -> None:
        c = self.editor.color
        chosen = QColorDialog.getColor(QColor(*c), self, "Couleur", QColorDialog.ColorDialogOption.ShowAlphaChannel)
        if chosen.isValid():
            self.editor.set_color((chosen.red(), chosen.green(), chosen.blue(), chosen.alpha()))
            self.refresh()

    def _toggle_lock(self) -> None:
        layer = self.editor.doc.active
        self.editor.set_layer_locked(layer.id, not layer.locked)

    def _layer_item_changed(self, item: QListWidgetItem) -> None:
        if getattr(self, "_building", False):
            return
        lid = item.data(ROLE)
        layer = self.editor.doc.layer(lid)
        if layer is not None and (item.checkState() == Qt.CheckState.Checked) != layer.visible:
            self.editor.set_layer_visible(lid, item.checkState() == Qt.CheckState.Checked)
            self.refresh()

    def _layer_selected(self, current, _prev) -> None:
        if current is not None and not getattr(self, "_building", False):
            self.editor.set_active(current.data(ROLE))
            self.refresh()

    def refresh(self) -> None:
        e = self.editor
        self._building = True
        try:
            self.layer_list.clear()
            for layer in reversed(e.doc.layers):  # le plus haut en premier
                it = QListWidgetItem(layer.name + ("  🔒" if layer.locked else ""))
                it.setData(ROLE, layer.id)
                it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                it.setCheckState(Qt.CheckState.Checked if layer.visible else Qt.CheckState.Unchecked)
                self.layer_list.addItem(it)
                if layer.id == e.doc.active_id:
                    self.layer_list.setCurrentItem(it)
            while self.palette_grid.count():
                self.palette_grid.takeAt(0).widget().deleteLater()
            for n, c in enumerate(e.palette):
                b = QPushButton()
                b.setFixedSize(QSize(20, 20))
                b.setStyleSheet(f"background: rgba({c[0]},{c[1]},{c[2]},{c[3] / 255}); border: 1px solid #555")
                b.setToolTip(f"R{c[0]} V{c[1]} B{c[2]} A{c[3]}")
                b.clicked.connect(lambda _=False, col=c: (e.set_color(col), self.refresh()))
                self.palette_grid.addWidget(b, n // 4, n % 4)
        finally:
            self._building = False
        c = e.color
        self.color_button.setStyleSheet(f"background: rgba({c[0]},{c[1]},{c[2]},{c[3] / 255}); padding: 6px")
        self.undo_btn.setEnabled(e.can_undo)
        self.redo_btn.setEnabled(e.can_redo)
        msg = e.error or ""
        if e.selection:
            s = e.selection
            msg = f"Sélection {s[2] - s[0] + 1}×{s[3] - s[1] + 1}  " + msg
        self.status.setText(msg)
        self.canvas.update()
