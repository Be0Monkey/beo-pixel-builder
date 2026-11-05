"""Lecture/écriture des sprites pour l'atelier Pixel Art.

Les calques sont gardés à côté de l'image (fichier « calques_<variante>.json » dans le dossier de la
ressource). Ils ne sont relus que si l'image à plat correspond encore (empreinte identique) :
sinon on repart de l'image seule, sans jamais afficher des calques périmés.
"""

import base64
import hashlib
import io
import json

from PIL import Image

from sbs.domain.pixel import PixelDoc, PixLayer
from sbs.services.atomic import write_text_atomic
from sbs.services.library import Library, LibraryError


def png_bytes(doc: PixelDoc) -> bytes:
    buf = io.BytesIO()
    doc.flatten_image().save(buf, format="PNG")
    return buf.getvalue()


def _sidecar(library: Library, uuid: str, variant: str | None):
    safe = "".join(c for c in (variant or "base") if c.isalnum() or c in "-_") or "base"
    return library.assets_dir / uuid / f"calques_{safe}.json"


def load_doc(library: Library, uuid: str, variant: str | None = None) -> PixelDoc:
    data = library.image_bytes(uuid, variant)
    try:
        with Image.open(io.BytesIO(data)) as im:
            flat = im.convert("RGBA")
    except OSError as exc:
        raise LibraryError(f"image illisible : {exc}") from exc
    doc = PixelDoc.from_image(flat)
    path = _sidecar(library, uuid, variant)
    try:
        info = json.loads(path.read_text(encoding="utf-8"))
        if info["flat_sha"] != hashlib.sha256(flat.tobytes()).hexdigest():
            return doc  # l'image a changé depuis : calques périmés, ignorés
        layers = []
        for item in info["layers"]:
            raw = Image.open(io.BytesIO(base64.b64decode(item["png"]))).convert("RGBA")
            if raw.size != flat.size:
                return doc
            layers.append(PixLayer(flat.width, flat.height, str(item["name"]), None,
                                   bool(item["visible"]), bool(item["locked"]), raw.tobytes()))
        if layers:
            rebuilt = PixelDoc(flat.width, flat.height, layers)
            return rebuilt
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return doc


def save_layers(library: Library, uuid: str, variant: str | None, doc: PixelDoc) -> None:
    """Garde les calques à côté de l'image (best effort : l'image à plat reste la référence)."""
    flat = doc.flatten_image()
    layers = []
    for layer in doc.layers:
        buf = io.BytesIO()
        Image.frombytes("RGBA", (doc.width, doc.height), bytes(layer.data)).save(buf, format="PNG")
        layers.append({"name": layer.name, "visible": layer.visible, "locked": layer.locked,
                       "png": base64.b64encode(buf.getvalue()).decode("ascii")})
    try:
        write_text_atomic(_sidecar(library, uuid, variant), json.dumps(
            {"flat_sha": hashlib.sha256(flat.tobytes()).hexdigest(), "layers": layers}))
    except OSError:
        pass
