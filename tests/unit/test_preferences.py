import json

from sbs.services.atomic import write_text_atomic
from sbs.services.preferences import Preferences


def test_aller_retour(tmp_path):
    p = Preferences(tmp_path / "prefs.json")
    p.set("zoom", 200)
    p.set("nom", "é à ç")
    p.save()
    q = Preferences(tmp_path / "prefs.json")
    assert q.get("zoom") == 200 and q.get("nom") == "é à ç"
    assert q.load_error is None


def test_fichier_absent(tmp_path):
    assert Preferences(tmp_path / "x.json").get("a", 5) == 5


def test_fichier_corrompu_ne_plante_pas_et_reste_intact(tmp_path):
    f = tmp_path / "prefs.json"
    f.write_text("{pas du json", encoding="utf-8")
    p = Preferences(f)
    assert p.load_error and p.get("a") is None
    assert f.read_text(encoding="utf-8") == "{pas du json"


def test_version_inconnue_refusee(tmp_path):
    f = tmp_path / "prefs.json"
    f.write_text(json.dumps({"schema_version": 999, "values": {"a": 1}}), encoding="utf-8")
    p = Preferences(f)
    assert p.load_error and p.get("a") is None


def test_ecriture_atomique_aucun_residu(tmp_path):
    f = tmp_path / "sous" / "a.txt"
    write_text_atomic(f, "un")
    write_text_atomic(f, "deux")
    assert f.read_text(encoding="utf-8") == "deux"
    assert [x.name for x in f.parent.iterdir()] == ["a.txt"]
