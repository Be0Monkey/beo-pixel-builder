"""Presse-papiers interne : sélection <-> texte JSON. Le contenu du presse-papiers est une
donnée NON FIABLE : tout est validé, rien n'est exécuté."""

import json
from dataclasses import dataclass

from sbs.domain.scene import Instance
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


def encode_instances(instances: list[Instance], library: Library) -> str:
    items = []
    for i in instances:
        asset = library.get(i.asset_uuid)
        items.append({
            "asset_uuid": i.asset_uuid,
            "origin": asset.origin if asset else "",
            "source_id": asset.source_id if asset else "",
            "x": i.x, "y": i.y, "z_manual": i.z_manual, "variant": i.variant,
        })
    return json.dumps({"format": _FORMAT, "version": 1, "items": items}, ensure_ascii=False)


def _int(d: dict, key: str) -> int:
    v = d.get(key, 0 if key == "z_manual" else None)
    if isinstance(v, bool) or not isinstance(v, int):
        raise ValueError(f"« {key} » invalide")
    return v


def decode_instances(text: str) -> list[ClipEntry]:
    try:
        doc = json.loads(text)
    except (TypeError, ValueError) as exc:
        raise ValueError("contenu du presse-papiers non reconnu") from exc
    if not isinstance(doc, dict) or doc.get("format") != _FORMAT or doc.get("version") != 1:
        raise ValueError("contenu du presse-papiers non reconnu")
    items = doc.get("items")
    if not isinstance(items, list) or len(items) > MAX_ITEMS:
        raise ValueError("liste d'objets invalide")
    out = []
    for d in items:
        if not isinstance(d, dict):
            raise ValueError("objet illisible")
        uuid, origin, sid = d.get("asset_uuid"), d.get("origin", ""), d.get("source_id", "")
        variant = d.get("variant")
        if not isinstance(uuid, str) or not isinstance(origin, str) or not isinstance(sid, str):
            raise ValueError("référence d'image invalide")
        if variant is not None and not isinstance(variant, str):
            raise ValueError("variante invalide")
        out.append(ClipEntry(uuid, origin, sid, _int(d, "x"), _int(d, "y"), _int(d, "z_manual"), variant))
    return out
