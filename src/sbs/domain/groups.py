"""Aide aux groupes : « unité de sélection » selon le groupe dans lequel on est entré."""

from sbs.domain.scene import Group, SceneModel


def chain_of(model: SceneModel, group_id: str | None) -> list[str]:
    """Groupe direct, puis ses parents, jusqu'à la racine."""
    out: list[str] = []
    while group_id is not None:
        out.append(group_id)
        group_id = model.groups[group_id].parent_id
    return out


def unit_of(model: SceneModel, inst_id: str, context: str | None):
    """Unité de sélection d'une instance : ("g", id_groupe) ou ("i", id_instance).
    None si l'instance est hors du groupe dans lequel on est entré."""
    chain = chain_of(model, model.get(inst_id).group_id)
    if context is None:
        return ("g", chain[-1]) if chain else ("i", inst_id)
    if context not in chain:
        return None
    idx = chain.index(context)
    return ("g", chain[idx - 1]) if idx > 0 else ("i", inst_id)


def in_context(model: SceneModel, inst_id: str, context: str | None) -> bool:
    return context is None or context in chain_of(model, model.get(inst_id).group_id)


def leaves(model: SceneModel, unit) -> list[str]:
    """Identifiants des instances contenues dans une unité."""
    kind, ident = unit
    if kind == "i":
        return [ident]
    under = {ident}
    changed = True
    while changed:  # descendants, quelle que soit la profondeur (3 niveaux au plus)
        changed = False
        for g in model.groups.values():
            if g.parent_id in under and g.id not in under:
                under.add(g.id)
                changed = True
    return [i.id for i in model.all() if i.group_id in under]


def prune_empty(groups: dict[str, Group], group_of: dict[str, str | None]) -> dict[str, Group]:
    """Retire les groupes vides (sans instance ni sous-groupe non vide), de proche en proche."""
    groups = {gid: Group(g.id, g.name, g.parent_id) for gid, g in groups.items()}
    while True:
        used = {gid for gid in group_of.values() if gid is not None}
        used |= {g.parent_id for g in groups.values() if g.parent_id is not None}
        empty = [gid for gid in groups if gid not in used]
        if not empty:
            return groups
        for gid in empty:
            del groups[gid]
