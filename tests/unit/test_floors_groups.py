import json

import pytest

from sbs.domain import structure as S
from sbs.domain.scene import MAX_GROUP_DEPTH, Group, SceneModel
from sbs.services.project_io import ProjectError, ProjectMeta, load_project, save_project
from tests.unit.test_kit_importer import card, make_files, make_kit
from sbs.services.kit_importer import import_kit
from sbs.services.library import Library


def _three_floors():
    m = SceneModel()
    fl = m.floors_copy()
    S.add_floor(fl, "Étage 1")
    S.add_floor(fl, "Toit")
    m.set_floors(fl)
    return m, [f.id for f in m.floors]


def test_ordre_etage_puis_calque_puis_z_puis_profondeur():
    m, (rdc, e1, toit) = _three_floors()
    l = lambda fid: m.find_floor(fid).layers[0].id
    haut = m.add("a", 0, 0, floor_id=toit, layer_id=l(toit))
    bas = m.add("a", 0, 500, floor_id=rdc, layer_id=l(rdc))  # plus « proche » mais étage plus bas
    milieu = m.add("a", 0, 10, floor_id=e1, layer_id=l(e1))
    assert m.draw_order() == [bas.id, milieu.id, haut.id]
    # Z manuel avant la profondeur automatique, dans un même calque
    a = m.add("a", 0, 0, floor_id=rdc, layer_id=l(rdc))
    m.set_z_manual(a.id, 1)
    assert m.draw_order().index(a.id) > m.draw_order().index(bas.id)


def test_masquer_exclut_de_laffichage_pas_du_modele():
    m, (rdc, e1, toit) = _three_floors()
    i = m.add("a", 0, 0, floor_id=toit, layer_id=m.find_floor(toit).layers[0].id)
    fl = m.floors_copy()
    S.set_visible(fl, toit, None, False)
    m.set_floors(fl)
    assert i.id in m and m.draw_instances() == [] and len(m.draw_instances(visible_only=False)) == 1


def test_structure_refuse_dernier_etage_et_dernier_calque():
    m = SceneModel()
    fl = m.floors_copy()
    with pytest.raises(ValueError):
        S.remove_floor(fl, fl[0].id)
    with pytest.raises(ValueError):
        S.remove_layer(fl, fl[0].id, fl[0].layers[0].id)


def test_reordonner_etages_et_calques():
    m, (rdc, e1, toit) = _three_floors()
    fl = m.floors_copy()
    S.move_floor(fl, rdc, +1)
    assert [f.id for f in fl] == [e1, rdc, toit]
    nl = S.add_layer(fl, rdc, "Détails")
    S.move_layer(fl, rdc, nl.id, -1)
    assert fl[1].layers[0].id == nl.id


def test_set_floors_refuse_de_supprimer_un_etage_utilise():
    m, (rdc, e1, toit) = _three_floors()
    m.add("a", 0, 0, floor_id=toit, layer_id=m.find_floor(toit).layers[0].id)
    fl = m.floors_copy()
    S.remove_floor(fl, toit)
    with pytest.raises(ValueError):
        m.set_floors(fl)


def test_groupes_profondeur_max_et_cycles():
    m = SceneModel()
    i = m.add("a", 0, 0)
    groups = {f"g{n}": Group(f"g{n}", f"G{n}", f"g{n-1}" if n > 1 else None) for n in range(1, MAX_GROUP_DEPTH + 2)}
    with pytest.raises(ValueError):
        m.set_grouping(groups, {i.id: "g1"})
    ok = {k: v for k, v in groups.items() if k != f"g{MAX_GROUP_DEPTH + 1}"}
    m.set_grouping(ok, {i.id: f"g{MAX_GROUP_DEPTH}"})
    cyc = {"a": Group("a", "A", "b"), "b": Group("b", "B", "a")}
    with pytest.raises(ValueError):
        m.set_grouping(cyc, {i.id: "a"})
    assert m.get(i.id).group_id == f"g{MAX_GROUP_DEPTH}"  # état inchangé après refus


def test_replace_refuse_references_inconnues():
    m = SceneModel()
    i = m.add("a", 0, 0)
    i.floor_id = "inconnu"
    with pytest.raises(ValueError):
        SceneModel().replace([i])


@pytest.fixture
def lib(tmp_path):
    cards = [card("mur_a")]
    kit = make_kit(tmp_path / "kit", cards)
    make_files(kit, cards[0])
    lb = Library(tmp_path / "lib")
    import_kit(lb, kit)
    return lb


def test_projet_v2_aller_retour_etages_et_groupes_masque_conserve(tmp_path, lib):
    a = lib.list_assets()[0]
    m, (rdc, e1, toit) = _three_floors()
    ids = []
    for fid, y in ((rdc, 0), (e1, 10), (toit, 20)):
        ids.append(m.add(a.uuid, 5, y, floor_id=fid, layer_id=m.find_floor(fid).layers[0].id).id)
    m.set_grouping({"g": Group("g", "Mur", None)}, {ids[0]: "g", ids[1]: "g"})
    fl = m.floors_copy()
    S.set_visible(fl, toit, None, False)
    S.set_locked(fl, rdc, None, True)
    m.set_floors(fl)
    path = tmp_path / "p.sbsproj"
    save_project(path, ProjectMeta(), m, lib)
    r = load_project(path, lib)
    m2 = SceneModel()
    m2.replace(r.instances, r.floors, r.groups)
    assert [f.name for f in m2.floors] == ["RDC", "Étage 1", "Toit"]
    assert m2.find_floor(toit).visible is False and m2.find_floor(rdc).locked is True
    assert m2.get(ids[0]).group_id == "g" and "g" in m2.groups
    assert m2.snapshot() == m.snapshot()
    assert [i.id for i in m2.draw_instances()] == ids[:2]  # le toit masqué n'est pas affiché


def test_t10_migration_v1_vers_v2(tmp_path, lib):
    a = lib.list_assets()[0]
    m = SceneModel()
    m.add(a.uuid, 1, 2)
    path = tmp_path / "p.sbsproj"
    save_project(path, ProjectMeta(), m, lib)
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["schema_version"] = 1
    for sc in doc["scenes"]:
        sc.pop("floors", None)
        sc.pop("groups", None)
        for inst in sc["instances"]:
            for k in ("floor_id", "layer_id", "group_id"):
                inst.pop(k, None)
    path.write_text(json.dumps(doc), encoding="utf-8")
    r = load_project(path, lib)
    assert len(r.floors) == 1 and len(r.instances) == 1
    m2 = SceneModel()
    m2.replace(r.instances, r.floors, r.groups)
    assert m2.get(r.instances[0].id).floor_id == r.floors[0].id


def test_projet_structure_invalide_refuse(tmp_path, lib):
    m = SceneModel()
    m.add(lib.list_assets()[0].uuid, 0, 0)
    path = tmp_path / "p.sbsproj"
    save_project(path, ProjectMeta(), m, lib)
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["scenes"][0]["instances"][0]["floor_id"] = "fantome"
    path.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(ProjectError):
        load_project(path, lib)
