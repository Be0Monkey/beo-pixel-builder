"""Échanges avec la version téléphone (Atelier Pixel, dans le navigateur).

Deux fichiers JSON, images PNG incluses (base64), sans exécution de code :
- « paquet bibliothèque » (PC -> téléphone) : les modules de la bibliothèque, avec pivot, catégorie, mots-clés ;
- « paquet scène » (téléphone -> PC) : les modules utilisés par une scène et la position de chaque objet.

Dans une scène, (x, y) est la position du pivot du module, comme dans un projet .sbsproj.
"""

import base64
import binascii
import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from sbs.domain.ids import new_id
from sbs.domain.scene import Floor, Instance, default_floors
from sbs.services.atomic import write_text_atomic
from sbs.services.batch_import import find_local_by_sha
from sbs.services.library import Library, LibraryError
from sbs.services.project_io import ProjectMeta

LIB_FORMAT = "sbs-library-pack"
SCENE_FORMAT = "sbs-scene-pack"
PACK_VERSION = 1
MAX_MODULES = 5000
MAX_INSTANCES = 20000
MAX_PNG_BYTES = 8 * 1024 * 1024
MAX_SIDE = 4096


class PackError(Exception):
    """Message destiné à l'utilisateur."""


# --------------------------------------------------------------------------- export de la bibliothèque
def export_library_pack(library: Library, path: Path, categories: list[str] | None = None,
                        progress: Callable[[int, int], None] | None = None) -> int:
    """Écrit le paquet bibliothèque. Renvoie le nombre de modules écrits."""
    assets = [a for a in library.list_assets() if not categories or a.category in categories]
    modules = []
    for n, a in enumerate(assets):
        if progress is not None:
            progress(n, len(assets))
        try:
            png = library.image_bytes(a.uuid)
        except (LibraryError, OSError):
            continue  # image absente : le module est ignoré, les autres passent
        modules.append({
            "id": a.uuid, "name": a.name, "category": a.category, "w": a.width, "h": a.height,
            "px": a.pivot_x, "py": a.pivot_y, "tags": list(a.tags),
            "png": base64.b64encode(png).decode("ascii"),
        })
    doc = {"format": LIB_FORMAT, "version": PACK_VERSION, "modules": modules}
    write_text_atomic(Path(path), json.dumps(doc, ensure_ascii=False, separators=(",", ":")))
    return len(modules)


# --------------------------------------------------------------------------- lecture d'un paquet scène
@dataclass
class PackModule:
    id: str
    name: str
    category: str
    w: int
    h: int
    px: int
    py: int
    png: bytes


@dataclass
class PackInstance:
    module: str
    x: int
    y: int
    z: int = 0


@dataclass
class ScenePack:
    name: str
    modules: dict[str, PackModule] = field(default_factory=dict)
    instances: list[PackInstance] = field(default_factory=list)


def _int(v: object, what: str, lo: int, hi: int) -> int:
    if isinstance(v, bool) or not isinstance(v, int) or not lo <= v <= hi:
        raise PackError(f"paquet invalide : « {what} » doit être un entier entre {lo} et {hi}")
    return v


def _text(v: object, what: str, maxlen: int) -> str:
    if not isinstance(v, str) or not v.strip() or len(v) > maxlen:
        raise PackError(f"paquet invalide : « {what} » manquant ou trop long")
    return v


def parse_scene_pack(text: str) -> ScenePack:
    try:
        doc = json.loads(text)
    except (ValueError, RecursionError) as exc:
        raise PackError("ce fichier n'est pas un paquet valide (JSON illisible)") from exc
    if not isinstance(doc, dict) or doc.get("format") != SCENE_FORMAT:
        raise PackError("ce fichier n'est pas un paquet scène du téléphone")
    if doc.get("version") != PACK_VERSION:
        raise PackError(f"version de paquet non prise en charge ({doc.get('version')!r}) : "
                        "mets à jour Sprite Builder Studio ou l'Atelier Pixel")
    raw_modules, raw_instances = doc.get("modules"), doc.get("instances")
    if not isinstance(raw_modules, list) or not isinstance(raw_instances, list):
        raise PackError("paquet invalide : listes « modules » et « instances » attendues")
    if len(raw_modules) > MAX_MODULES or len(raw_instances) > MAX_INSTANCES:
        raise PackError("paquet trop gros")
    name = str(doc.get("name") or "Scène du téléphone").strip()[:60] or "Scène du téléphone"
    pack = ScenePack(name)
    for n, m in enumerate(raw_modules, 1):
        if not isinstance(m, dict):
            raise PackError(f"paquet invalide : module n°{n} illisible")
        mid = _text(m.get("id"), "id", 64)
        if mid in pack.modules:
            raise PackError(f"paquet invalide : module en double ({mid})")
        w, h = _int(m.get("w"), "w", 1, MAX_SIDE), _int(m.get("h"), "h", 1, MAX_SIDE)
        px, py = _int(m.get("px"), "px", 0, w - 1), _int(m.get("py"), "py", 0, h - 1)
        try:
            png = base64.b64decode(_text(m.get("png"), "png", 4 * MAX_PNG_BYTES), validate=True)
        except (binascii.Error, ValueError) as exc:
            raise PackError(f"paquet invalide : image illisible (module « {mid} »)") from exc
        if len(png) > MAX_PNG_BYTES:
            raise PackError(f"paquet invalide : image trop lourde (module « {mid} »)")
        try:
            size = Library._check_png(png)
        except LibraryError as exc:
            raise PackError(f"paquet invalide : {exc} (module « {mid} »)") from exc
        if size != (w, h):
            raise PackError(f"paquet invalide : la taille annoncée ne correspond pas à l'image (module « {mid} »)")
        pack.modules[mid] = PackModule(mid, " ".join(str(m.get("name") or mid).split())[:80] or mid,
                                       " ".join(str(m.get("category") or "divers").split())[:40] or "divers",
                                       w, h, px, py, png)
    for n, i in enumerate(raw_instances, 1):
        if not isinstance(i, dict):
            raise PackError(f"paquet invalide : objet n°{n} illisible")
        mod = i.get("module")
        if not isinstance(mod, str) or mod not in pack.modules:
            raise PackError(f"paquet invalide : l'objet n°{n} utilise un module absent du paquet")
        pack.instances.append(PackInstance(mod, _int(i.get("x"), "x", -1_000_000, 1_000_000),
                                           _int(i.get("y"), "y", -1_000_000, 1_000_000),
                                           _int(i.get("z", 0), "z", -1_000_000, 1_000_000)))
    return pack


# --------------------------------------------------------------------------- import dans la bibliothèque
@dataclass
class ImportResult:
    meta: ProjectMeta
    instances: list[Instance]
    floors: list[Floor]
    reused: int = 0
    created: int = 0


def import_scene_pack(library: Library, pack: ScenePack) -> ImportResult:
    """Rattache chaque module du paquet à la bibliothèque (réutilise ou crée), puis construit la scène."""
    mapping: dict[str, str] = {}
    created_now: list[str] = []
    reused = created = 0
    try:
        for mid, m in pack.modules.items():
            existing = library.get(mid)
            if existing is not None and (existing.width, existing.height) == (m.w, m.h):
                mapping[mid], reused = existing.uuid, reused + 1
                continue
            same = find_local_by_sha(library, hashlib.sha256(m.png).hexdigest())
            if same is not None:
                mapping[mid], reused = same, reused + 1
                continue
            asset = library.create_asset(m.name, m.png, (m.px, m.py), m.category)
            created_now.append(asset.uuid)
            mapping[mid], created = asset.uuid, created + 1
    except (LibraryError, ValueError, OSError) as exc:
        for uuid in created_now:  # rien à moitié fait
            library.delete_asset(uuid)
        raise PackError(f"import impossible : {exc}") from exc
    floors = default_floors()
    fid, lid = floors[0].id, floors[0].layers[0].id
    instances = [Instance(new_id(), mapping[i.module], i.x, i.y, i.z, None, fid, lid, None) for i in pack.instances]
    meta = ProjectMeta(name=pack.name)
    return ImportResult(meta, instances, floors, reused, created)
