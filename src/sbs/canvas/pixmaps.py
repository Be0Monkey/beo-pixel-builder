"""Cache des images affichées. Image manquante ou illisible : repère clair, jamais de plantage."""

from collections import OrderedDict

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
    """Images chargées, gardées en mémoire dans la limite de `max_bytes` (les moins récemment
    utilisées sont oubliées ; les objets qui les affichent gardent leur propre référence)."""

    def __init__(self, library: Library, max_bytes: int = 256 * 1024 * 1024):
        self.library = library
        self.max_bytes = max_bytes
        self._cache: OrderedDict[str, QPixmap] = OrderedDict()
        self._bytes = 0
        self._placeholder = _placeholder()

    @property
    def size_bytes(self) -> int:
        return self._bytes

    @staticmethod
    def _cost(pm: QPixmap) -> int:
        return max(1, pm.width() * pm.height() * 4)

    def _drop(self, key: str) -> None:
        pm = self._cache.pop(key, None)
        if pm is not None and pm is not self._placeholder:
            self._bytes -= self._cost(pm)

    def invalidate(self, asset: Asset | None) -> None:
        """Oublie les images d'une ressource (elle vient d'être retouchée)."""
        if asset is not None:
            for path in [asset.image_path, *[v.image_path for v in asset.variants]]:
                self._drop(path)

    def get(self, asset: Asset | None, variant: str | None = None) -> QPixmap:
        if asset is None:
            return self._placeholder
        key = asset.image_for(variant)
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        pm = QPixmap(str(self.library.abs_path(key)))
        if pm.isNull():
            self._cache[key] = self._placeholder
            return self._placeholder
        self._cache[key] = pm
        self._bytes += self._cost(pm)
        while self._bytes > self.max_bytes and len(self._cache) > 1:
            self._drop(next(iter(self._cache)))  # la plus anciennement utilisée
        return pm
