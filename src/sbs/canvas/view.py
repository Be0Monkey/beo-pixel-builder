"""Vue du canevas : damier, zoom net, déplacement de la vue, sélection, dépôt depuis la bibliothèque."""

import math

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPen, QPixmap
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QGraphicsView, QMenu

from sbs.canvas.mime import ASSET_MIME
from sbs.canvas.scene import CanvasScene

ZOOM_LEVELS = [0.25, 0.5, 1.0, 2.0, 3.0, 4.0, 6.0, 8.0, 12.0, 16.0]
DEFAULT_ZOOM_INDEX = 3  # 200 %
CHECKER = 8  # px de scène par case du damier
GRID = 32  # case de grille de référence du kit (décision D-A)


def _checker_brush() -> QBrush:
    pm = QPixmap(2 * CHECKER, 2 * CHECKER)
    pm.fill(QColor(206, 206, 206))
    p = QPainter(pm)
    dark = QColor(172, 172, 172)
    p.fillRect(0, 0, CHECKER, CHECKER, dark)
    p.fillRect(CHECKER, CHECKER, CHECKER, CHECKER, dark)
    p.end()
    return QBrush(pm)


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
            painter.setPen(QPen(QColor(0, 0, 0, 60), 0))
            x = math.floor(rect.left() / GRID) * GRID
            while x <= rect.right():
                painter.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))
                x += GRID
            y = math.floor(rect.top() / GRID) * GRID
            while y <= rect.bottom():
                painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
                y += GRID
        painter.setPen(QPen(QColor(220, 60, 60, 160), 0))  # repères de l'origine
        painter.drawLine(QPointF(rect.left(), 0), QPointF(rect.right(), 0))
        painter.drawLine(QPointF(0, rect.top()), QPointF(0, rect.bottom()))

    # --- souris : déplacement de la vue (bouton du milieu), sélection, déplacement ------
    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.MiddleButton:
            self._panning = True
            self._last_pan = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

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
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.MiddleButton and self._panning:
            self._panning = False
            self.unsetCursor()
            event.accept()
            return
        super().mouseReleaseEvent(event)
        self.canvas_scene.commit_positions()  # un geste = une mise à jour du modèle

    # --- clavier : déplacement précis ---------------------------------------------------
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
            self.canvas_scene.clearSelection()
            event.accept()
            return
        super().keyPressEvent(event)

    # --- menu contextuel (clic droit) -------------------------------------------------------
    def contextMenuEvent(self, event) -> None:
        item = self.itemAt(event.pos())
        if item is not None and not item.isSelected():
            self.canvas_scene.clearSelection()
            item.setSelected(True)
        if not self.canvas_scene.selected_ids():
            return
        sc = self.canvas_scene
        menu = QMenu(self)
        menu.addAction(QAction("Mettre devant", menu, triggered=lambda: sc.shift_z_selected(1)))
        menu.addAction(QAction("Mettre derrière", menu, triggered=lambda: sc.shift_z_selected(-1)))
        menu.addAction(QAction("Ordre automatique", menu, triggered=sc.reset_z_selected))
        menu.addSeparator()
        menu.addAction(QAction("Supprimer", menu, triggered=sc.remove_selected))
        menu.exec(event.globalPos())

    # --- ajout de modules -----------------------------------------------------------------
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
