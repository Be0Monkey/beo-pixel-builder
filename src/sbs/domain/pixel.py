"""Document Pixel Art : calques de pixels RGBA (sans Qt). Les pixels sont bruts, jamais lissés."""

from PIL import Image

from sbs.domain.ids import new_id

MAX_SIZE = 512
MAX_LAYERS = 32
RGBA = tuple[int, int, int, int]
CLEAR: RGBA = (0, 0, 0, 0)


class PixLayer:
    def __init__(self, width: int, height: int, name: str = "Calque", layer_id: str | None = None,
                 visible: bool = True, locked: bool = False, data: bytes | None = None):
        self.id = layer_id or new_id()
        self.name = name
        self.visible = visible
        self.locked = locked
        size = width * height * 4
        if data is not None and len(data) != size:
            raise ValueError("données de calque de mauvaise taille")
        self.data = bytearray(data) if data is not None else bytearray(size)


class PixelDoc:
    def __init__(self, width: int, height: int, layers: list[PixLayer] | None = None):
        for name, v in (("largeur", width), ("hauteur", height)):
            if isinstance(v, bool) or not isinstance(v, int) or not (1 <= v <= MAX_SIZE):
                raise ValueError(f"{name} : un entier de 1 à {MAX_SIZE}")
        self.width, self.height = width, height
        self.layers = layers or [PixLayer(width, height, "Calque 1")]
        self.active_id = self.layers[-1].id

    # --- accès ------------------------------------------------------------------------------
    def inside(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def index(self, x: int, y: int) -> int:
        return (y * self.width + x) * 4

    def layer(self, layer_id: str) -> PixLayer | None:
        return next((layer for layer in self.layers if layer.id == layer_id), None)

    @property
    def active(self) -> PixLayer:
        return self.layer(self.active_id) or self.layers[-1]

    def get(self, layer: PixLayer, x: int, y: int) -> RGBA:
        i = self.index(x, y)
        return tuple(layer.data[i:i + 4])  # type: ignore[return-value]

    # --- image finale ------------------------------------------------------------------------
    def flatten_image(self) -> Image.Image:
        out = Image.new("RGBA", (self.width, self.height), CLEAR)
        for layer in self.layers:
            if layer.visible:
                out = Image.alpha_composite(
                    out, Image.frombytes("RGBA", (self.width, self.height), bytes(layer.data)))
        return out

    def flatten_get(self, x: int, y: int) -> RGBA:
        r, g, b, a = self.flatten_image().getpixel((x, y))
        return r, g, b, a

    @classmethod
    def from_image(cls, im: Image.Image) -> "PixelDoc":
        im = im.convert("RGBA")
        doc = cls(im.width, im.height, [])
        doc.layers = [PixLayer(im.width, im.height, "Calque 1", data=im.tobytes())]
        doc.active_id = doc.layers[0].id
        return doc
