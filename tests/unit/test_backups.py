"""T12 et résilience : sauvegardes versionnées, récupération après arrêt brutal."""

import os

import pytest

from sbs.domain.scene import SceneModel
from sbs.services import backups
from sbs.services.backups import BackupStore, RecoveryStore
from sbs.services.library import Library
from sbs.services.project_io import ProjectMeta, load_project, save_project, serialize_project


def _png(tmp_path):
    from PIL import Image
    p = tmp_path / "s.png"
    Image.new("RGBA", (4, 4), (255, 0, 0, 255)).save(p)
    return p.read_bytes()


@pytest.fixture
def world(tmp_path):
    lib = Library(tmp_path / "lib")
    a = lib.create_asset("a", _png(tmp_path), (2, 3))
    model = SceneModel()
    model.add(a.uuid, 10, 20)
    return lib, model, a


def test_versions_gardees_limitees_et_dedupliquees(world, tmp_path):
    lib, model, a = world
    meta, path = ProjectMeta(), tmp_path / "p.sbsproj"
    store = BackupStore(tmp_path / "bk", keep=3)
    assert store.snapshot(path, meta.id) is None  # fichier absent : pas d'erreur
    for n in range(5):
        model.add(a.uuid, n, n)
        save_project(path, meta, model, lib)
        assert store.snapshot(path, meta.id) is not None
    assert store.snapshot(path, meta.id) is None  # identique à la dernière : pas de doublon
    versions = store.versions(meta.id)
    assert len(versions) == 3  # les plus anciennes sont élaguées
    assert versions[0].path.name > versions[1].path.name  # plus récente d'abord
    newest = load_project(versions[0].path, lib)
    oldest = load_project(versions[-1].path, lib)
    assert len(newest.instances) == 6 and len(oldest.instances) == 4


def test_identifiant_hostile_ne_sort_pas_du_dossier(tmp_path):
    store = BackupStore(tmp_path / "bk")
    f = tmp_path / "x.sbsproj"
    f.write_text("{}", encoding="utf-8")
    dest = store.snapshot(f, "../../evil")
    assert dest is not None and (tmp_path / "bk") in dest.parents


def test_t12_ecriture_interrompue_garde_la_derniere_copie_saine(world, tmp_path, monkeypatch):
    lib, model, a = world
    meta = ProjectMeta()
    rec = RecoveryStore(tmp_path / "rec")
    rec.write(meta.id, serialize_project(meta, model, lib), "Mon projet", None)
    good = rec.pending()[0].file.read_text(encoding="utf-8")
    model.add(a.uuid, 99, 99)
    real_replace = os.replace
    monkeypatch.setattr(os, "replace", lambda *a, **k: (_ for _ in ()).throw(OSError("coupure")))
    with pytest.raises(OSError):
        rec.write(meta.id, serialize_project(meta, model, lib), "Mon projet", None)
    monkeypatch.setattr(os, "replace", real_replace)
    entry = rec.pending()[0]
    assert entry.file.read_text(encoding="utf-8") == good  # dernière sauvegarde saine intacte
    assert load_project(entry.file, lib).instances.__len__() == 1
    assert not list((tmp_path / "rec").glob("*.tmp"))  # pas de résidu


def test_recuperation_liste_nom_origine_et_effacement(world, tmp_path):
    lib, model, a = world
    meta = ProjectMeta(name="Village")
    rec = RecoveryStore(tmp_path / "rec")
    assert rec.pending() == []
    rec.write(meta.id, serialize_project(meta, model, lib), "Village", tmp_path / "v.sbsproj")
    [entry] = rec.pending()
    assert entry.name == "Village" and entry.origin_path == str(tmp_path / "v.sbsproj")
    rec.clear(meta.id)
    assert rec.pending() == []
    rec.clear(meta.id)  # idempotent


def test_recuperation_sans_fiche_d_informations_reste_possible(world, tmp_path):
    lib, model, _ = world
    meta = ProjectMeta()
    rec = RecoveryStore(tmp_path / "rec")
    rec.write(meta.id, serialize_project(meta, model, lib), "X", None)
    for f in (tmp_path / "rec").glob("*.info.json"):
        f.unlink()  # arrêt entre les deux écritures
    [entry] = rec.pending()
    assert entry.origin_path is None and entry.saved_at
    (tmp_path / "rec" / "zz.info.json").write_text("{pas du json", encoding="utf-8")  # fiche abîmée
    assert len(rec.pending()) == 1


def test_nettoyage_des_fichiers_temporaires(tmp_path):
    (tmp_path / "a.tmp").write_text("x")
    (tmp_path / "b.sbsproj").write_text("x")
    assert backups.remove_leftovers(tmp_path) == 1
    assert (tmp_path / "b.sbsproj").exists()
