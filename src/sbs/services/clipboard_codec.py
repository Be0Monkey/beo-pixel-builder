"""Presse-papiers interne : sélection <-> texte JSON. Le contenu du presse-papiers est une
donnée NON FIABLE : tout est validé, rien n'est exécuté."""

import json
from dataclasses import dataclass

from sbs.domain.scene import Group, Instance, SceneModel
from sbs.services.library import Library

MIME = "application/x-sbs-instances"
_FORMAT = "sbs-instances"
MAX_ITEMS = 100_000


@dataclass
class ClipEntry:
    asset_uuid: str
    origin: str
    source_id: str
    x: int
    y: int
    z_manual: int
    variant: str | None
    floor_id: str = ""
    layer_id: str = ""
    group_id: str | None = None


def encode_instances(instances: list[Instance], library: Library, model: SceneModel | None = None) -> str:
    items = []
    for i in instances:
        asset = library.get(i.asset_uuid)
        items.append({
            "asset_uuid": i.asset_uuid,
            "origin": asset.origin if asset else "",
            "source_id": asset.source_id if asset else "",
            "x": i.x, "y": i.y, "z_manual": i.z_manual, "variant": i.variant,
            "floor_id": i.floor_id, "layer_id": i.layer_id, "group_id": i.group_id,
        })
    groups: list[dict] = []
    if model is not None:
        needed: set[str] = set()
        for i in instances:
            gid = i.group_id
            while gid is not None and gid not in needed:
                needed.add(gid)
                gid = model.groups[gid].parent_id
        groups = [{"id": g.id, "name": g.name, "parent_id": g.parent_id}
                  for g in model.groups.values() if g.id in needed]
    return json.dumps({"format": _FORMAT, "version": 1, "items": items, "groups": groups},
                      ensure_ascii=False)


def _int(d: dict, key: str) -> int:
    v = d.get(key, 0 if key == "z_manual" else None)
    if isinstance(v, bool) or not isinstance(v, int):
        raise ValueError(f"« {key} » invalide")
    return v


def _opt_str(d: dict, key: str, default: str | None) -> str | None:
    v = d.get(key, default)
    if v is not None and not isinstance(v, str):
        raise ValueError(f"« {key} » invalide")
    return v


def decode_instances(text: str) -> tuple[list[ClipEntry], list[Group]]:
    try:
        doc = json.loads(text)
    except (TypeError, ValueError) as exc:
        raise ValueError("contenu du presse-papiers non reconnu") from exc
    if not isinstance(doc, dict) or doc.get("format") != _FORMAT or doc.get("version") != 1:
        raise ValueError("contenu du presse-papiers non reconnu")
    items = doc.get("items")
    raw_groups = doc.get("groups", [])
    if not isinstance(items, list) or len(items) > MAX_ITEMS or not isinstance(raw_groups, list):
        raise ValueError("liste d'objets invalide")
    out = []
    for d in items:
        if not isinstance(d, dict):
            raise ValueError("objet illisible")
        uuid, origin, sid = d.get("asset_uuid"), d.get("origin", ""), d.get("source_id", "")
        if not isinstance(uuid, str) or not isinstance(origin, str) or not isinstance(sid, str):
            raise ValueError("référence d'image invalide")
        out.append(ClipEntry(
            uuid, origin, sid, _int(d, "x"), _int(d, "y"), _int(d, "z_manual"),
            _opt_str(d, "variant", None), _opt_str(d, "floor_id", "") or "",
            _opt_str(d, "layer_id", "") or "", _opt_str(d, "group_id", None),
        ))
    groups = []
    for g in raw_groups:
        if not isinstance(g, dict) or not isinstance(g.get("id"), str):
            raise ValueError("groupe invalide")
        groups.append(Group(g["id"], str(g.get("name") or "Groupe"), _opt_str(g, "parent_id", None)))
    return out, groups
