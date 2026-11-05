from sbs.domain.ids import is_valid_id, new_id


def test_ids_uniques_et_valides():
    ids = {new_id() for _ in range(1000)}
    assert len(ids) == 1000
    assert all(is_valid_id(i) for i in ids)


def test_id_invalide():
    assert not is_valid_id("angle_rdc_droit")
    assert not is_valid_id(None)
