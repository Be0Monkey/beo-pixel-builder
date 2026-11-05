"""Détection des références manquantes : ressource absente de la bibliothèque ou image absente du disque."""

from sbs.domain.scene import SceneModel
from sbs.services.library import Library


def find_missing(model: SceneModel, library: Library) -> list[tuple[str, str]]:
    """[(id d'instance, raison)] pour les objets qui ne peuvent pas être affichés correctement."""
    verdict: dict[tuple[str, str | None], str] = {}
    out: list[tuple[str, str]] = []
    for inst in model.all():
        key = (inst.asset_uuid, inst.variant)
        if key not in verdict:
            asset = library.get(inst.asset_uuid)
            if asset is None:
                verdict[key] = "ressource absente de la bibliothèque"
            elif not library.abs_path(asset.image_for(inst.variant)).is_file():
                verdict[key] = "fichier image absent"
            else:
                verdict[key] = ""
        if verdict[key]:
            out.append((inst.id, verdict[key]))
    return out
