"""Répéter un module : en ligne, en grille ou le long d'un tracé, avec aperçu avant validation."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from sbs.canvas.scene import CanvasScene
from sbs.domain import repeat as R

BIG = 100000


def _spin(lo=-BIG, hi=BIG, value=0) -> QSpinBox:
    s = QSpinBox()
    s.setRange(lo, hi)
    s.setValue(value)
    return s


def parse_points(text: str) -> list[tuple[int, int]]:
    """Une ligne = un point « x, y » (entiers)."""
    pts = []
    for n, line in enumerate(text.splitlines(), 1):
        line = line.strip().replace(";", ",")
        if not line:
            continue
        try:
            x, y = (int(v) for v in line.split(","))
        except ValueError as exc:
            raise ValueError(f"ligne {n} : écris deux entiers « x, y »") from exc
        pts.append((x, y))
    return pts


class RepeatDialog(QDialog):
    def __init__(self, scene: CanvasScene, asset_uuid: str, variant: str | None, origin: tuple[int, int],
                 parent: QWidget | None = None):
        super().__init__(parent)
        self.scene, self.asset_uuid, self.variant = scene, asset_uuid, variant
        asset = scene.library.get(asset_uuid)
        self.setWindowTitle(f"Répéter — {asset.name if asset else '?'}")
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)

        self.mode = QComboBox()
        self.mode.addItem("En ligne", "line")
        self.mode.addItem("En grille", "grid")
        self.mode.addItem("Le long d'un tracé", "path")
        self.mode.addItem("Couvrir une longueur", "cover")
        self.ox, self.oy = _spin(value=origin[0]), _spin(value=origin[1])
        self.count = _spin(1, R.MAX_COUNT, 5)
        self.sx, self.sy = _spin(value=32), _spin(value=0)
        self.cols, self.rows = _spin(1, R.MAX_COUNT, 4), _spin(1, R.MAX_COUNT, 3)
        self.points = QPlainTextEdit()
        self.points.setPlaceholderText("Un point par ligne : x, y")
        self.points.setFixedHeight(70)
        self.smooth = QCheckBox("Tracé lissé (courbe)")
        self.by = QComboBox()
        self.by.addItem("Espacement (px)", "spacing")
        self.by.addItem("Nombre d'objets", "count")
        self.amount = _spin(1, R.MAX_COUNT, 16)
        self.length = _spin(1, 100000, 128)
        self.axis = QComboBox()
        self.axis.addItem("Horizontal (largeur)", "h")
        self.axis.addItem("Vertical (hauteur)", "v")
        self.piece = _spin(1, 100000, max(1, asset.width) if asset else 16)
        self.fit = QComboBox()
        self.fit.addItem("Tout couvrir (la dernière dépasse)", "over")
        self.fit.addItem("Pièces entières seulement (un vide possible)", "within")
        self.fit.addItem("Exact (léger chevauchement, jamais de vide)", "exact")
        self._asset_size = (asset.width, asset.height) if asset else (16, 16)
        self.group = QCheckBox("Grouper le résultat")
        self.info = QLabel("")
        use_sel = QPushButton("Points = objets sélectionnés")
        use_sel.clicked.connect(self.points_from_selection)
        place = QPushButton("Placer")
        place.clicked.connect(self.place)
        close = QPushButton("Fermer")
        close.clicked.connect(self.close)

        form = QFormLayout()
        form.addRow("Type", self.mode)
        self.rows_widgets = {
            "origin": [("Départ X", self.ox), ("Départ Y", self.oy)],
            "line": [("Nombre", self.count), ("Pas X", self.sx), ("Pas Y", self.sy)],
            "grid": [("Colonnes", self.cols), ("Lignes", self.rows)],
            "cover": [("Longueur à couvrir (px)", self.length), ("Sens", self.axis),
                      ("Largeur/hauteur d'une pièce (px)", self.piece), ("Ajustement", self.fit)],
            "path": [("Points du tracé", self.points), ("", self.smooth), ("Répartir par", self.by),
                     ("Valeur", self.amount)],
        }
        self._rows: dict[str, list[tuple[QWidget, QWidget | None]]] = {}
        for key, items in self.rows_widgets.items():
            for label, w in items:
                lab = QLabel(label)
                form.addRow(lab, w)
                self._rows.setdefault(key, []).append((lab, w))
        # la grille réutilise « Pas X / Pas Y » : un seul jeu de champs
        self._rows["grid"] += self._rows["line"][1:]
        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(use_sel)
        lay.addWidget(self.group)
        lay.addWidget(self.info)
        row = QHBoxLayout()
        row.addWidget(place)
        row.addWidget(close)
        lay.addLayout(row)

        for w in (self.ox, self.oy, self.count, self.sx, self.sy, self.cols, self.rows, self.amount,
                  self.length, self.piece):
            w.valueChanged.connect(self.update_preview)
        self.points.textChanged.connect(self.update_preview)
        self.smooth.toggled.connect(self.update_preview)
        self.mode.currentIndexChanged.connect(self._mode_changed)
        self.by.currentIndexChanged.connect(self.update_preview)
        self.fit.currentIndexChanged.connect(self.update_preview)
        self.axis.currentIndexChanged.connect(self._axis_changed)
        self._mode_changed()

    # --- calcul --------------------------------------------------------------------------------------
    def positions(self) -> list[tuple[int, int]]:
        mode = self.mode.currentData()
        origin, step = (self.ox.value(), self.oy.value()), (self.sx.value(), self.sy.value())
        if mode == "line":
            return R.line(origin, self.count.value(), step)
        if mode == "grid":
            return R.grid(origin, self.cols.value(), self.rows.value(), step)
        if mode == "cover":
            return R.cover(origin, self.length.value(), self.piece.value(),
                           self.axis.currentData() == "h", self.fit.currentData())
        pts = parse_points(self.points.toPlainText())
        if self.by.currentData() == "spacing":
            return R.path(pts, self.smooth.isChecked(), spacing=self.amount.value())
        return R.path(pts, self.smooth.isChecked(), count=self.amount.value())

    def _mode_changed(self) -> None:
        mode = self.mode.currentData()
        show = {"origin": mode != "path", "line": mode == "line", "grid": mode == "grid", "path": mode == "path",
                "cover": mode == "cover"}
        shown = set()
        for key, rows in self._rows.items():
            if show[key]:
                shown.update(id(w) for _, w in rows)
        for rows in self._rows.values():
            for lab, w in rows:
                vis = id(w) in shown
                lab.setVisible(vis)
                w.setVisible(vis)
        self.update_preview()

    def _axis_changed(self) -> None:
        """Propose la largeur (sens horizontal) ou la hauteur (sens vertical) du module comme taille de pièce."""
        self.piece.setValue(max(1, self._asset_size[0] if self.axis.currentData() == "h" else self._asset_size[1]))
        self.update_preview()

    def update_preview(self) -> None:
        try:
            pos = self.positions()
        except ValueError as exc:
            self.scene.clear_preview()
            self.info.setText(str(exc))
            return
        n = self.scene.show_preview(self.asset_uuid, self.variant, pos)
        extra = "" if n == len(pos) else f" (aperçu limité à {n})"
        cover = ""
        if self.mode.currentData() == "cover":
            reach = self.length.value() if self.fit.currentData() == "exact" else len(pos) * self.piece.value()
            cover = f" — {reach} px couverts sur {self.length.value()}"
        self.info.setText(f"{len(pos)} objet(s){extra}{cover}")

    def points_from_selection(self) -> None:
        pts = [(i.x, i.y) for i in self.scene.selection_in_model_order()]
        self.points.setPlainText("\n".join(f"{x}, {y}" for x, y in pts))

    def place(self) -> str | None:
        try:
            pos = self.positions()
        except ValueError as exc:
            self.info.setText(str(exc))
            return str(exc)
        err = self.scene.place_repeated(self.asset_uuid, self.variant, pos, self.group.isChecked())
        self.info.setText(err or f"{len(pos)} objet(s) placé(s) (Ctrl+Z pour annuler).")
        return err

    def done(self, result: int) -> None:
        self.scene.clear_preview()
        super().done(result)
