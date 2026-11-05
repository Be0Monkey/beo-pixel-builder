import json

import pytest

from sbs.domain.scene import SceneModel
from sbs.services.clipboard_codec import decode_instances, encode_instances
from sbs.services.kit_importer import import_kit
from sbs.services.library import Library
from tests.unit.test_kit_importer import card, make_files, make_kit


@pytest.fixture
def lib(tmp_path):
    c = card("mur_a")
    kit = make_kit(tmp_path / "kit", [c])
    make_files(kit, c)
    lib = Library(tmp_path / "lib")
    import_kit(lib, kit)
    return lib


def test_aller_retour(lib):
    a = lib.list_assets()[0]
    m = SceneModel()
    i = m.add(a.uuid, 4, 5)
    m.set_z_manual(i.id, 2)
    entries = decode_instances(encode_instances(m.all(), lib))
    assert [(e.asset_uuid, e.source_id, e.x, e.y, e.z_manual) for e in entries] == \
           [(a.uuid, "mur_a", 4, 5, 2)]


@pytest.mark.parametrize("text", [
    "", "pas du json", "[]", '{"format": "autre"}', '{"format":"sbs-instances","version":2,"items":[]}',
    '{"format":"sbs-instances","version":1,"items":"x"}',
    '{"format":"sbs-instances","version":1,"items":[5]}',
    '{"format":"sbs-instances","version":1,"items":[{"asset_uuid":"u","x":1.5,"y":0}]}',
    '{"format":"sbs-instances","version":1,"items":[{"asset_uuid":3,"x":1,"y":0}]}',
    '{"format":"sbs-instances","version":1,"items":[{"asset_uuid":"u","x":1,"y":0,"variant":4}]}',
    None,
])
def test_contenu_non_fiable_refuse(text):
    with pytest.raises(ValueError):
        decode_instances(text)
