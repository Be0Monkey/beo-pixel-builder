"""Vue du canevas : damier, zoom net, déplacement de la vue, sélection, glisser avec aimantation,
guides d'alignement, groupes, dépôt depuis la bibliothèque."""

import math

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QAction, QBrush, QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QGraphicsView, QMenu

from sbs.canvas.mime import ASSET_MIME
from sbs.canvas.scene import CanvasScene

ZOOM_LEVELS = [0.25, 0.5, 1.0, 2.0, 3.0, 4.0, 6.0, 8.0, 12.0, 16.0]
DEFAULT_ZOOM_INDEX = 3  # 200 %
CHECKER = 8  # px de scène par case du damier


def _checker_brush() -> QBrush:
    pm = QPixmap(2 * CHECKER, 2 * CHECKER)
    pm.fill(QColor(206, 206, 206))
    p = QPainter(pm)
    dark = QColor(172, 172, 172)
    p.fillRect(0, 0, CHECKER, CHECKER, dark)
    p.fillRect(CHECKER, CHECKER, CHECKER, CHECKER, dark)
    p.end()
    return QBrush(pm)


class _Drag:
    """État d'un glissement d'objets à la souris."""

    def __init__(self, press: QPointF, starts: dict[str, QPointF], boxes: list[tuple[int, int, int, int]],
                 primary_pivot: tuple[int, int], points: list[tuple[int, int]] | None = None):
        self.press = press
        self.starts = starts
        self.boxes = boxes
        self.primary_pivot = primary_pivot
        self.points = points or []


class CanvasView(QGraphicsView):
    mouse_moved = Signal(int, int)
    zoom_changed = Signal(float)

    def __init__(self, scene: CanvasScene):
        super().__init__(scene)
        self.canvas_scene = scene
        self.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)  # voisin le plus proche
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setMouseTracking(True)
        self.setAcceptDrops(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._brush = _checker_brush()
        self.show_grid = False
        self._zoom_index = DEFAULT_ZOOM_INDEX
        self._panning = False
        self._last_pan = None
        self._drag: _Drag | None = None
        self.scale(self.zoom, self.zoom)
        self.centerOn(0, 0)

    # --- zoom -------------------------------------------------------------------
    @property
    def zoom(self) -> float:
        return ZOOM_LEVELS[self._zoom_index]

    def set_zoom_index(self, index: int) -> None:
        index = max(0, min(len(ZOOM_LEVELS) - 1, index))
        if index == self._zoom_index:
            return
        ratio = ZOOM_LEVELS[index] / self.zoom
        self._zoom_index = index
        self.scale(ratio, ratio)
        self.zoom_changed.emit(self.zoom)

    def zoom_in(self) -> None:
        self.set_zoom_index(self._zoom_index + 1)

    def zoom_out(self) -> None:
        self.set_zoom_index(self._zoom_index - 1)

    def zoom_reset(self) -> None:
        self.set_zoom_index(DEFAULT_ZOOM_INDEX)

    def wheelEvent(self, event) -> None:
        dy = event.angleDelta().y()
        if dy > 0:
            self.zoom_in()
        elif dy < 0:
            self.zoom_out()
        event.accept()

    # --- affichage --------------------------------------------------------------
    def set_grid_visible(self, visible: bool) -> None:
        self.show_grid = visible
        self.viewport().update()

    def drawBackground(self, painter: QPainter, rect) -> None:
        painter.fillRect(rect, self._brush)
        if self.show_grid:
            g = max(1, self.canvas_scene.snap.grid_size)
            painter.setPen(QPen(QColor(0, 0, 0, 60), 0))
            x = math.floor(rect.left() / g) * g
            while x <= rect.right():
                painter.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))
                x += g
            y = math.floor(rect.top() / g) * g
            while y <= rect.bottom():
                painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
                y += g
        painter.setPen(QPen(QColor(220, 60, 60, 160), 0))  # repères de l'origine
        painter.drawLine(QPointF(rect.left(), 0), QPointF(rect.right(), 0))
        painter.drawLine(QPointF(0, rect.top()), QPointF(0, rect.bottom()))

    def drawForeground(self, painter: QPainter, rect) -> None:
        if not self.canvas_scene.guides:
            return
        painter.setPen(QPen(QColor(255, 0, 200, 220), 0, Qt.PenStyle.DashLine))  # guides d'alignement
        for kind, pos in self.canvas_scene.guides:
            if kind == "v":
                painter.drawLine(QPointF(pos, rect.top()), QPointF(pos, rect.bottom()))
            else:
                painter.drawLine(QPointF(rect.left(), pos), QPointF(rect.right(), pos))

    def visible_scene_rect(self) -> QRectF:
        return self.mapToScene(self.viewport().rect()).boundingRect()

    # --- souris -------------------------------------------------------------------
    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.MiddleButton:
            self._panning = True
            self._last_pan = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        if event.button() == Qt.MouseButton.LeftButton:
            pos = self.mapToScene(event.position().toPoint())
            item = self.canvas_scene.item_at(pos)
            if item is not None:
                if self._begin_drag(item, pos, event.modifiers()):
                    event.accept()
                    return
                event.accept()  # Maj+clic qui désélectionne : pas de glissement
                return
        super().mousePressEvent(event)

    def _begin_drag(self, item, pos: QPointF, mods) -> bool:
        sc = self.canvas_scene
        if mods & Qt.KeyboardModifier.ShiftModifier:  # Maj : ajouter/retirer de la sélection
            if item.isSelected():
                for i in sc.unit_ids(item.inst_id):
                    sc.items_by_id[i].setSelected(False)
                return False
            sc.select_unit_of(item.inst_id, add=True)
        elif not item.isSelected():
            sc.select_unit_of(item.inst_id)
        primary_pivot = item.pivot_position()
        if mods & Qt.KeyboardModifier.ControlModifier:  # Ctrl + glisser : dupliquer puis déplacer
            sc.duplicate_selected(0)
        chosen = [sc.items_by_id[i] for i in sc.selected_ids()]
        self._drag = _Drag(pos, {it.inst_id: QPointF(it.pos()) for it in chosen},
                           [it.box() for it in chosen], primary_pivot,
                           [p for it in chosen for p in sc.anchor_points(it)])
        return True

    def mouseMoveEvent(self, event) -> None:
        p = self.mapToScene(event.position().toPoint())
        self.mouse_moved.emit(math.floor(p.x()), math.floor(p.y()))
        if self._panning:
            d = event.position() - self._last_pan
            self._last_pan = event.position()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - round(d.x()))
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - round(d.y()))
            event.accept()
            return
        if self._drag is not None:
            self._drag_to(p, bool(event.modifiers() & Qt.KeyboardModifier.AltModifier))
            event.accept()
            return
        super().mouseMoveEvent(event)

    def _drag_to(self, p: QPointF, no_snap: bool) -> None:
        d, sc = self._drag, self.canvas_scene
        dx, dy = round(p.x() - d.press.x()), round(p.y() - d.press.y())
        sx = sy = 0
        sc.guides = []
        if not no_snap:  # Alt : aimantation coupée temporairement
            res = sc.snap_delta(d.boxes, d.primary_pivot, dx, dy, self.zoom,
                                self.visible_scene_rect(), set(d.starts), d.points)
            sx, sy, sc.guides = res.dx, res.dy, res.guides
        for inst_id, start in d.starts.items():
            item = sc.items_by_id.get(inst_id)
            if item is not None:
                item.setPos(start.x() + dx + sx, start.y() + dy + sy)
        self.viewport().update()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.MiddleButton and self._panning:
            self._panning = False
            self.unsetCursor()
            event.accept()
            return
        if self._drag is not None and event.button() == Qt.MouseButton.LeftButton:
            self._drag = None
            self.canvas_scene.guides = []
            self.canvas_scene.commit_positions()  # un geste = une commande annulable
            self.viewport().update()
            event.accept()
            return
        super().mouseReleaseEvent(event)
        if event.button() == Qt.MouseButton.LeftButton:
            self.canvas_scene.expand_selection_to_groups()  # rectangle de sélection

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            pos = self.mapToScene(event.position().toPoint())
            if not self.canvas_scene.enter_group_at(pos) and self.canvas_scene.item_at(pos) is None:
                self.canvas_scene.exit_group()  # double-clic dans le vide : on sort du groupe
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    # --- clavier : déplacement précis (jamais aimanté) ---------------------------------
    def keyPressEvent(self, event) -> None:
        step = 8 if event.modifiers() & Qt.KeyboardModifier.ShiftModifier else 1
        moves = {
            Qt.Key.Key_Left: (-step, 0), Qt.Key.Key_Right: (step, 0),
            Qt.Key.Key_Up: (0, -step), Qt.Key.Key_Down: (0, step),
        }
        if event.key() in moves and self.canvas_scene.selected_ids():
            self.canvas_scene.move_selected(*moves[event.key()])
            event.accept()
            return
        if event.key() == Qt.Key.Key_Escape:
            if self.canvas_scene.selected_ids():
                self.canvas_scene.clearSelection()
            else:
                self.canvas_scene.exit_group()
            event.accept()
            return
        super().keyPressEvent(event)

    # --- menu contextuel (clic droit) -----------------------------------------------------
    def contextMenuEvent(self, event) -> None:
        sc = self.canvas_scene
        item = sc.item_at(self.mapToScene(event.pos()))
        if item is not None and not item.isSelected():
            sc.select_unit_of(item.inst_id)
        if not sc.selected_ids():
            return
        menu = QMenu(self)
        menu.addAction(QAction("Mettre devant", menu, triggered=lambda: sc.shift_z_selected(1)))
        menu.addAction(QAction("Mettre derrière", menu, triggered=lambda: sc.shift_z_selected(-1)))
        menu.addAction(QAction("Ordre automatique", menu, triggered=sc.reset_z_selected))
        menu.addSeparator()
        asset = sc.selected_asset()
        if asset is not None and asset.variants:
            vm = menu.addMenu("Variante")
            vm.addAction(QAction("(base)", vm, triggered=lambda: sc.set_variant_selected(None)))
            for v in asset.variants:
                vm.addAction(QAction(v.name, vm, triggered=lambda _=False, n=v.name: sc.set_variant_selected(n)))
            menu.addSeparator()
        menu.addAction(QAction("Grouper", menu, triggered=lambda: sc.group_selected()))
        menu.addAction(QAction("Dégrouper", menu, triggered=sc.ungroup_selected))
        menu.addSeparator()
        menu.addAction(QAction("Supprimer", menu, triggered=sc.remove_selected))
        menu.exec(event.globalPos())

    # --- ajout de modules ------------------------------------------------------------------
    def visible_center(self) -> tuple[int, int]:
        c = self.mapToScene(self.viewport().rect().center())
        return round(c.x()), round(c.y())

    def add_asset_at_center(self, asset_uuid: str):
        return self.canvas_scene.add_asset(asset_uuid, *self.visible_center())

    def handle_drop(self, mime, scene_pos: QPointF):
        if not mime.hasFormat(ASSET_MIME):
            return None
        asset_uuid = bytes(mime.data(ASSET_MIME)).decode("utf-8")
        return self.canvas_scene.add_asset(asset_uuid, round(scene_pos.x()), round(scene_pos.y()))

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasFormat(ASSET_MIME):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:
        self.dragEnterEvent(event)

    def dropEvent(self, event) -> None:
        if self.handle_drop(event.mimeData(), self.mapToScene(event.position().toPoint())):
            event.acceptProposedAction()
            self.setFocus()
        else:
            event.ignore()
