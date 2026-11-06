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
from sbs.domain.animation import MAX_FPS, MAX_FRAMES, MAX_HOLD, Animation, Frame
from sbs.domain.scene import MAX_GROUP_DEPTH, Floor, Group, Instance, Layer, default_floors
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
    floor: str | None = None  # identifiants du paquet (facultatifs)
    layer: str | None = None
    group: str | None = None


@dataclass
class ScenePack:
    name: str
    modules: dict[str, PackModule] = field(default_factory=dict)
    instances: list[PackInstance] = field(default_factory=list)
    floors: list[dict] = field(default_factory=list)       # [{id, name, visible, locked, layers:[{id, name, visible, locked}]}]
    groups: dict[str, dict] = field(default_factory=dict)  # id -> {name, parent}
    animations: list[dict] = field(default_factory=list)   # [{name, fps, loop, frames:[{module, hold}]}]


def _int(v: object, what: str, lo: int, hi: int) -> int:
    if isinstance(v, bool) or not isinstance(v, int) or not lo <= v <= hi:
        raise PackError(f"paquet invalide : « {what} » doit être un entier entre {lo} et {hi}")
    return v


def _text(v: object, what: str, maxlen: int) -> str:
    if not isinstance(v, str) or not v.strip() or len(v) > maxlen:
        raise PackError(f"paquet invalide : « {what} » manquant ou trop long")
    return v


def _parse_module(m: object, n: int) -> "PackModule":
    """Valide un module d'un paquet (scène ou bibliothèque) ; PackError si un champ est incorrect."""
    if not isinstance(m, dict):
        raise PackError(f"paquet invalide : module n°{n} illisible")
    mid = _text(m.get("id"), "id", 64)
    w, h = _int(m.get("w"), "w", 1, MAX_SIDE), _int(m.get("h"), "h", 1, MAX_SIDE)
    # le pivot peut être hors de l'image (ex. sur le bord bas : y = hauteur)
    px, py = _int(m.get("px"), "px", -MAX_SIDE, 2 * MAX_SIDE), _int(m.get("py"), "py", -MAX_SIDE, 2 * MAX_SIDE)
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
    return PackModule(mid, " ".join(str(m.get("name") or mid).split())[:80] or mid,
                      " ".join(str(m.get("category") or "divers").split())[:40] or "divers", w, h, px, py, png)


def _pivot_in_image(m: "PackModule") -> tuple[int, int]:
    """La bibliothèque exige un pivot dans l'image : un pivot plus loin est ramené au bord (le module n'est pas perdu)."""
    return min(max(m.px, 0), m.w), min(max(m.py, 0), m.h)


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
        mod = _parse_module(m, n)
        if mod.id in pack.modules:
            raise PackError(f"paquet invalide : module en double ({mod.id})")
        pack.modules[mod.id] = mod
    for n, i in enumerate(raw_instances, 1):
        if not isinstance(i, dict):
            raise PackError(f"paquet invalide : objet n°{n} illisible")
        mod = i.get("module")
        if not isinstance(mod, str) or mod not in pack.modules:
            raise PackError(f"paquet invalide : l'objet n°{n} utilise un module absent du paquet")
        ref = lambda k: i.get(k) if isinstance(i.get(k), str) and len(i.get(k)) <= 64 else None  # noqa: E731
        pack.instances.append(PackInstance(mod, _int(i.get("x"), "x", -1_000_000, 1_000_000),
                                           _int(i.get("y"), "y", -1_000_000, 1_000_000),
                                           _int(i.get("z", 0), "z", -1_000_000, 1_000_000),
                                           ref("floor"), ref("layer"), ref("group")))
    _read_structure(pack, doc)
    return pack


def _name(v: object, default: str) -> str:
    return " ".join(str(v or default).split())[:40] or default


def _read_structure(pack: ScenePack, doc: dict) -> None:
    """Étages, calques, groupes, animations : facultatifs, lus avec indulgence (le reste de la scène passe toujours)."""
    floors = doc.get("floors")
    if isinstance(floors, list):
        for f in floors[:50]:
            if not isinstance(f, dict) or not isinstance(f.get("id"), str) or not isinstance(f.get("layers"), list):
                continue
            layers = [{"id": l["id"], "name": _name(l.get("name"), "Calque"), "visible": l.get("visible") is not False,
                       "locked": l.get("locked") is True}
                      for l in f["layers"][:50] if isinstance(l, dict) and isinstance(l.get("id"), str)]
            if layers:
                pack.floors.append({"id": f["id"], "name": _name(f.get("name"), "Étage"),
                                    "visible": f.get("visible") is not False, "locked": f.get("locked") is True,
                                    "layers": layers})
    groups = doc.get("groups")
    if isinstance(groups, dict):
        for gid, g in list(groups.items())[:2000]:
            if isinstance(gid, str) and isinstance(g, dict):
                parent = g.get("parent")
                pack.groups[gid] = {"name": _name(g.get("name"), "Groupe"), "parent": parent if isinstance(parent, str) else None}
    anims = doc.get("animations")
    if isinstance(anims, list):
        for a in anims[:50]:
            if not isinstance(a, dict) or not isinstance(a.get("frames"), list):
                continue
            frames = [{"module": fr["module"], "hold": fr.get("hold") if isinstance(fr.get("hold"), int) and 1 <= fr["hold"] <= MAX_HOLD else 1}
                      for fr in a["frames"][:MAX_FRAMES] if isinstance(fr, dict) and fr.get("module") in pack.modules]
            fps = a.get("fps")
            pack.animations.append({"name": _name(a.get("name"), "Animation"),
                                    "fps": fps if isinstance(fps, int) and 1 <= fps <= MAX_FPS else 8,
                                    "loop": a.get("loop") is not False, "frames": frames})


# --------------------------------------------------------------------------- import dans la bibliothèque
@dataclass
class ImportResult:
    meta: ProjectMeta
    instances: list[Instance]
    floors: list[Floor]
    reused: int = 0
    created: int = 0
    groups: dict[str, Group] = field(default_factory=dict)
    animations: dict[str, Animation] = field(default_factory=dict)


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
            asset = library.create_asset(m.name, m.png, _pivot_in_image(m), m.category)
            created_now.append(asset.uuid)
            mapping[mid], created = asset.uuid, created + 1
    except (LibraryError, ValueError, OSError) as exc:
        for uuid in created_now:  # rien à moitié fait
            library.delete_asset(uuid)
        raise PackError(f"import impossible : {exc}") from exc
    floors, fmap, lmap = [], {}, {}
    for f in pack.floors:
        nf = Floor(new_id(), f["name"], 0, f["visible"], f["locked"], [])
        for l in f["layers"]:
            nl = Layer(new_id(), l["name"], l["visible"], l["locked"])
            nf.layers.append(nl)
            lmap[(f["id"], l["id"])] = (nf.id, nl.id)
        fmap[f["id"]] = nf
        floors.append(nf)
    if not floors:
        floors = default_floors()
    groups = _build_groups(pack.groups)
    instances = []
    for i in pack.instances:
        fid, lid = lmap.get((i.floor, i.layer)) or (floors[0].id, floors[0].layers[0].id)
        group = groups[1].get(i.group)
        instances.append(Instance(new_id(), mapping[i.module], i.x, i.y, i.z, None, fid, lid, group))
    used = {g for g in (inst.group_id for inst in instances) if g}
    group_objs = _prune(groups[0], used)
    animations = {}
    for a in pack.animations:
        frames = [Frame(mapping[fr["module"]], None, fr["hold"]) for fr in a["frames"]]
        anim = Animation(new_id(), a["name"], a["fps"], a["loop"], frames)
        animations[anim.id] = anim
    meta = ProjectMeta(name=pack.name)
    return ImportResult(meta, instances, floors, reused, created, group_objs, animations)


def _build_groups(raw: dict[str, dict]) -> tuple[dict[str, Group], dict[str, str]]:
    """Groupes du paquet -> groupes de la scène (nouveaux identifiants). Parent inconnu, cycle ou profondeur > 3 :
    le groupe est mis à la racine (jamais d'échec). Renvoie (groupes, ancien id -> nouvel id)."""
    new_ids = {gid: new_id() for gid in raw}
    groups = {new_ids[gid]: Group(new_ids[gid], g["name"], new_ids.get(g["parent"])) for gid, g in raw.items()}

    def depth(gid: str) -> int | None:
        d, seen = 1, {gid}
        cur = groups[gid]
        while cur.parent_id is not None:
            if cur.parent_id in seen:
                return None
            seen.add(cur.parent_id)
            cur = groups[cur.parent_id]
            d += 1
        return d

    for gid in list(groups):
        d = depth(gid)
        if d is None or d > MAX_GROUP_DEPTH:
            groups[gid].parent_id = None
    return groups, new_ids


def _prune(groups: dict[str, Group], used: set[str]) -> dict[str, Group]:
    keep = set(used)
    changed = True
    while changed:
        changed = False
        for g in groups.values():
            if g.id in keep and g.parent_id and g.parent_id not in keep:
                keep.add(g.parent_id)
                changed = True
    return {gid: g for gid, g in groups.items() if gid in keep}


# --------------------------------------------------------------------------- modules de départ (paquet bibliothèque)
def starter_pack_path() -> Path:
    """Paquet de modules fourni avec l'application (ressource du paquet Windows)."""
    return Path(__file__).resolve().parents[1] / "resources" / "modules_depart.sbspack.json"


def import_library_pack(library: Library, text: str) -> tuple[int, int]:
    """Ajoute à la bibliothèque les modules d'un paquet bibliothèque. Renvoie (créés, déjà présents).

    Un module identique (même image) déjà dans la bibliothèque n'est pas dupliqué ; un module invalide
    est ignoré sans arrêter les autres.
    """
    try:
        doc = json.loads(text)
    except (ValueError, RecursionError) as exc:
        raise PackError("ce fichier n'est pas un paquet valide (JSON illisible)") from exc
    if not isinstance(doc, dict) or doc.get("format") != LIB_FORMAT or doc.get("version") != PACK_VERSION \
            or not isinstance(doc.get("modules"), list):
        raise PackError("ce fichier n'est pas un paquet bibliothèque")
    created = reused = 0
    for n, raw in enumerate(doc["modules"][:MAX_MODULES], 1):
        try:
            m = _parse_module(raw, n)
            if find_local_by_sha(library, hashlib.sha256(m.png).hexdigest()) is not None:
                reused += 1
                continue
            asset = library.create_asset(m.name, m.png, _pivot_in_image(m), m.category)
            tags = raw.get("tags")
            if isinstance(tags, list) and tags:
                library.set_tags(asset.uuid, [str(t)[:40] for t in tags[:20]])
            created += 1
        except (PackError, LibraryError, ValueError, OSError):
            continue
    return created, reused
