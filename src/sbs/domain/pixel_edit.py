"""Moteur d'édition Pixel Art (sans Qt) : outils, sélection, calques, palette, annuler/rétablir.

Outils : "pencil", "eraser", "picker", "fill", "select". Un geste (glisser) = une commande annulable.
Un calque masqué ou verrouillé ne peut pas être modifié ; la sélection limite pinceau, gomme,
remplissage, suppression et déplacement.
"""

from copy import deepcopy

from sbs.domain.ids import new_id
from sbs.domain.pixel import CLEAR, MAX_LAYERS, RGBA, PixelDoc, PixLayer

TOOLS = ("pencil", "eraser", "picker", "fill", "select")
MAX_PALETTE = 64
DEFAULT_PALETTE: list[RGBA] = [
    (0, 0, 0, 255), (255, 255, 255, 255), (157, 157, 157, 255), (90, 60, 40, 255),
    (190, 38, 51, 255), (224, 111, 139, 255), (235, 137, 49, 255), (247, 226, 107, 255),
    (164, 100, 34, 255), (68, 137, 26, 255), (163, 206, 39, 255), (0, 87, 132, 255),
    (49, 162, 242, 255), (178, 220, 239, 255), (47, 72, 78, 255), (136, 70, 160, 255),
]


def check_color(c) -> RGBA:
    if not (isinstance(c, (tuple, list)) and len(c) == 4
            and all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 255 for v in c)):
        raise ValueError("une couleur est formée de 4 entiers de 0 à 255 (R, G, B, A)")
    return tuple(c)  # type: ignore[return-value]


def line_points(x0: int, y0: int, x1: int, y1: int):
    """Bresenham : tous les pixels entre deux points (pas de trous quand la souris va vite)."""
    dx, dy = abs(x1 - x0), -abs(y1 - y0)
    sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
    err = dx + dy
    while True:
        yield x0, y0
        if x0 == x1 and y0 == y1:
            return
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


class _Entry:
    def __init__(self, name: str, layer_id: str | None = None, changes=None, before=None, after=None):
        self.name, self.layer_id = name, layer_id
        self.changes: dict[int, tuple[bytes, bytes]] = changes or {}
        self.before, self.after = before, after  # états de structure (calques)


class PixelEditor:
    def __init__(self, doc: PixelDoc, palette: list[RGBA] | None = None):
        self.doc = doc
        self.tool = "pencil"
        self.color: RGBA = (0, 0, 0, 255)
        self.palette: list[RGBA] = [check_color(c) for c in (palette or DEFAULT_PALETTE)][:MAX_PALETTE]
        self.selection: tuple[int, int, int, int] | None = None  # x0, y0, x1, y1 inclus
        self.error = ""
        self._stack: list[_Entry] = []
        self._pos = 0
        self._saved = 0
        self._stroke: dict[int, tuple[bytes, bytes]] | None = None
        self._stroke_layer: PixLayer | None = None
        self._last: tuple[int, int] | None = None
        self._sel_anchor: tuple[int, int] | None = None

    # --- historique ---------------------------------------------------------------------------
    @property
    def modified(self) -> bool:
        return self._pos != self._saved

    def mark_saved(self) -> None:
        self._saved = self._pos

    @property
    def can_undo(self) -> bool:
        return self._pos > 0

    @property
    def can_redo(self) -> bool:
        return self._pos < len(self._stack)

    def _push(self, entry: _Entry) -> None:
        del self._stack[self._pos:]
        if self._saved > self._pos:
            self._saved = -1  # l'état enregistré n'est plus atteignable
        self._stack.append(entry)
        self._pos += 1

    def undo(self) -> bool:
        if not self.can_undo:
            return False
        self._pos -= 1
        self._apply(self._stack[self._pos], undo=True)
        return True

    def redo(self) -> bool:
        if not self.can_redo:
            return False
        self._apply(self._stack[self._pos], undo=False)
        self._pos += 1
        return True

    def _apply(self, e: _Entry, undo: bool) -> None:
        if e.before is not None:
            self._restore(e.before if undo else e.after)
            return
        layer = self.doc.layer(e.layer_id)
        if layer is None:
            return
        for i, (old, new) in e.changes.items():
            layer.data[i:i + 4] = old if undo else new

    def _state(self):
        return ([(layer.id, layer.name, layer.visible, layer.locked, bytes(layer.data))
                 for layer in self.doc.layers], self.doc.active_id)

    def _restore(self, state) -> None:
        layers, active = state
        w, h = self.doc.width, self.doc.height
        self.doc.layers = [PixLayer(w, h, n, i, v, lk, d) for i, n, v, lk, d in layers]
        self.doc.active_id = active

    # --- calques --------------------------------------------------------------------------------
    def _structure(self, name: str, fn) -> bool:
        before = self._state()
        try:
            fn()
        except ValueError as exc:
            self._restore(before)
            self.error = str(exc)
            return False
        self._push(_Entry(name, before=before, after=self._state()))
        return True

    def add_layer(self, name: str | None = None) -> bool:
        def fn():
            if len(self.doc.layers) >= MAX_LAYERS:
                raise ValueError(f"{MAX_LAYERS} calques au maximum")
            idx = self.doc.layers.index(self.doc.active) + 1
            layer = PixLayer(self.doc.width, self.doc.height, name or f"Calque {len(self.doc.layers) + 1}")
            self.doc.layers.insert(idx, layer)
            self.doc.active_id = layer.id
        return self._structure("Ajouter un calque", fn)

    def duplicate_layer(self) -> bool:
        def fn():
            if len(self.doc.layers) >= MAX_LAYERS:
                raise ValueError(f"{MAX_LAYERS} calques au maximum")
            src = self.doc.active
            dup = PixLayer(self.doc.width, self.doc.height, src.name + " (copie)", None,
                           src.visible, False, bytes(src.data))
            self.doc.layers.insert(self.doc.layers.index(src) + 1, dup)
            self.doc.active_id = dup.id
        return self._structure("Dupliquer le calque", fn)

    def remove_layer(self) -> bool:
        def fn():
            if len(self.doc.layers) <= 1:
                raise ValueError("il faut garder au moins un calque")
            idx = self.doc.layers.index(self.doc.active)
            del self.doc.layers[idx]
            self.doc.active_id = self.doc.layers[min(idx, len(self.doc.layers) - 1)].id
        return self._structure("Supprimer le calque", fn)

    def rename_layer(self, name: str) -> bool:
        name = " ".join(name.split())
        if not name:
            self.error = "le nom ne peut pas être vide"
            return False
        return self._structure("Renommer le calque", lambda: setattr(self.doc.active, "name", name))

    def set_layer_visible(self, layer_id: str, value: bool) -> bool:
        layer = self.doc.layer(layer_id)
        return layer is not None and self._structure(
            "Afficher/masquer", lambda: setattr(layer, "visible", bool(value)))

    def set_layer_locked(self, layer_id: str, value: bool) -> bool:
        layer = self.doc.layer(layer_id)
        return layer is not None and self._structure(
            "Verrouiller", lambda: setattr(layer, "locked", bool(value)))

    def move_layer(self, delta: int) -> bool:
        def fn():
            idx = self.doc.layers.index(self.doc.active)
            new = idx + delta
            if not (0 <= new < len(self.doc.layers)):
                raise ValueError("déjà au bout de la pile")
            self.doc.layers.insert(new, self.doc.layers.pop(idx))
        return self._structure("Déplacer le calque", fn)

    def set_active(self, layer_id: str) -> bool:
        if self.doc.layer(layer_id) is None:
            return False
        self.doc.active_id = layer_id
        return True

    # --- palette / couleur ----------------------------------------------------------------------
    def set_color(self, color) -> None:
        self.color = check_color(color)

    def add_to_palette(self, color=None) -> bool:
        c = check_color(color or self.color)
        if c in self.palette or len(self.palette) >= MAX_PALETTE:
            return False
        self.palette.append(c)
        return True

    # --- sélection ----------------------------------------------------------------------------------
    def _clamp(self, x: int, y: int) -> tuple[int, int]:
        return min(max(x, 0), self.doc.width - 1), min(max(y, 0), self.doc.height - 1)

    def set_selection(self, x0: int, y0: int, x1: int, y1: int) -> None:
        a, b = self._clamp(min(x0, x1), min(y0, y1)), self._clamp(max(x0, x1), max(y0, y1))
        self.selection = (a[0], a[1], b[0], b[1])

    def select_all(self) -> None:
        self.selection = (0, 0, self.doc.width - 1, self.doc.height - 1)

    def clear_selection(self) -> None:
        self.selection = None

    def _allowed(self, x: int, y: int) -> bool:
        if not self.doc.inside(x, y):
            return False
        if self.selection is None:
            return True
        x0, y0, x1, y1 = self.selection
        return x0 <= x <= x1 and y0 <= y <= y1

    # --- écriture contrôlée -----------------------------------------------------------------------------
    def _editable_layer(self) -> PixLayer | None:
        layer = self.doc.active
        if not layer.visible:
            self.error = "le calque actif est masqué"
            return None
        if layer.locked:
            self.error = "le calque actif est verrouillé"
            return None
        self.error = ""
        return layer

    def _put(self, layer: PixLayer, x: int, y: int, rgba: RGBA, changes: dict) -> None:
        i = self.doc.index(x, y)
        old = bytes(layer.data[i:i + 4])
        new = bytes(rgba)
        if old != new:
            changes.setdefault(i, (old, new))
            changes[i] = (changes[i][0], new)
            layer.data[i:i + 4] = new

    def _commit(self, name: str, layer: PixLayer, changes: dict) -> bool:
        changes = {i: c for i, c in changes.items() if c[0] != c[1]}
        if not changes:
            return False
        self._push(_Entry(name, layer.id, changes))
        return True

    # --- gestes de souris --------------------------------------------------------------------------
    def begin(self, x: int, y: int) -> bool:
        """Début d'un geste. Renvoie True si quelque chose a été fait ou démarré."""
        tool = self.tool
        if tool == "select":
            self._sel_anchor = self._clamp(x, y)
            self.selection = (*self._sel_anchor, *self._sel_anchor)
            return True
        if tool == "picker":
            if not self.doc.inside(x, y):
                return False
            c = self.doc.flatten_get(x, y)
            if c[3] == 0:
                self.error = "pixel transparent : rien à prélever"
                return False
            self.color = c
            return True
        layer = self._editable_layer()
        if layer is None:
            return False
        if tool == "fill":
            return self._fill(layer, x, y)
        self._stroke, self._stroke_layer, self._last = {}, layer, (x, y)
        self._paint(x, y)
        return True

    def move(self, x: int, y: int) -> None:
        if self.tool == "select" and self._sel_anchor is not None:
            self.set_selection(*self._sel_anchor, x, y)
        elif self._stroke is not None and self._last is not None:
            for px, py in line_points(*self._last, x, y):
                self._paint(px, py)
            self._last = (x, y)

    def end(self) -> bool:
        if self.tool == "select":
            self._sel_anchor = None
            return False
        if self._stroke is None:
            return False
        name = "Gomme" if self.tool == "eraser" else "Crayon"
        done = self._commit(name, self._stroke_layer, self._stroke)
        self._stroke = self._stroke_layer = self._last = None
        return done

    def _paint(self, x: int, y: int) -> None:
        if self._allowed(x, y):
            self._put(self._stroke_layer, x, y, CLEAR if self.tool == "eraser" else self.color, self._stroke)

    def _fill(self, layer: PixLayer, x: int, y: int) -> bool:
        if not self._allowed(x, y):
            return False
        target = self.doc.get(layer, x, y)
        if target == self.color:
            return False
        changes: dict[int, tuple[bytes, bytes]] = {}
        todo, seen = [(x, y)], {(x, y)}
        while todo:
            cx, cy = todo.pop()
            self._put(layer, cx, cy, self.color, changes)
            for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                if (nx, ny) not in seen and self._allowed(nx, ny) and self.doc.get(layer, nx, ny) == target:
                    seen.add((nx, ny))
                    todo.append((nx, ny))
        return self._commit("Remplir", layer, changes)

    # --- actions sur la sélection ---------------------------------------------------------------------
    def delete_selection(self) -> bool:
        if self.selection is None:
            self.error = "aucune sélection"
            return False
        layer = self._editable_layer()
        if layer is None:
            return False
        x0, y0, x1, y1 = self.selection
        changes: dict[int, tuple[bytes, bytes]] = {}
        for yy in range(y0, y1 + 1):
            for xx in range(x0, x1 + 1):
                self._put(layer, xx, yy, CLEAR, changes)
        return self._commit("Effacer la sélection", layer, changes)

    def move_selection(self, dx: int, dy: int) -> bool:
        """Déplace le contenu du calque actif dans la sélection (la sélection suit). Ce qui sort est perdu."""
        if self.selection is None:
            self.error = "aucune sélection"
            return False
        layer = self._editable_layer()
        if layer is None:
            return False
        x0, y0, x1, y1 = self.selection
        lifted = {(xx + dx, yy + dy): self.doc.get(layer, xx, yy)
                  for yy in range(y0, y1 + 1) for xx in range(x0, x1 + 1)}
        changes: dict[int, tuple[bytes, bytes]] = {}
        for yy in range(y0, y1 + 1):
            for xx in range(x0, x1 + 1):
                self._put(layer, xx, yy, CLEAR, changes)
        for (xx, yy), rgba in lifted.items():
            if self.doc.inside(xx, yy):
                self._put(layer, xx, yy, rgba, changes)
        before = self.selection
        self.selection = (x0 + dx, y0 + dy, x1 + dx, y1 + dy)
        if not self._commit("Déplacer la sélection", layer, changes):
            self.selection = before
            return False
        return True

    def snapshot_layers(self):
        return deepcopy(self._state())

    def new_id(self) -> str:  # pour les tests et l'interface
        return new_id()
