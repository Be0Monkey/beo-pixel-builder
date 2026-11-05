"""Historique annuler / rétablir. Un geste continu = une seule entrée."""

import time
from collections.abc import Callable

from sbs.commands.base import Command
from sbs.domain.scene import SceneModel


class History:
    def __init__(self, model: SceneModel, limit: int = 1000,
                 clock: Callable[[], float] = time.monotonic, merge_window: float = 0.8):
        self.model = model
        self.limit = limit
        self._clock = clock
        self._merge_window = merge_window
        self._stack: list[Command] = []
        self._pos = 0  # commandes appliquées = _stack[:_pos] ; à rétablir = _stack[_pos:]
        self._saved_pos: int | None = 0  # None : l'état enregistré n'est plus atteignable
        self._last_time = float("-inf")
        self._listeners: list[Callable[[], None]] = []

    # --- observateurs -------------------------------------------------------------
    def add_listener(self, fn: Callable[[], None]) -> None:
        self._listeners.append(fn)

    def _changed(self) -> None:
        for fn in list(self._listeners):
            fn()

    # --- état ---------------------------------------------------------------------
    @property
    def can_undo(self) -> bool:
        return self._pos > 0

    @property
    def can_redo(self) -> bool:
        return self._pos < len(self._stack)

    @property
    def undo_name(self) -> str | None:
        return self._stack[self._pos - 1].name if self.can_undo else None

    @property
    def redo_name(self) -> str | None:
        return self._stack[self._pos].name if self.can_redo else None

    @property
    def dirty(self) -> bool:
        return self._saved_pos is None or self._pos != self._saved_pos

    def mark_saved(self) -> None:
        self._saved_pos = self._pos
        self._changed()

    def mark_dirty(self) -> None:
        self._saved_pos = None
        self._changed()

    def clear(self) -> None:
        """Nouveau document ou projet ouvert : on repart d'un historique vide et propre."""
        self._stack, self._pos, self._saved_pos = [], 0, 0
        self._changed()

    # --- actions ------------------------------------------------------------------
    def execute(self, cmd: Command) -> None:
        with self.model.batch():
            cmd.do(self.model)
        now = self._clock()
        if (cmd.mergeable and self._pos > 0 and self._pos == len(self._stack)
                and self._pos != self._saved_pos
                and now - self._last_time <= self._merge_window
                and self._stack[self._pos - 1].merge(cmd)):
            self._last_time = now
            self._changed()
            return
        del self._stack[self._pos:]  # la branche « rétablir » est perdue
        if self._saved_pos is not None and self._saved_pos > self._pos:
            self._saved_pos = None
        self._stack.append(cmd)
        self._pos += 1
        if len(self._stack) > self.limit:
            drop = len(self._stack) - self.limit
            del self._stack[:drop]
            self._pos -= drop
            if self._saved_pos is not None:
                self._saved_pos -= drop
                if self._saved_pos < 0:
                    self._saved_pos = None
        self._last_time = now
        self._changed()

    def undo(self) -> Command | None:
        if not self.can_undo:
            return None
        cmd = self._stack[self._pos - 1]
        with self.model.batch():
            cmd.undo(self.model)
        self._pos -= 1
        self._last_time = float("-inf")  # plus de fusion avec ce qui précède
        self._changed()
        return cmd

    def redo(self) -> Command | None:
        if not self.can_redo:
            return None
        cmd = self._stack[self._pos]
        with self.model.batch():
            cmd.do(self.model)
        self._pos += 1
        self._last_time = float("-inf")
        self._changed()
        return cmd
