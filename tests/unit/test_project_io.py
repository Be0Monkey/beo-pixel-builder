import json
import os

import pytest

from sbs.domain.scene import SceneModel
from sbs.services.kit_importer import import_kit
from sbs.services.library import Library
from sbs.services.project_io import (
    ProjectError,
    ProjectMeta,
    load_project,
    save_project,
)
from tests.unit.test_kit_importer import card, make_files, make_kit


@pytest.fixture
def lib_and_kit(tmp_path):
    cards = [card("mur_a"), card("toit_b", "toitures")]
    kit = make_kit(tmp_path / "kit", cards)
    for c in cards:
        make_files(kit, c)
    lib = Library(tmp_path / "lib")
    import_kit(lib, kit)
    return lib, kit


def _model(lib):
    a, b = lib.list_assets()
    m = SceneModel()
    m.add(a.uuid, 10, 20)
    m.add(b.uuid, -5, 40)
    i3 = m.add(a.uuid, 10, 20)  # même profondeur : ordre d'insertion
    m.set_z_manual(i3.id, 2)
    return m


def test_t01_aller_retour_identifiants_positions_ordre(tmp_path, lib_and_kit):
    lib, _ = lib_and_kit
    m = _model(lib)
    path = tmp_path / "Mes projets é" / "ma maison.sbsproj"  # accents + espaces
    meta = ProjectMeta(name="ma maison")
    save_project(path, meta, m, lib)
    r = load_project(path, lib)
    assert [(i.id, i.asset_uuid, i.x, i.y, i.z_manual) for i in r.instances] == \
           [(i.id, i.asset_uuid, i.x, i.y, i.z_manual) for i in m.all()]
    m2 = SceneModel()
    m2.replace(r.instances, r.floors, r.groups)
    assert m2.draw_order() == m.draw_order()
    assert r.meta.id == meta.id and not r.missing_assets and r.remapped == 0


def test_sauvegarde_atomique_echec_laisse_le_fichier_intact(tmp_path, lib_and_kit, monkeypatch):
    lib, _ = lib_and_kit
    m = _model(lib)
    path = tmp_path / "p.sbsproj"
    meta = ProjectMeta()
    save_project(path, meta, m, lib)
    before = path.read_bytes()
    m.add(lib.list_assets()[0].uuid, 1, 1)

    def boom(*a, **k):
        raise OSError("disque plein simulé")

    monkeypatch.setattr("sbs.services.atomic.os.replace", boom)
    with pytest.raises(OSError):
        save_project(path, meta, m, lib)
    assert path.read_bytes() == before  # T12 : dernière sauvegarde saine
    assert [p.name for p in tmp_path.iterdir() if p.suffix == ".tmp"] == []  # pas de résidu


def test_copie_de_secours_bak(tmp_path, lib_and_kit):
    lib, _ = lib_and_kit
    m = _model(lib)
    path = tmp_path / "p.sbsproj"
    meta = ProjectMeta()
    save_project(path, meta, m, lib)
    first = path.read_text(encoding="utf-8")
    m.add(lib.list_assets()[0].uuid, 1, 1)
    save_project(path, meta, m, lib)
    assert (tmp_path / "p.sbsproj.bak").read_text(encoding="utf-8") == first


@pytest.mark.parametrize("content,fragment", [
    ("{pas du json", "abîmé"),
    ("[1, 2]", "n'est pas un projet"),
    (json.dumps({"format": "autre"}), "n'est pas un projet"),
    (json.dumps({"format": "sprite-builder-studio-project", "schema_version": 999, "scenes": []}),
     "plus récente"),
    (json.dumps({"format": "sprite-builder-studio-project", "schema_version": 0, "scenes": []}),
     "version"),
    (json.dumps({"format": "sprite-builder-studio-project", "schema_version": 1, "scenes": []}),
     "0 scène"),
])
def test_t10_t11_fichiers_invalides_erreur_claire(tmp_path, lib_and_kit, content, fragment):
    lib, _ = lib_and_kit
    p = tmp_path / "x.sbsproj"
    p.write_text(content, encoding="utf-8")
    with pytest.raises(ProjectError, match=fragment):
        load_project(p, lib)


def _doc(instances):
    return {"format": "sprite-builder-studio-project", "schema_version": 1, "id": "x",
            "scenes": [{"id": "s", "name": "S", "instances": instances}]}


@pytest.mark.parametrize("inst", [
    {"id": "a", "asset_uuid": "u", "x": 1.5, "y": 0},
    {"id": "a", "asset_uuid": "u", "x": 1, "y": "2"},
    {"id": "a", "asset_uuid": "u", "x": True, "y": 0},
    {"id": "a", "asset_uuid": 5, "x": 1, "y": 0},
    {"asset_uuid": "u", "x": 1, "y": 0},
    "pas un objet",
    {"id": "a", "asset_uuid": "u", "x": 1, "y": 0, "z_manual": "haut"},
])
def test_donnees_mal_formees_refusees(tmp_path, lib_and_kit, inst):
    lib, _ = lib_and_kit
    p = tmp_path / "x.sbsproj"
    p.write_text(json.dumps(_doc([inst])), encoding="utf-8")
    with pytest.raises(ProjectError):
        load_project(p, lib)


def test_identifiants_en_double_refuses(tmp_path, lib_and_kit):
    lib, _ = lib_and_kit
    i = {"id": "a", "asset_uuid": "u", "x": 1, "y": 0}
    p = tmp_path / "x.sbsproj"
    p.write_text(json.dumps(_doc([i, dict(i)])), encoding="utf-8")
    with pytest.raises(ProjectError, match="double"):
        load_project(p, lib)


def test_aucun_code_execute_au_chargement(tmp_path, lib_and_kit):
    lib, _ = lib_and_kit
    marker = tmp_path / "pwned"
    d = _doc([])
    d["__import__"] = f"open(r'{marker}','w')"
    d["name"] = "__import__('os').system('echo x')"
    p = tmp_path / "x.sbsproj"
    p.write_text(json.dumps(d), encoding="utf-8")
    load_project(p, lib)
    assert not marker.exists()


def test_images_absentes_instances_conservees_et_references_gardees(tmp_path, lib_and_kit):
    lib, _ = lib_and_kit
    m = _model(lib)
    path = tmp_path / "p.sbsproj"
    save_project(path, ProjectMeta(), m, lib)
    autre = Library(tmp_path / "autre_bibliotheque")  # bibliothèque vide : tout est « absent »
    r = load_project(path, autre)
    assert len(r.instances) == 3 and len(r.missing_assets) == 2
    m2 = SceneModel()
    m2.replace(r.instances, r.floors, r.groups)
    save_project(path, r.meta, m2, autre)  # re-sauvegarde sans rien perdre
    doc = json.loads(path.read_text(encoding="utf-8"))
    assert len(doc["scenes"][0]["instances"]) == 3
    assert {v["source_id"] for v in doc["library_refs"].values()} == {"mur_a", "toit_b"}


def test_projet_ouvert_sur_un_autre_ordinateur_est_rattache_par_source(tmp_path, lib_and_kit):
    lib, kit = lib_and_kit
    m = _model(lib)
    path = tmp_path / "p.sbsproj"
    save_project(path, ProjectMeta(), m, lib)
    autre = Library(tmp_path / "autre")
    import_kit(autre, kit)  # mêmes modules, UUID différents
    r = load_project(path, autre)
    assert r.remapped == 3 and not r.missing_assets
    assert all(autre.get(i.asset_uuid) is not None for i in r.instances)


def test_chemin_long_et_accentue(tmp_path, lib_and_kit):
    lib, _ = lib_and_kit
    d = tmp_path
    for _ in range(6):
        d = d / ("dossier très long et accentué é à ç " * 2)
    path = d / "projet été.sbsproj"
    if os.name == "nt" and len(str(path)) > 240:
        pytest.skip("chemin > MAX_PATH sans préfixe long")
    save_project(path, ProjectMeta(), _model(lib), lib)
    assert load_project(path, lib).instances
