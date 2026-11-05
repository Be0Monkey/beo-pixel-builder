import pytest

from sbs.commands.history import History
from sbs.commands.instances import MoveInstances, PlaceInstances, RemoveInstances, SetZ
from sbs.domain.scene import Instance, SceneModel


class Clock:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t


@pytest.fixture
def env():
    m = SceneModel()
    clock = Clock()
    return m, History(m, clock=clock), clock


def inst(i, x=0, y=0):
    return Instance(f"id{i}", "asset", x, y)


def test_t04_deplacer_puis_annuler_restaure_exactement(env):
    m, h, _ = env
    h.execute(PlaceInstances([inst(1, 10, 20)]))
    before = m.snapshot()
    h.execute(MoveInstances({"id1": (10, 20, 33, -7)}, "Déplacer"))
    assert (m.get("id1").x, m.get("id1").y) == (33, -7)
    h.undo()
    assert m.snapshot() == before
    h.redo()
    assert (m.get("id1").x, m.get("id1").y) == (33, -7)


def test_annuler_suppression_rend_l_ordre_d_insertion(env):
    m, h, _ = env
    h.execute(PlaceInstances([inst(i, 0, 5) for i in range(5)]))
    before = m.snapshot()
    h.execute(RemoveInstances(["id1", "id3"]))
    assert [i.id for i in m.all()] == ["id0", "id2", "id4"]
    h.undo()
    assert m.snapshot() == before  # même rang : l'ordre à profondeur égale est inchangé
    h.redo()
    assert [i.id for i in m.all()] == ["id0", "id2", "id4"]


def test_une_commande_une_seule_notification(env):
    m, h, _ = env
    calls = []
    m.add_listener(lambda: calls.append(1))
    h.execute(PlaceInstances([inst(i) for i in range(10)]))
    assert len(calls) == 1
    h.undo()
    assert len(calls) == 2


def test_noms_et_etats(env):
    m, h, _ = env
    assert not h.can_undo and not h.can_redo and h.undo_name is None
    h.execute(PlaceInstances([inst(1)], "Ajouter mur"))
    h.execute(SetZ({"id1": (0, 1)}, "Mettre devant"))
    assert h.undo_name == "Mettre devant" and h.redo_name is None
    h.undo()
    assert h.undo_name == "Ajouter mur" and h.redo_name == "Mettre devant"


def test_nouvelle_action_apres_annulation_efface_le_retablissement(env):
    m, h, _ = env
    h.execute(PlaceInstances([inst(1)]))
    h.execute(PlaceInstances([inst(2)]))
    h.undo()
    h.execute(PlaceInstances([inst(3)]))
    assert not h.can_redo and [i.id for i in m.all()] == ["id1", "id3"]


def test_gestes_continus_fusionnes_dans_le_temps(env):
    m, h, clock = env
    h.execute(PlaceInstances([inst(1)]))
    h.mark_saved()
    h.execute(MoveInstances({"id1": (0, 0, 1, 0)}, "Clavier", mergeable=True))
    clock.t += 0.3
    h.execute(MoveInstances({"id1": (1, 0, 2, 0)}, "Clavier", mergeable=True))
    clock.t += 0.3
    h.execute(MoveInstances({"id1": (2, 0, 3, 0)}, "Clavier", mergeable=True))
    assert m.get("id1").x == 3
    h.undo()  # UNE seule entrée pour les trois appuis
    assert m.get("id1").x == 0
    h.redo()
    clock.t += 5  # pause : nouvelle entrée
    h.execute(MoveInstances({"id1": (3, 0, 4, 0)}, "Clavier", mergeable=True))
    h.undo()
    assert m.get("id1").x == 3


def test_modifie_puis_annule_jusqu_a_l_etat_enregistre_n_est_plus_modifie(env):
    m, h, _ = env
    h.execute(PlaceInstances([inst(1)]))
    h.mark_saved()
    assert not h.dirty
    h.execute(MoveInstances({"id1": (0, 0, 5, 5)}))
    assert h.dirty
    h.undo()
    assert not h.dirty
    h.undo()
    assert h.dirty  # on est avant l'état enregistré
    h.redo()
    assert not h.dirty


def test_etat_enregistre_perdu_si_la_branche_est_ecrasee(env):
    m, h, _ = env
    h.execute(PlaceInstances([inst(1)]))
    h.execute(PlaceInstances([inst(2)]))
    h.mark_saved()
    h.undo()
    h.execute(PlaceInstances([inst(3)]))  # écrase la branche qui contenait l'état enregistré
    h.undo()
    assert h.dirty  # jamais « propre » à tort


def test_limite_de_l_historique(env):
    m, _, clock = env
    h = History(m, limit=5, clock=clock)
    for i in range(12):
        h.execute(PlaceInstances([inst(i)]))
    undone = 0
    while h.undo():
        undone += 1
    assert undone == 5 and len(m) == 7


def test_clear_repart_a_zero(env):
    m, h, _ = env
    h.execute(PlaceInstances([inst(1)]))
    h.clear()
    assert not h.can_undo and not h.dirty
