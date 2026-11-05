"""Cache des images affichées. Image manquante ou illisible : repère clair, jamais de plantage."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPixmap

from sbs.domain.asset import Asset
from sbs.services.library import Library


def _placeholder() -> QPixmap:
    pm = QPixmap(16, 16)
    pm.fill(QColor(255, 0, 255, 160))
    p = QPainter(pm)
    p.setPen(QColor(0, 0, 0))
    p.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter, "?")
    p.end()
    return pm


class PixmapCache:
    def __init__(self, library: Library):
        self.library = library
        self._cache: dict[str, QPixmap] = {}
        self._placeholder = _placeholder()

    def get(self, asset: Asset | None, variant: str | None = None) -> QPixmap:
        if asset is None:
            return self._placeholder
        key = asset.image_for(variant)
        if key not in self._cache:
            pm = QPixmap(str(self.library.abs_path(key)))
            self._cache[key] = pm if not pm.isNull() else self._placeholder
        return self._cache[key]
