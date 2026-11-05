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

from sbs.domain.ids import is_valid_id, new_id
from sbs.domain.scene import Instance
from sbs.domain.schema import PROJECT_SCHEMA_VERSION
from sbs.services.atomic import write_text_atomic
from sbs.services.library import Library

FORMAT = "sprite-builder-studio-project"
EXTENSION = ".sbsproj"

# version de départ -> fonction qui transforme le dict vers la version suivante
MIGRATIONS: dict[int, Any] = {}


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
    missing_assets: list[str]  # uuid absents de la bibliothèque (instances conservées)
    remapped: int  # instances rattachées à un autre uuid grâce à library_refs


# --------------------------------------------------------------------------- sauvegarde
def save_project(path: Path, meta: ProjectMeta, instances: list[Instance], library: Library) -> None:
    path = Path(path)
    refs = dict(meta.library_refs)  # on garde les références des images absentes
    used = {i.asset_uuid for i in instances}
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
            "instances": [
                {"id": i.id, "asset_uuid": i.asset_uuid, "x": i.x, "y": i.y,
                 "z_manual": i.z_manual, "variant": i.variant}
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

    instances: list[Instance] = []
    seen: set[str] = set()
    missing: list[str] = []
    remapped = 0
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

        if library.get(asset_uuid) is None:
            ref = refs.get(asset_uuid)
            found = library.find_by_source(ref["origin"], ref["source_id"]) if ref else None
            if found is not None:
                asset_uuid, remapped = found.uuid, remapped + 1
            elif asset_uuid not in missing:
                missing.append(asset_uuid)  # l'instance est conservée (repère rose)
        instances.append(Instance(inst_id, asset_uuid, x, y, z, variant))

    meta = ProjectMeta(
        id=doc["id"] if isinstance(doc.get("id"), str) and is_valid_id(doc.get("id")) else new_id(),
        name=str(doc.get("name") or path.stem),
        scene_id=scene["id"] if isinstance(scene.get("id"), str) else new_id(),
        scene_name=str(scene.get("name") or "Construction 1"),
        created_at=str(doc.get("created_at") or _now()),
        updated_at=str(doc.get("updated_at") or _now()),
        library_refs=refs,
    )
    return LoadResult(meta, instances, missing, remapped)
