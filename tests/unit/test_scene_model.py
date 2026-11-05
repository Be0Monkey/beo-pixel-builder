import pytest

from sbs.domain.scene import SceneModel


def test_ajout_deplacement_suppression():
    m = SceneModel()
    a = m.add("asset-1", 10, 20)
    assert len(m) == 1 and (a.x, a.y) == (10, 20)
    m.set_position(a.id, 11, 22)
    assert (m.get(a.id).x, m.get(a.id).y) == (11, 22)
    assert [i.id for i in m.remove([a.id, "inconnu"])] == [a.id]
    assert len(m) == 0


def test_valeurs_invalides_refusees():
    m = SceneModel()
    for bad in (1.5, float("nan"), float("inf"), "3", None, True):
        with pytest.raises(ValueError):
            m.add("a", bad, 0)
    a = m.add("a", 0, 0)
    with pytest.raises(ValueError):
        m.set_position(a.id, 0, 2.5)


def test_t08_ordre_stable_a_profondeur_egale():
    m = SceneModel()
    ids = [m.add("a", 0, 50).id for _ in range(5)]
    assert m.draw_order() == ids  # ordre d'insertion
    assert m.draw_order() == ids  # identique à chaque appel


def test_profondeur_auto_puis_z_manuel():
    m = SceneModel()
    loin = m.add("a", 0, 10)
    pres = m.add("a", 0, 90)
    assert m.draw_order() == [loin.id, pres.id]  # y plus grand = devant
    m.set_z_manual(loin.id, 1)  # forcé devant
    assert m.draw_order() == [pres.id, loin.id]
