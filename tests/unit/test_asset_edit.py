import sqlite3

import pytest

from sbs.domain.asset import Anchor
from sbs.services.kit_importer import import_kit
from sbs.services.library import Library, LibraryError
from tests.unit.test_kit_importer import card, make_files, make_kit


@pytest.fixture
def lib(tmp_path):
    cards = [card("mur_a")]  # 16×20, pivot (3, 17)
    kit = make_kit(tmp_path / "kit", cards)
    make_files(kit, cards[0])
    lb = Library(tmp_path / "lib")
    import_kit(lb, kit)
    return lb


def test_ancrages_persistants_et_revision(lib):
    a = lib.list_assets()[0]
    seen = []
    lib.add_listener(seen.append)
    b = lib.update_geometry(a.uuid, (5, 18), [Anchor("mur_haut", 8, 0)])
    assert (b.pivot_x, b.pivot_y, b.revision) == (5, 18, a.revision + 1)
    assert Library(lib.root).get(a.uuid).anchors == (Anchor("mur_haut", 8, 0),)  # relu depuis le disque
    assert seen == [a.uuid]
    back = lib.update_geometry(a.uuid, (a.pivot_x, a.pivot_y), a.anchors, revision=a.revision)
    assert back.revision == a.revision and back.anchors == ()


@pytest.mark.parametrize("pivot,anchors", [
    ((-1, 0), []), ((17, 0), []), ((0, 21), []), ((1.5, 2), []),
    ((0, 0), [Anchor("", 1, 1)]), ((0, 0), [Anchor("a", 1, 1), Anchor("a", 2, 2)]),
    ((0, 0), [Anchor("a", 99, 1)]),
])
def test_geometrie_invalide_refusee_sans_rien_changer(lib, pivot, anchors):
    a = lib.list_assets()[0]
    with pytest.raises(LibraryError):
        lib.update_geometry(a.uuid, pivot, anchors)
    assert lib.get(a.uuid).revision == a.revision


def test_clone_independant(lib):
    a = lib.list_assets()[0]
    c = lib.clone_asset(a.uuid)
    assert c.uuid != a.uuid and c.origin == "local" and c.source_id != a.source_id
    assert lib.abs_path(c.image_path).is_file() and c.image_path != a.image_path
    lib.update_geometry(c.uuid, (0, 0), [])
    assert (lib.get(a.uuid).pivot_x, lib.get(a.uuid).pivot_y) == (a.pivot_x, a.pivot_y)
    assert lib.count() == 2


def test_ancienne_bibliotheque_v1_migree(tmp_path):
    root = tmp_path / "old"
    root.mkdir()
    db = sqlite3.connect(root / "library.db")
    db.executescript("""CREATE TABLE assets (uuid TEXT PRIMARY KEY, origin TEXT NOT NULL, source_id TEXT NOT NULL,
      name TEXT NOT NULL, category TEXT NOT NULL, description TEXT NOT NULL DEFAULT '', width INTEGER NOT NULL,
      height INTEGER NOT NULL, pivot_x INTEGER NOT NULL, pivot_y INTEGER NOT NULL, mode TEXT NOT NULL DEFAULT '',
      image_path TEXT NOT NULL, normal_path TEXT, emission_path TEXT, sha256 TEXT NOT NULL,
      revision INTEGER NOT NULL DEFAULT 1, extra_json TEXT NOT NULL DEFAULT '{}', UNIQUE (origin, source_id));
      CREATE TABLE variants (asset_uuid TEXT NOT NULL, name TEXT NOT NULL, image_path TEXT NOT NULL,
      sha256 TEXT NOT NULL, PRIMARY KEY (asset_uuid, name));
      INSERT INTO assets (uuid,origin,source_id,name,category,width,height,pivot_x,pivot_y,image_path,sha256)
      VALUES ('u','kit','x','x','c',4,4,0,0,'assets/u/x.png','h'); PRAGMA user_version = 1;""")
    db.commit()
    db.close()
    lb = Library(root)
    assert lb.get("u").anchors == ()
