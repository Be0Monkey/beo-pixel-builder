"""Fichier projet natif (JSON versionné). Voir docs/specs/02_Architecture_technique.md §7.

- Sauvegarde atomique (fichier temporaire puis renommage) + copie de secours `.bak`.
- Chargement strict et sans exécution de code : tout est validé avant d'être utilisé.
- Un projet illisible ou d'une version inconnue produit une erreur claire, jamais un plantage
  ni une perte du projet déjà ouvert.
"""

import json
import shutil
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sbs.domain.animation import Animation, Frame, validate_animation
from sbs.domain.ids import is_valid_id, new_id
from sbs.domain.scene import (
    Floor,
    Group,
    Instance,
    Layer,
    SceneModel,
        validate_floors,
    validate_grouping,
)
from sbs.domain.schema import PROJECT_SCHEMA_VERSION
from sbs.services.atomic import write_text_atomic
from sbs.services.library import Library

FORMAT = "sprite-builder-studio-project"
EXTENSION = ".sbsproj"

# version de départ -> fonction qui transforme le dict vers la version suivante
def _migrate_1_to_2(doc: dict) -> dict:
    """v1 -> v2 : ajoute un étage « RDC » avec un calque et y range tous les objets."""
    floor, layer = new_id(), new_id()
    scenes = doc.get("scenes")
    if isinstance(scenes, list):
        for sc in scenes:
            if not isinstance(sc, dict):
                continue
            sc["floors"] = [{"id": floor, "name": "RDC", "elevation_px": 0, "visible": True,
                             "locked": False, "layers": [{"id": layer, "name": "Calque 1",
                                                          "visible": True, "locked": False}]}]
            sc["groups"] = []
            for inst in sc.get("instances", []) if isinstance(sc.get("instances"), list) else []:
                if isinstance(inst, dict):
                    inst["floor_id"], inst["layer_id"], inst["group_id"] = floor, layer, None
    doc["schema_version"] = 2
    return doc


def _migrate_2_to_3(doc: dict) -> dict:
    """v2 -> v3 : ajoute la liste des animations (vide)."""
    for sc in doc.get("scenes", []) if isinstance(doc.get("scenes"), list) else []:
        if isinstance(sc, dict):
            sc.setdefault("animations", [])
    doc["schema_version"] = 3
    return doc


MIGRATIONS: dict[int, Any] = {1: _migrate_1_to_2, 2: _migrate_2_to_3}


class ProjectError(Exception):
    """Message destiné à l'utilisateur."""


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class ProjectMeta:
    id: str = field(default_factory=new_id)
    name: str = "Sans titre"
    scene_id: str = field(default_factory=new_id)
    scene_name: str = "Construction 1"
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)
    library_refs: dict[str, dict[str, str]] = field(default_factory=dict)


@dataclass
class LoadResult:
    meta: ProjectMeta
    instances: list[Instance]
    floors: list[Floor]
    groups: dict[str, Group]
    animations: dict[str, Animation]
    missing_assets: list[str]  # uuid absents de la bibliothèque (instances conservées)
    remapped: int  # instances rattachées à un autre uuid grâce à library_refs


# --------------------------------------------------------------------------- sauvegarde
def save_project(path: Path, meta: ProjectMeta, model: SceneModel, library: Library) -> None:
    path = Path(path)
    instances = model.all()
    refs = dict(meta.library_refs)  # on garde les références des images absentes
    used = {i.asset_uuid for i in instances} | {f.asset_uuid for a in model.animations.values() for f in a.frames}
    for uuid in used:
        asset = library.get(uuid)
        if asset is not None:
            refs[uuid] = {"origin": asset.origin, "source_id": asset.source_id, "sha256": asset.sha256}
    refs = {u: r for u, r in refs.items() if u in used}
    meta.library_refs = refs
    meta.updated_at = _now()
    doc = {
        "format": FORMAT,
        "schema_version": PROJECT_SCHEMA_VERSION,
        "id": meta.id,
        "name": meta.name,
        "created_at": meta.created_at,
        "updated_at": meta.updated_at,
        "library_refs": refs,
        "scenes": [{
            "id": meta.scene_id,
            "name": meta.scene_name,
            "floors": [
                {"id": f.id, "name": f.name, "elevation_px": f.elevation_px, "visible": f.visible,
                 "locked": f.locked,
                 "layers": [{"id": layer.id, "name": layer.name, "visible": layer.visible,
                             "locked": layer.locked} for layer in f.layers]}
                for f in model.floors
            ],
            "groups": [{"id": g.id, "name": g.name, "parent_id": g.parent_id}
                       for g in model.groups.values()],
            "animations": [
                {"id": a.id, "name": a.name, "fps": a.fps, "loop": a.loop,
                 "frames": [{"asset_uuid": f.asset_uuid, "variant": f.variant, "hold": f.hold}
                            for f in a.frames]}
                for a in model.animations.values()
            ],
            "instances": [
                {"id": i.id, "asset_uuid": i.asset_uuid, "x": i.x, "y": i.y, "z_manual": i.z_manual,
                 "variant": i.variant, "floor_id": i.floor_id, "layer_id": i.layer_id,
                 "group_id": i.group_id}
                for i in instances
            ],
        }],
    }
    text = json.dumps(doc, indent=1, ensure_ascii=False)  # sérialisé AVANT de toucher au disque
    if path.exists():
        try:
            shutil.copy2(path, path.with_name(path.name + ".bak"))
        except OSError:
            pass  # la copie de secours est un plus ; l'écriture atomique protège déjà le fichier
    write_text_atomic(path, text)


# --------------------------------------------------------------------------- chargement
def _parse_floors(raw: list) -> list[Floor]:
    floors: list[Floor] = []
    for n, f in enumerate(raw):
        if not isinstance(f, dict):
            raise ProjectError(f"projet invalide : étage n°{n + 1} illisible")
        where = f"étage n°{n + 1}"
        layers = []
        for m, layer in enumerate(_need(f, "layers", list, where)):
            if not isinstance(layer, dict):
                raise ProjectError(f"projet invalide : calque n°{m + 1} illisible ({where})")
            layers.append(Layer(
                _need(layer, "id", str, where), _need(layer, "name", str, where),
                layer["visible"] if isinstance(layer.get("visible"), bool) else True,
                layer["locked"] if isinstance(layer.get("locked"), bool) else False,
            ))
        elev = f.get("elevation_px", 0)
        if isinstance(elev, bool) or not isinstance(elev, int):
            raise ProjectError(f"projet invalide : « elevation_px » incorrect ({where})")
        floors.append(Floor(
            _need(f, "id", str, where), _need(f, "name", str, where), elev,
            f["visible"] if isinstance(f.get("visible"), bool) else True,
            f["locked"] if isinstance(f.get("locked"), bool) else False, layers,
        ))
    try:
        validate_floors(floors)
    except ValueError as exc:
        raise ProjectError(f"projet invalide : {exc}") from exc
    return floors


def _parse_groups(raw: list) -> dict[str, Group]:
    groups: dict[str, Group] = {}
    for n, g in enumerate(raw):
        if not isinstance(g, dict):
            raise ProjectError(f"projet invalide : groupe n°{n + 1} illisible")
        gid = _need(g, "id", str, f"groupe n°{n + 1}")
        if gid in groups:
            raise ProjectError(f"projet invalide : groupe en double ({gid})")
        parent = g.get("parent_id")
        if parent is not None and not isinstance(parent, str):
            raise ProjectError(f"projet invalide : « parent_id » incorrect (groupe n°{n + 1})")
        groups[gid] = Group(gid, str(g.get("name") or "Groupe"), parent)
    return groups


def _need(d: dict, key: str, typ: type, where: str):
    v = d.get(key)
    if isinstance(v, bool) or not isinstance(v, typ):
        raise ProjectError(f"projet invalide : « {key} » manquant ou de mauvais type ({where})")
    return v


def load_project(path: Path, library: Library) -> LoadResult:
    path = Path(path)
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise ProjectError(f"fichier introuvable : {path}") from None
    except (OSError, UnicodeDecodeError) as exc:
        raise ProjectError(f"impossible de lire le fichier : {exc}") from exc
    try:
        doc = json.loads(raw)
    except ValueError as exc:
        raise ProjectError(f"fichier abîmé (JSON invalide) : {exc}") from exc
    if not isinstance(doc, dict) or doc.get("format") != FORMAT:
        raise ProjectError("ce fichier n'est pas un projet Sprite Builder Studio")

    version = doc.get("schema_version")
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        raise ProjectError("version du projet absente ou invalide")
    if version > PROJECT_SCHEMA_VERSION:
        raise ProjectError(
            f"projet créé par une version plus récente de l'application (format {version}, "
            f"cette version comprend jusqu'à {PROJECT_SCHEMA_VERSION}). Mets l'application à jour."
        )
    while version < PROJECT_SCHEMA_VERSION:
        migrate = MIGRATIONS.get(version)
        if migrate is None:
            raise ProjectError(f"aucune migration disponible depuis le format {version}")
        doc, version = migrate(doc), version + 1

    scenes = _need(doc, "scenes", list, "racine")
    if len(scenes) != 1 or not isinstance(scenes[0], dict):
        raise ProjectError(
            f"ce projet contient {len(scenes)} scène(s) ; une seule est gérée pour l'instant"
        )
    scene = scenes[0]
    refs_raw = doc.get("library_refs", {})
    if not isinstance(refs_raw, dict):
        raise ProjectError("projet invalide : « library_refs » doit être un objet")
    refs = {k: v for k, v in refs_raw.items()
            if isinstance(k, str) and isinstance(v, dict)
            and all(isinstance(v.get(f), str) for f in ("origin", "source_id"))}

    floors = _parse_floors(_need(scene, "floors", list, "scène"))
    groups = _parse_groups(_need(scene, "groups", list, "scène"))
    valid_targets = {(f.id, layer.id) for f in floors for layer in f.layers}
    instances: list[Instance] = []
    seen: set[str] = set()
    missing: list[str] = []
    remapped = 0

    def resolve(asset_uuid: str) -> str:
        """Rattache un module à la bibliothèque de cet ordinateur (par origine + identifiant du kit)."""
        nonlocal remapped
        if library.get(asset_uuid) is None:
            ref = refs.get(asset_uuid)
            found = library.find_by_source(ref["origin"], ref["source_id"]) if ref else None
            if found is not None:
                remapped += 1
                return found.uuid
            if asset_uuid not in missing:
                missing.append(asset_uuid)  # conservé : repère rose
        return asset_uuid
    for n, d in enumerate(_need(scene, "instances", list, "scène")):
        if not isinstance(d, dict):
            raise ProjectError(f"projet invalide : objet n°{n + 1} illisible")
        where = f"objet n°{n + 1}"
        inst_id = _need(d, "id", str, where)
        if inst_id in seen:
            raise ProjectError(f"projet invalide : identifiant en double ({inst_id})")
        seen.add(inst_id)
        asset_uuid = _need(d, "asset_uuid", str, where)
        x, y = _need(d, "x", int, where), _need(d, "y", int, where)
        z = d.get("z_manual", 0)
        if isinstance(z, bool) or not isinstance(z, int):
            raise ProjectError(f"projet invalide : « z_manual » incorrect ({where})")
        variant = d.get("variant")
        if variant is not None and not isinstance(variant, str):
            raise ProjectError(f"projet invalide : « variant » incorrect ({where})")
        floor_id, layer_id = _need(d, "floor_id", str, where), _need(d, "layer_id", str, where)
        if (floor_id, layer_id) not in valid_targets:
            raise ProjectError(f"projet invalide : {where} référence un étage ou un calque inconnu")
        group_id = d.get("group_id")
        if group_id is not None and not isinstance(group_id, str):
            raise ProjectError(f"projet invalide : « group_id » incorrect ({where})")

        asset_uuid = resolve(asset_uuid)
        instances.append(Instance(inst_id, asset_uuid, x, y, z, variant, floor_id, layer_id, group_id))

    try:
        validate_grouping(groups, {i.id: i.group_id for i in instances})
    except ValueError as exc:
        raise ProjectError(f"projet invalide : {exc}") from exc

    animations: dict[str, Animation] = {}
    for n, d in enumerate(scene.get("animations", [])):
        where = f"animation n°{n + 1}"
        if not isinstance(d, dict) or not isinstance(d.get("frames"), list):
            raise ProjectError(f"projet invalide : {where} illisible")
        frames = []
        for fd in d["frames"]:
            if not isinstance(fd, dict) or not isinstance(fd.get("asset_uuid"), str):
                raise ProjectError(f"projet invalide : image d'{where} illisible")
            frames.append(Frame(resolve(fd["asset_uuid"]), fd.get("variant"), fd.get("hold", 1)))
        anim = Animation(d.get("id"), d.get("name"), d.get("fps", 8), d.get("loop", True), frames)
        try:
            validate_animation(anim)
        except ValueError as exc:
            raise ProjectError(f"projet invalide : {where} : {exc}") from exc
        if anim.id in animations:
            raise ProjectError(f"projet invalide : identifiant d'animation en double ({anim.id})")
        animations[anim.id] = anim

    meta = ProjectMeta(
        id=doc["id"] if isinstance(doc.get("id"), str) and is_valid_id(doc.get("id")) else new_id(),
        name=str(doc.get("name") or path.stem),
        scene_id=scene["id"] if isinstance(scene.get("id"), str) else new_id(),
        scene_name=str(scene.get("name") or "Construction 1"),
        created_at=str(doc.get("created_at") or _now()),
        updated_at=str(doc.get("updated_at") or _now()),
        library_refs=refs,
    )
    return LoadResult(meta, instances, floors, groups, animations, missing, remapped)
